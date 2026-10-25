package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import jakarta.annotation.PreDestroy;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Điều phối round đồng bộ; Java quyết định update nào được chấp nhận và model nào được commit. */
@Service
public class RoundCoordinator {
    private static final Logger log=LoggerFactory.getLogger(RoundCoordinator.class);
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
        log.info("experiment.admitted experiment={} rounds={} clients={} selectedPerRound={} selection={} aggregation={} seed={} simulation={}",
                c.experimentId(),c.rounds(),c.totalClients(),c.selectedPerRound(),c.selection(),c.aggregation(),c.seed(),c.simulationEnabled());
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
            log.info("experiment.resume experiment={} committedRound={} modelVersion={} checkpoint={}",
                    id,snapshot==null?0:snapshot.round,snapshot==null?0:snapshot.modelVersion,snapshot==null?"none":snapshot.checkpointPath);
            executor.submit(() -> run(config,snapshot));
        } catch(Exception e) {busy.set(false);throw new IllegalArgumentException(e.getMessage(),e);}
    }
    private Map<String,Object> context(ExperimentConfig c,String operation) {
        var map=new LinkedHashMap<String,Object>();
        map.put("experimentId",c.experimentId());map.put("manifestPath",c.manifestPath());
        map.put("seed",c.seed());map.put("operationId",operation);return map;
    }
    private JsonNode evaluate(ExperimentConfig c,String checkpoint,String split) {
        log.info("evaluation.started experiment={} split={} checkpoint={}",c.experimentId(),split,checkpoint);
        var result=worker.post("/models/evaluate",Map.of("manifestPath",c.manifestPath(),"checkpointPath",checkpoint,"split",split));
        log.info("evaluation.completed experiment={} split={} architecture={} loss={} accuracy={} macroF1={} worstClassRecall={} evaluationMs={}",
                c.experimentId(),split,result.path("architecture").asText(),result.path("loss").asDouble(),result.path("accuracy").asDouble(),
                result.path("macroF1").asDouble(),result.path("worstClassRecall").asDouble(),result.path("evaluationMs").asDouble());
        log.debug("evaluation.classes experiment={} split={} precision={} recall={} confusionMatrix={}",c.experimentId(),split,
                result.path("perClassPrecision"),result.path("perClassRecall"),result.path("confusionMatrix"));
        return result;
    }
    private Snapshot initialize(ExperimentConfig c) {
        log.info("experiment.initializing experiment={} manifest={}",c.experimentId(),c.manifestPath());
        var manifest=worker.get("/datasets/manifest?manifestPath="+URLEncoder.encode(c.manifestPath(),StandardCharsets.UTF_8));
        if(manifest.path("totalClients").asInt()!=c.totalClients()) throw new IllegalArgumentException("Manifest totalClients mismatch");
        Snapshot s=new Snapshot();s.manifest=manifest;
        for(var entry:manifest.path("clients")) s.clients.add(new ClientProfile(entry.path("clientId").asInt(),entry.path("numSamples").asInt(),c.totalClients(),c.resourceProfile()));
        var initialized=worker.post("/models/initialize",context(c,UUID.randomUUID().toString()));
        s.checkpointPath=initialized.path("checkpointPath").asText();
        log.info("model.initialized experiment={} architecture={} checkpoint={}",c.experimentId(),initialized.path("architecture").asText(),s.checkpointPath);
        s.initialEvaluation=evaluate(c,s.checkpointPath,"test");
        if(s.initialEvaluation.path("accuracy").asDouble()>=c.targetAccuracy()) s.timeToTargetSeconds=0.0;
        try {
            var process=new ProcessBuilder("git","rev-parse","HEAD").start();
            s.gitCommit=new String(process.getInputStream().readAllBytes(),StandardCharsets.UTF_8).trim();
            var status=new ProcessBuilder("git","status","--porcelain").start();
            s.gitDirty=status.getInputStream().readAllBytes().length>0;
        }catch(Exception e) {s.gitCommit="unknown";}
        repository.snapshot(c.experimentId(),s);
        log.info("experiment.initialized experiment={} clients={} gitCommit={} gitDirty={}",c.experimentId(),s.clients.size(),s.gitCommit,s.gitDirty);
        return s;
    }
    private void run(ExperimentConfig c,Snapshot s) {
        int lastCommittedRound=s==null?0:s.round;
        MDC.put("experimentId",c.experimentId());
        MDC.put("roundId",Integer.toString(lastCommittedRound));
        try {
            if(s==null) s=initialize(c);
            // Khi worker nạp lại dataset sau restart, hash của các file được kiểm tra lại.
            var current=worker.get("/datasets/manifest?manifestPath="+URLEncoder.encode(c.manifestPath(),StandardCharsets.UTF_8));
            if(!current.equals(s.manifest)) throw new IllegalArgumentException("Dataset manifest changed since experiment started");
            for(int round=s.round+1;round<=c.rounds();round++) {
                executeRound(c,s,round);
                lastCommittedRound=round;
            }
            repository.status(c.experimentId(),"COMPLETED",null);
            log.info("experiment.completed experiment={} rounds={} modelVersion={} virtualSeconds={} timeToTargetSeconds={} checkpoint={} resultUrl=/experiments/{}/result",
                    c.experimentId(),s.round,s.modelVersion,s.cumulativeVirtualSeconds,s.timeToTargetSeconds,s.checkpointPath,c.experimentId());
        } catch(Exception e) {
            log.error("experiment.failed experiment={} lastCommittedRound={} error={}",c.experimentId(),lastCommittedRound,e.getMessage(),e);
            repository.status(c.experimentId(),"FAILED",e.getMessage());
        } finally {
            MDC.remove("experimentId");MDC.remove("roundId");MDC.remove("operationId");
            busy.set(false);
        }
    }
    private void executeRound(ExperimentConfig c,Snapshot s,int round) {
        long started=System.nanoTime();
        // Mỗi lần thử có ID riêng để artifact chưa commit không đè lên kết quả khi retry.
        var operation=UUID.randomUUID().toString();
        MDC.put("roundId",Integer.toString(round));MDC.put("operationId",operation);
        log.info("round.started experiment={} round={}/{} modelVersion={} operation={}",c.experimentId(),round,c.rounds(),s.modelVersion,operation);
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
        log.info("selection.completed experiment={} round={} eligible={}/{} selected={} policy={}",
                c.experimentId(),round,eligible.size(),s.clients.size(),selected.stream().map(p -> p.clientId).toList(),c.selection());
        if(selected.isEmpty()) log.warn("selection.empty experiment={} round={} eligible={} policy={}",c.experimentId(),round,eligible.size(),c.selection());
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
            log.info("training.dispatched experiment={} round={} client={} samples={} tier={} predictedSeconds={} epochs={} batchSize={} learningRate={} operation={}",
                    c.experimentId(),round,p.clientId,p.numSamples,p.tier,p.estimate(c),c.localEpochs(),c.batchSize(),c.learningRate(),operation);
            var update=worker.post("/train",request);
            validateUpdate(update,c.experimentId(),round,s.modelVersion,p);
            log.info("training.completed experiment={} round={} client={} loss={} trainingMs={} workerRssMb={} update={}",c.experimentId(),round,p.clientId,
                    update.path("trainingLoss").asDouble(),update.path("actualTrainingMs").asDouble(),update.path("workerRssMb").asDouble(),update.path("updatePath").asText());
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
        log.info("simulation.completed experiment={} round={} enabled={} jobs={} deadlineSeconds={} virtualRoundSeconds={}",
                c.experimentId(),round,c.simulationEnabled(),jobs.size(),c.deadlineSeconds(),simulated.path("virtualRoundSeconds").asDouble());
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
            if(accept) log.info("update.accepted experiment={} round={} client={} status={} completionSeconds={}",
                    c.experimentId(),round,id,p.lastStatus,result.path("completionSeconds").asDouble());
            else log.warn("update.rejected experiment={} round={} client={} status={} completionSeconds={} deadlineSeconds={}",
                    c.experimentId(),round,id,p.lastStatus,result.path("completionSeconds").asDouble(),c.deadlineSeconds());
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
            log.info("aggregation.started experiment={} round={} method={} acceptedClients={}",c.experimentId(),round,c.aggregation(),accepted.stream().map(u -> u.path("clientId").asInt()).toList());
            weights=worker.aggregationWeights(c.aggregation(),accepted.stream().map(u -> u.path("numSamples").asInt()).toList(),losses);
            log.info("aggregation.weights experiment={} round={} weights={} proxyLosses={}",c.experimentId(),round,weights,losses);
            var request=context(c,operation);
            request.put("roundId",round);request.put("baseModelVersion",s.modelVersion);
            request.put("updates",accepted.stream().map(u -> u.path("updatePath").asText()).toList());request.put("weights",weights);
            long aggregationStarted=System.nanoTime();
            var aggregated=worker.post("/models/aggregate",request);
            aggregationMs=(System.nanoTime()-aggregationStarted)/1e6;
            if(aggregated.path("modelVersion").asInt()!=s.modelVersion+1) throw new IllegalStateException("Invalid new model version");
            s.modelVersion++;s.checkpointPath=aggregated.path("checkpointPath").asText();outcome="COMMITTED";
            log.info("aggregation.completed experiment={} round={} modelVersion={} aggregationMs={} checkpoint={}",c.experimentId(),round,s.modelVersion,aggregationMs,s.checkpointPath);
        } else log.warn("aggregation.skipped experiment={} round={} reason=no_accepted_updates modelVersion={}",c.experimentId(),round,s.modelVersion);
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
        var fairnessMetrics=fairness(s.clients,round);
        metrics.put("wallClockSeconds",(System.nanoTime()-started)/1e9);metrics.put("fairness",fairnessMetrics);
        s.round=round;
        // Chỉ sau transaction này, snapshot mới trở thành điểm phục hồi chính thức.
        repository.commit(c.experimentId(),round,s.modelVersion,outcome,metrics,s);
        log.info("round.committed experiment={} round={}/{} outcome={} accepted={}/{} modelVersion={} accuracy={} macroF1={} loss={} virtualSeconds={} wallSeconds={} coverage={}",
                c.experimentId(),round,c.rounds(),outcome,accepted.size(),selected.size(),s.modelVersion,evaluation.path("accuracy").asDouble(),
                evaluation.path("macroF1").asDouble(),evaluation.path("loss").asDouble(),virtual,metrics.get("wallClockSeconds"),
                fairnessMetrics.get("coverage"));
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
