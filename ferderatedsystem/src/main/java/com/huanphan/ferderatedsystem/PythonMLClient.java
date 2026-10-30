package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.ArrayList;

/** Gửi metadata và đường dẫn artifact qua HTTP; tensor được lưu ở workspace dùng chung. */
@Component
public class PythonMLClient {
    private static final Logger log=LoggerFactory.getLogger(PythonMLClient.class);
    // Dùng HTTP/1.1 để tránh yêu cầu nâng cấp h2c không được uvicorn hỗ trợ.
    private final HttpClient client;
    private final ObjectMapper json;
    private final String baseUrl;
    private final int maxAttempts;
    private final long retryDelayMs,maxRetryDelayMs;
    private final Duration requestTimeout;
    private final Sleeper sleeper;
    private volatile boolean checkpointRetrySupported;
    private volatile JsonNode expectedRuntime;
    private final java.util.concurrent.atomic.AtomicLong retryCounter=new java.util.concurrent.atomic.AtomicLong();
    private volatile String lastRetryReason="";
    public Map<String,Object> retryStatus() {return Map.of("retryAttempts",retryCounter.get(),"lastRetryReason",lastRetryReason);}
    @Value("${minifls.worker.recovery-budget-seconds:7200}") private long recoveryBudgetSeconds=7200;
    @Value("${minifls.worker.retry-jitter:0}") private double retryJitter=0;
    public void requireRuntime(JsonNode runtime) {expectedRuntime=runtime.deepCopy();}
    @FunctionalInterface interface Sleeper {void sleep(long millis) throws InterruptedException;}
    public PythonMLClient(ObjectMapper json,String baseUrl) {this(json,baseUrl,4,2000,30000,1800);}
    @Autowired
    public PythonMLClient(ObjectMapper json,@Value("${minifls.worker-url}") String baseUrl,
                          @Value("${minifls.worker.max-attempts:4}") int maxAttempts,
                          @Value("${minifls.worker.retry-delay-ms:2000}") long retryDelayMs,
                          @Value("${minifls.worker.retry-max-delay-ms:30000}") long maxRetryDelayMs,
                          @Value("${minifls.worker.request-timeout-seconds:1800}") long timeoutSeconds) {
        this(json,baseUrl,maxAttempts,retryDelayMs,maxRetryDelayMs,Duration.ofSeconds(timeoutSeconds),
                HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(10)).build(),Thread::sleep);
    }
    PythonMLClient(ObjectMapper json,String baseUrl,int maxAttempts,long retryDelayMs,long maxRetryDelayMs,
                   Duration timeout,HttpClient client,Sleeper sleeper) {
        if(maxAttempts<1||maxAttempts>100||retryDelayMs<0||maxRetryDelayMs<retryDelayMs||maxRetryDelayMs>60000||timeout.isNegative()||timeout.isZero())
            throw new IllegalArgumentException("Invalid worker retry/timeout configuration");
        this.json=json;this.baseUrl=baseUrl;this.maxAttempts=maxAttempts;this.retryDelayMs=retryDelayMs;
        this.maxRetryDelayMs=maxRetryDelayMs;this.requestTimeout=timeout;this.client=client;this.sleeper=sleeper;
    }
    public JsonNode get(String route) {return request(route,null);}
    public JsonNode post(String route,Object payload) {return request(route,payload);}
    public Map<String,Object> retryPolicy() {
        return Map.of("maxAttempts",maxAttempts,"retryDelayMs",retryDelayMs,"retryMaxDelayMs",maxRetryDelayMs,"requestTimeoutMs",requestTimeout.toMillis(),"recoveryBudgetSeconds",recoveryBudgetSeconds,"retryJitter",retryJitter);
    }
    private boolean checkpointRoute(String route) {return route.equals("/train")||route.equals("/models/initialize")||route.equals("/models/aggregate");}
    private void ensureCheckpointRetrySupport(boolean refresh) {
        if(refresh||!checkpointRetrySupported) {
            var runtime=get("/runtime");
            if(expectedRuntime!=null && !expectedRuntime.equals(runtime))
                throw new IllegalStateException("Worker runtime changed during operation; refusing incompatible restart");
            if(!runtime.path("idempotentCheckpointOperations").asBoolean())
                throw new IllegalStateException("Worker lacks safe checkpoint retry support; restart the updated Python worker or set MINIFLS_WORKER_MAX_ATTEMPTS=1");
            checkpointRetrySupported=true;
        }
    }
    /** Điểm trỏ Java → package minifls.methods.fedavg. */
    public List<Double> fedAvgWeights(List<Integer> samples) {
        return methodWeights("fedavg",samples,List.of());
    }
    /** Điểm trỏ Java → package minifls.methods.fedlbw. */
    public List<Double> fedLBWWeights(List<Integer> samples,List<Double> proxyLosses) {
        return methodWeights("fedlbw",samples,proxyLosses);
    }
    public List<Double> aggregationWeights(String method,List<Integer> samples,List<Double> losses) {
        return switch(method) {
            case "fedavg" -> fedAvgWeights(samples);
            case "fedlbw" -> fedLBWWeights(samples,losses);
            default -> throw new IllegalArgumentException("Unknown Python method: "+method);
        };
    }
    private List<Double> methodWeights(String method,List<Integer> samples,List<Double> losses) {
        var response=post("/methods/"+method+"/weights",Map.of("samples",samples,"losses",losses));
        if(!method.equals(response.path("method").asText()) || !response.path("weights").isArray()
                || response.path("weights").size()!=samples.size())
            throw new IllegalStateException("Invalid method weights response");
        var result=new ArrayList<Double>();
        for(var value:response.path("weights")) {
            if(!value.isNumber() || !Double.isFinite(value.asDouble()) || value.asDouble()<0)
                throw new IllegalStateException("Invalid aggregation weight");
            result.add(value.asDouble());
        }
        if(Math.abs(result.stream().mapToDouble(Double::doubleValue).sum()-1)>1e-8)
            throw new IllegalStateException("Aggregation weights must sum to one");
        return List.copyOf(result);
    }
    private JsonNode request(String route,Object payload) {
        long started=System.nanoTime();
        String method=payload==null?"GET":"POST";
        boolean checkpoint=payload!=null&&checkpointRoute(route);
        if(checkpoint&&maxAttempts>1) ensureCheckpointRetrySupport(expectedRuntime!=null);
        // Serialize once: transport retries keep exactly the same payload and operationId.
        final HttpRequest request;
        try {
            var builder=HttpRequest.newBuilder(URI.create(baseUrl+route)).timeout(Duration.ofMillis(Math.min(requestTimeout.toMillis(),Math.max(1,recoveryBudgetSeconds)*1000)));
            // Correlation headers only affect logs; experiment validation still uses payload/checkpoints.
            var metadata=payload instanceof Map<?,?> map ? map : Map.of();
            correlationHeader(builder,"X-MiniFLS-Experiment",metadata.get("experimentId"),MDC.get("experimentId"));
            correlationHeader(builder,"X-MiniFLS-Round",metadata.get("roundId"),MDC.get("roundId"));
            correlationHeader(builder,"X-MiniFLS-Client",metadata.get("clientId"),null);
            correlationHeader(builder,"X-MiniFLS-Attempt",metadata.get("operationId"),MDC.get("operationId"));
            if(payload!=null) builder.header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(json.writeValueAsString(payload)));
            else builder.GET();
            request=builder.build();
        } catch(com.fasterxml.jackson.core.JsonProcessingException e) {
            throw new IllegalArgumentException("Cannot serialize worker request method="+method+" route="+route,e);
        }
        long delay=retryDelayMs;
        for(int attempt=1;attempt<=maxAttempts;attempt++) {
            if((System.nanoTime()-started)/1e9>=recoveryBudgetSeconds)
                throw failure(method,route,attempt,"recovery budget exhausted",null);
            if(checkpoint&&attempt>1) ensureCheckpointRetrySupport(true);
            HttpResponse<String> response;
            try {
                log.debug("worker.request method={} route={} worker={} attempt={}/{}",method,route,baseUrl,attempt,maxAttempts);
                response=client.send(request,HttpResponse.BodyHandlers.ofString());
            } catch(InterruptedException e) {
                Thread.currentThread().interrupt();
                throw failure(method,route,attempt,"interrupted",e);
            } catch(java.io.IOException e) {
                if(attempt==maxAttempts) throw failure(method,route,attempt,e.toString(),e);
                pause(method,route,attempt,delay,e.toString());delay=nextDelay(delay);continue;
            }
            if(response.statusCode()/100!=2) {
                String reason="HTTP "+response.statusCode()+": "+response.body();
                if(retryable(response)&&attempt<maxAttempts) {
                    pause(method,route,attempt,delay,reason);delay=nextDelay(delay);continue;
                }
                throw failure(method,route,attempt,reason,null);
            }
            // Invalid JSON is an application/protocol error, not a transient transport error.
            try {
                var result=json.readTree(response.body());
                if(result==null||result.isNull()) throw new IllegalStateException("Worker returned an empty JSON response method="+method+" route="+route);
                log.debug("worker.response method={} route={} status={} attempt={} elapsedMs={}",method,route,response.statusCode(),attempt,(System.nanoTime()-started)/1e6);
                return result;
            } catch(com.fasterxml.jackson.core.JsonProcessingException e) {
                throw failure(method,route,attempt,"Invalid JSON response",e);
            }
        }
        throw new IllegalStateException("Unreachable worker retry state");
    }
    private boolean retryable(HttpResponse<String> response) {
        int status=response.statusCode();
        if(status==502||status==503||status==504) return true;
        if(status==409) try {
            var body=json.readTree(response.body());
            return body!=null&&body.path("detail").asText().equals("Worker busy; only one active ML operation allowed");
        } catch(com.fasterxml.jackson.core.JsonProcessingException ignored) {return false;}
        return false;
    }
    private long nextDelay(long delay) {return Math.min(maxRetryDelayMs,delay*2);}
    private void pause(String method,String route,int attempt,long delay,String reason) {
        retryCounter.incrementAndGet();lastRetryReason=reason;
        if(!Double.isFinite(retryJitter)||retryJitter<0||retryJitter>1) throw new IllegalStateException("Invalid retry jitter");
        delay=Math.min(maxRetryDelayMs,Math.max(0,(long)(delay*(1+java.util.concurrent.ThreadLocalRandom.current().nextDouble(-1,1)*retryJitter))));
        log.warn("worker.retry method={} route={} worker={} attempt={}/{} nextAttempt={} delayMs={} reason={} experiment={} round={} operation={}",method,route,baseUrl,attempt,maxAttempts,attempt+1,delay,reason,MDC.get("experimentId"),MDC.get("roundId"),MDC.get("operationId"));
        try {sleeper.sleep(delay);}
        catch(InterruptedException e) {Thread.currentThread().interrupt();throw failure(method,route,attempt,"retry wait interrupted",e);}
    }
    private IllegalStateException failure(String method,String route,int attempt,String reason,Throwable cause) {
        String message="Worker request failed method="+method+" route="+route+" worker="+baseUrl+" attempts="+attempt+"/"+maxAttempts+" reason="+reason;
        log.error("worker.failed {}",message);
        return new IllegalStateException(message,cause);
    }
    private void correlationHeader(HttpRequest.Builder builder,String header,Object value,String fallback) {
        String text=value==null?fallback:value.toString();
        if(text!=null) builder.header(header,text);
    }
}
