package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import org.springframework.beans.factory.annotation.Value;
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
    private final HttpClient client=HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(10)).build();
    private final ObjectMapper json;
    private final String baseUrl;
    public PythonMLClient(ObjectMapper json,@Value("${minifls.worker-url}") String baseUrl) {this.json=json;this.baseUrl=baseUrl;}
    public JsonNode get(String route) {return request(route,null);}
    public JsonNode post(String route,Object payload) {return request(route,payload);}
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
        log.debug("worker.request method={} route={} worker={}",method,route,baseUrl);
        try {
            var builder=HttpRequest.newBuilder(URI.create(baseUrl+route)).timeout(Duration.ofMinutes(30));
            // Correlation headers only affect logs; experiment validation still uses payload/checkpoints.
            var metadata=payload instanceof Map<?,?> map ? map : Map.of();
            correlationHeader(builder,"X-MiniFLS-Experiment",metadata.get("experimentId"),MDC.get("experimentId"));
            correlationHeader(builder,"X-MiniFLS-Round",metadata.get("roundId"),MDC.get("roundId"));
            correlationHeader(builder,"X-MiniFLS-Client",metadata.get("clientId"),null);
            correlationHeader(builder,"X-MiniFLS-Attempt",metadata.get("operationId"),MDC.get("operationId"));
            if(payload!=null) builder.header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(json.writeValueAsString(payload)));
            else builder.GET();
            var response=client.send(builder.build(),HttpResponse.BodyHandlers.ofString());
            if(response.statusCode()/100!=2) {
                log.warn("worker.rejected method={} route={} status={} elapsedMs={}",method,route,response.statusCode(),(System.nanoTime()-started)/1e6);
                throw new IllegalStateException("Worker HTTP "+response.statusCode()+": "+response.body());
            }
            log.debug("worker.response method={} route={} status={} elapsedMs={}",method,route,response.statusCode(),(System.nanoTime()-started)/1e6);
            return json.readTree(response.body());
        } catch(InterruptedException e) {
            Thread.currentThread().interrupt();log.warn("worker.interrupted method={} route={}",method,route);
            throw new IllegalStateException("Worker call interrupted",e);
        }
        catch(java.io.IOException e) {
            log.error("worker.unavailable method={} route={} worker={} elapsedMs={} error={}",method,route,baseUrl,(System.nanoTime()-started)/1e6,e.toString());
            throw new IllegalStateException("Worker unavailable",e);
        }
    }
    private void correlationHeader(HttpRequest.Builder builder,String header,Object value,String fallback) {
        String text=value==null?fallback:value.toString();
        if(text!=null) builder.header(header,text);
    }
}
