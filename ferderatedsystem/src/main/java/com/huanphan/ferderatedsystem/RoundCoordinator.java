package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import org.springframework.stereotype.Service;
import jakarta.annotation.PreDestroy;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Điều phối round đồng bộ; Java quyết định update nào được chấp nhận và model nào được commit. */
@Service
public class RoundCoordinator {
    private final PythonMLClient worker;
    private final ExperimentRepository repository;
    private final ObjectMapper json;
    // Chỉ chạy một thí nghiệm tại một thời điểm để không tranh chấp worker ML duy nhất.
    private final ExecutorService executor=Executors.newSingleThreadExecutor();
    private final AtomicBoolean busy=new AtomicBoolean(false);

    public RoundCoordinator(PythonMLClient worker,ExperimentRepository repository,ObjectMapper json) {
        this.worker=worker;this.repository=repository;this.json=json;
    }
    /** Trạng thái của round đã commit gần nhất, dùng để tiếp tục sau gián đoạn. */
    public static class Snapshot {
        public int round;
        public int modelVersion;
        public String checkpointPath;
        public double cumulativeVirtualSeconds;
        public Double timeToTargetSeconds;
        public List<ClientProfile> clients=new ArrayList<>();
        public JsonNode initialEvaluation;
        public JsonNode manifest;
        public String gitCommit;
        public boolean gitDirty;
    }
    public void start(ExperimentConfig c) {
        c.check();
        if(!busy.compareAndSet(false,true)) throw new IllegalStateException("Another experiment is running");
        try {repository.create(c);}
        catch(RuntimeException e) {busy.set(false);throw e;}
        executor.submit(() -> run(c,null));
    }
    public void resume(String id) {
        if(!busy.compareAndSet(false,true)) throw new IllegalStateException("Another experiment is running");
        try {
            var row=repository.find(id);
            if(!Set.of("FAILED","INTERRUPTED").contains(row.get("status"))) throw new IllegalArgumentException("Only failed/interrupted experiments can resume");
            var config=json.readValue((String)row.get("config"),ExperimentConfig.class);
            // Khôi phục từ SQLite thay vì dùng state trong bộ nhớ của tác vụ đã lỗi.
            Snapshot snapshot=row.get("snapshot")==null ? null : json.readValue((String)row.get("snapshot"),Snapshot.class);
            repository.status(id,"RUNNING",null);
            executor.submit(() -> run(config,snapshot));
        } catch(Exception e) {busy.set(false);throw new IllegalArgumentException(e.getMessage(),e);}
    }
    private Map<String,Object> context(ExperimentConfig c,String operation) {
        var map=new LinkedHashMap<String,Object>();
        map.put("experimentId",c.experimentId());map.put("manifestPath",c.manifestPath());
        map.put("seed",c.seed());map.put("operationId",operation);return map;
    }
    private JsonNode evaluate(ExperimentConfig c,String checkpoint,String split) {
        return worker.post("/models/evaluate",Map.of("manifestPath",c.manifestPath(),"checkpointPath",checkpoint,"split",split));
    }
    private Snapshot initialize(ExperimentConfig c) {
        var manifest=worker.get("/datasets/manifest?manifestPath="+URLEncoder.encode(c.manifestPath(),StandardCharsets.UTF_8));
        if(manifest.path("totalClients").asInt()!=c.totalClients()) throw new IllegalArgumentException("Manifest totalClients mismatch");
        Snapshot s=new Snapshot();s.manifest=manifest;
        for(var entry:manifest.path("clients")) s.clients.add(new ClientProfile(entry.path("clientId").asInt(),entry.path("numSamples").asInt(),c.totalClients(),c.resourceProfile()));
        var initialized=worker.post("/models/initialize",context(c,UUID.randomUUID().toString()));
        s.checkpointPath=initialized.path("checkpointPath").asText();
        s.initialEvaluation=evaluate(c,s.checkpointPath,"test");
        if(s.initialEvaluation.path("accuracy").asDouble()>=c.targetAccuracy()) s.timeToTargetSeconds=0.0;
        try {
            var process=new ProcessBuilder("git","rev-parse","HEAD").start();
            s.gitCommit=new String(process.getInputStream().readAllBytes(),StandardCharsets.UTF_8).trim();
            var status=new ProcessBuilder("git","status","--porcelain").start();
            s.gitDirty=status.getInputStream().readAllBytes().length>0;
        }catch(Exception e) {s.gitCommit="unknown";}
        repository.snapshot(c.experimentId(),s);
        return s;
    }
    private void run(ExperimentConfig c,Snapshot s) {
        try {
            if(s==null) s=initialize(c);
            // Khi worker nạp lại dataset sau restart, hash của các file được kiểm tra lại.
            var current=worker.get("/datasets/manifest?manifestPath="+URLEncoder.encode(c.manifestPath(),StandardCharsets.UTF_8));
            if(!current.equals(s.manifest)) throw new IllegalArgumentException("Dataset manifest changed since experiment started");
            for(int round=s.round+1;round<=c.rounds();round++) executeRound(c,s,round);
            repository.status(c.experimentId(),"COMPLETED",null);
        } catch(Exception e) {
            repository.status(c.experimentId(),"FAILED",e.getMessage());
        } finally {busy.set(false);}
    }
    private void executeRound(ExperimentConfig c,Snapshot s,int round) {
        long started=System.nanoTime();
        // Mỗi lần thử có ID riêng để artifact chưa commit không đè lên kết quả khi retry.
        var operation=UUID.randomUUID().toString();
        var eligible=new ArrayList<ClientProfile>();
        // Availability là thông tin quan sát trước khi chọn; kết quả dropout/timeout đến sau.
        for(var p:s.clients) {
            var availability=new Random(c.seed()+1000003L*round+7919L*p.clientId);
            if(!c.simulationEnabled() || availability.nextDouble()<c.availability()) {
                eligible.add(p);p.opportunityCount++;p.lastStatus="AVAILABLE";
            } else p.lastStatus="UNAVAILABLE";
        }
        Policies.ClientSelector selector=c.selection().equals("random") ? new Policies.RandomSelector() : new Policies.ResourceAwareSelector();
        var selected=selector.select(eligible,c,new Random(c.seed()+104729L*round));
        var decisions=new ArrayList<Map<String,Object>>();
        var updates=new HashMap<Integer,JsonNode>();
        var participants=new ArrayList<Map<String,Object>>();
        var jobs=new ArrayList<Map<String,Object>>();
        // Giữ nguyên checkpoint/version trong suốt vòng lặp: mọi client bắt đầu từ cùng model.
        for(var p:selected) {
            decisions.add(Map.of("clientId",p.clientId,"predictedSeconds",p.estimate(c),"estimateSource",p.estimatedSeconds==null?"prior":"history"));
            p.selectionCount++;p.lastSelectedRound=round;p.lastStatus="SELECTED";
            var request=context(c,operation);
            request.put("seed",(c.seed()+31L*round+p.clientId)%2147483647);
            request.put("roundId",round);request.put("clientId",p.clientId);
            request.put("baseModelVersion",s.modelVersion);request.put("globalModelPath",s.checkpointPath);
            request.put("training",Map.of("epochs",c.localEpochs(),"batchSize",c.batchSize(),"learningRate",c.learningRate()));
            var update=worker.post("/train",request);
            validateUpdate(update,c.experimentId(),round,s.modelVersion,p);
            updates.put(p.clientId,update);
            jobs.add(Map.of("clientId",p.clientId,"actualTrainingMs",update.path("actualTrainingMs").asDouble(),
                    "cpu",p.cpu,"ramMb",p.ramMb,"requiredRamMb",c.requiredRamMb()));
        }
        var simulation=new LinkedHashMap<String,Object>();
        simulation.put("jobs",jobs);simulation.put("seed",c.seed()+round);
        simulation.put("deadline",c.simulationEnabled()?c.deadlineSeconds():null);
        simulation.put("enabled",c.simulationEnabled());simulation.put("dropout",c.dropout());simulation.put("jitter",c.jitter());
        // Training thật chạy tuần tự, nhưng SimPy xếp các thiết bị ảo chạy song song.
        var simulated=worker.post("/simulation/round",simulation);
        var accepted=new ArrayList<JsonNode>();
        var acceptedIds=new HashSet<Integer>();
        for(var result:simulated.path("results")) {
            int id=result.path("clientId").asInt();
            var update=updates.get(id);
            if(update==null || !acceptedIds.add(id)) throw new IllegalStateException("Unknown/duplicate simulation result");
            var p=s.clients.stream().filter(client -> client.clientId==id).findFirst().orElseThrow();
            p.lastStatus=result.path("status").asText();
            p.estimatedSeconds=update.path("actualTrainingMs").asDouble()/1000/p.cpu;
            p.recentTrainingLoss=update.path("trainingLoss").asDouble();
            // Train xong trên laptop chưa đủ: update còn phải hoàn thành hợp lệ trong mô phỏng.
            boolean accept=p.lastStatus.equals("COMPLETED") && (c.deadlineSeconds()==null || !c.simulationEnabled() || result.path("completionSeconds").asDouble()<=c.deadlineSeconds());
            if(accept) {accepted.add(update);p.completionCount++;p.lastCompletedRound=round;}
            var participant=new LinkedHashMap<String,Object>();
            participant.put("clientId",id);participant.put("accepted",accept);participant.put("status",p.lastStatus);
            participant.put("training",update);participant.put("simulation",result);participant.put("tier",p.tier);
            participants.add(participant);
        }
        if(acceptedIds.size()!=selected.size()) throw new IllegalStateException("Missing simulation results");
        accepted.sort(Comparator.comparingInt(u -> u.path("clientId").asInt()));
        var losses=new ArrayList<Double>();
        double proxyMs=0;
        // FedLBW dùng proxy riêng; held-out test không tham gia tính trọng số.
        if(c.aggregation().equals("fedlbw")) for(var u:accepted) {
            var evaluation=evaluate(c,u.path("updatePath").asText(),"proxy");
            losses.add(evaluation.path("loss").asDouble());proxyMs+=evaluation.path("evaluationMs").asDouble();
        }
        var weights=List.<Double>of();
        double aggregationMs=0;
        // Không có update hợp lệ thì bỏ qua aggregation và giữ nguyên model version.
        String outcome="SKIPPED";
        if(!accepted.isEmpty()) {
            Policies.AggregationStrategy policy=c.aggregation().equals("fedavg")?new Policies.FedAvg():new Policies.FedLBW();
            weights=policy.weights(accepted.stream().map(u -> u.path("numSamples").asInt()).toList(),losses);
            var request=context(c,operation);
            request.put("roundId",round);request.put("baseModelVersion",s.modelVersion);
            request.put("updates",accepted.stream().map(u -> u.path("updatePath").asText()).toList());request.put("weights",weights);
            long aggregationStarted=System.nanoTime();
            var aggregated=worker.post("/models/aggregate",request);
            aggregationMs=(System.nanoTime()-aggregationStarted)/1e6;
            if(aggregated.path("modelVersion").asInt()!=s.modelVersion+1) throw new IllegalStateException("Invalid new model version");
            s.modelVersion++;s.checkpointPath=aggregated.path("checkpointPath").asText();outcome="COMMITTED";
        }
        var evaluation=evaluate(c,s.checkpointPath,"test");
        // Virtual time không bao gồm thời gian test phục vụ quan sát; wall time được ghi riêng.
        double virtual=simulated.path("virtualRoundSeconds").asDouble()+aggregationMs/1000+proxyMs/1000;
        s.cumulativeVirtualSeconds+=virtual;
        if(s.timeToTargetSeconds==null && evaluation.path("accuracy").asDouble()>=c.targetAccuracy()) s.timeToTargetSeconds=s.cumulativeVirtualSeconds;
        var metrics=new LinkedHashMap<String,Object>();
        metrics.put("roundId",round);metrics.put("modelVersion",s.modelVersion);metrics.put("outcome",outcome);
        metrics.put("population",s.clients.size());metrics.put("eligibleIds",eligible.stream().map(p -> p.clientId).toList());
        metrics.put("selectedIds",selected.stream().map(p -> p.clientId).toList());metrics.put("selectionDecisions",decisions);
        metrics.put("acceptedIds",accepted.stream().map(u -> u.path("clientId").asInt()).toList());
        metrics.put("participants",participants);metrics.put("weights",weights);metrics.put("proxyLosses",losses);
        metrics.put("proxyEvaluationMs",proxyMs);metrics.put("aggregationMs",aggregationMs);
        metrics.put("evaluation",evaluation);metrics.put("virtualRoundSeconds",virtual);metrics.put("cumulativeVirtualSeconds",s.cumulativeVirtualSeconds);
        metrics.put("wallClockSeconds",(System.nanoTime()-started)/1e9);metrics.put("fairness",fairness(s.clients,round));
        s.round=round;
        // Chỉ sau transaction này, snapshot mới trở thành điểm phục hồi chính thức.
        repository.commit(c.experimentId(),round,s.modelVersion,outcome,metrics,s);
    }
    public static void validateUpdate(JsonNode u,String experiment,int round,int version,ClientProfile p) {
        // Loại update cũ, sai client/thí nghiệm hoặc metrics không hữu hạn trước aggregation.
        if(!u.path("experimentId").asText().equals(experiment) || u.path("roundId").asInt(-1)!=round ||
                u.path("baseModelVersion").asInt(-1)!=version || u.path("clientId").asInt(-1)!=p.clientId ||
                u.path("numSamples").asInt()!=p.numSamples || !u.path("status").asText().equals("TRAINING_COMPLETED") ||
                !Double.isFinite(u.path("trainingLoss").asDouble(Double.NaN)) ||
                !Double.isFinite(u.path("actualTrainingMs").asDouble(Double.NaN)) || u.path("actualTrainingMs").asDouble()<0 ||
                u.path("modelSchemaHash").asText().isEmpty() || u.path("updatePath").asText().isEmpty())
            throw new IllegalArgumentException("Invalid, stale or foreign client update");
    }
    public static Map<String,Object> fairness(List<ClientProfile> clients,int round) {
        // Đo theo số lần hoàn thành và chuẩn hóa theo cơ hội có mặt của từng client.
        var counts=clients.stream().mapToDouble(p -> p.completionCount).sorted().toArray();
        var opportunityAdjusted=clients.stream().filter(p -> p.opportunityCount>0)
                .mapToDouble(p -> p.completionCount/(double)p.opportunityCount).sorted().toArray();
        return Map.of("coverage",clients.stream().filter(p -> p.completionCount>0).count()/(double)clients.size(),
                "participationGini",gini(counts),"opportunityAdjustedGini",gini(opportunityAdjusted),
                "meanStaleness",clients.stream().mapToInt(p -> round-p.lastCompletedRound).average().orElse(0),
                "maxStaleness",clients.stream().mapToInt(p -> round-p.lastCompletedRound).max().orElse(0));
    }
    private static double gini(double[] sorted) {
        double sum=Arrays.stream(sorted).sum(),weighted=0;
        for(int i=0;i<sorted.length;i++) weighted+=(2.0*(i+1)-sorted.length-1)*sorted[i];
        return sum==0?0:weighted/(sorted.length*sum);
    }
    @PreDestroy void close() {executor.shutdownNow();}
}
