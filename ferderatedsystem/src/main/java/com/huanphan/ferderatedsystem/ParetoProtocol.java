package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.nio.file.*;
import java.util.*;
import static com.huanphan.ferderatedsystem.ControlledExperiments.*;

/** Predeclared policies and historical validation evidence, never held-out scores. */
final class ParetoProtocol {
    static final List<Row> ROWS=List.of(Row.P1,Row.P2,Row.P3,Row.P4);
    static final List<Double> LAMBDAS=List.of(.65,.675,.725,.3);
    static final List<String> INHERITED=List.of("baseConfig","heterogeneousScenario","fuzzySelection","timing","splitSeed",
            "validation","evaluation","stabilityWindow","accuracyTargets","partitionPattern");
    private ParetoProtocol() {}
    static void validate(JsonNode p) {
        if((!p.path("smoke").asBoolean()&&!p.path("dataset").asText().equals("covertype"))||p.path("alpha").asDouble()!=.5)
            throw new IllegalArgumentException("Held-out protocol requires Covertype Dirichlet alpha=.5");
        if(!p.path("analysisType").asText().equals("PARETO_COMPARISON")||!p.path("requireAudit").asBoolean())
            throw new IllegalArgumentException("Pareto comparison requires its own analysis type and E0 gate");
        var policies=p.path("policies");if(!policies.isArray()||policies.size()!=4) throw new IllegalArgumentException("Exactly P1-P4 must be locked");
        for(int i=0;i<4;i++) {
            var policy=policies.get(i);
            if(!policy.path("id").asText().equals(ROWS.get(i).name())||!policy.path("selection").asText().equals(ROWS.get(i).selection)||
                    !policy.path("lambda").isNumber()||policy.path("lambda").asDouble()!=LAMBDAS.get(i))
                throw new IllegalArgumentException("Locked P1-P4 policies changed");
        }
        if(!p.path("smoke").asBoolean()&&(!ResearchExperiments.seeds(p.path("evaluation").path("partitionSeeds")).equals(List.of(2001L,2002L,2003L))||
                !ResearchExperiments.seeds(p.path("evaluation").path("seeds")).equals(List.of(42L,43L,44L,45L,46L))))
            throw new IllegalArgumentException("Held-out protocol requires partitions2001-2003 and training/scenario seeds42-46");
        for(String key:List.of("reportPath","lockPath","reportSha256","lockSha256"))
            if(p.path("phaseA").path(key).asText().isBlank()) throw new IllegalArgumentException("Pinned Phase A evidence required: "+key);
        if(!p.path("largeAccuracyDropPp").isNumber()||!Double.isFinite(p.path("largeAccuracyDropPp").asDouble())||p.path("largeAccuracyDropPp").asDouble()<0)
            throw new IllegalArgumentException("Predeclare a nonnegative large-drop diagnostic threshold");
    }
    static ObjectNode phaseAEvidence(Path root,JsonNode p,ObjectMapper json) throws Exception {
        var reference=p.path("phaseA");Path reportPath=inside(root,reference.path("reportPath").asText()),lockPath=inside(root,reference.path("lockPath").asText());
        if(!ResearchProvenance.hash(reportPath).equals(reference.path("reportSha256").asText())||!ResearchProvenance.hash(lockPath).equals(reference.path("lockSha256").asText()))
            throw new IllegalStateException("Phase A evidence hash changed; refusing to reselect policies");
        var report=json.readTree(Files.readString(reportPath));var lock=json.readTree(Files.readString(lockPath));
        var unsigned=(ObjectNode)lock.deepCopy();unsigned.remove("lockHash");
        if(!lock.path("lockHash").asText().equals(ResearchProvenance.hash(unsigned))||!lock.path("protocolHash").asText().equals(ResearchProvenance.hash(lock.path("protocol")))||
                !lock.path("validationReportHash").asText().equals(ResearchProvenance.hash(reportPath))||!lock.path("adaptiveHyperparameters").equals(lock.path("protocol").path("fuzzySelection")))
            throw new IllegalStateException("Phase A lock/report integrity mismatch");
        if(!report.path("complete").asBoolean()||!report.path("phase").asText().equals("validation")||
                !report.path("fairnessMatching").path("status").asText().equals("NO_MATCH")||!lock.path("status").asText().equals("NO_MATCH"))
            throw new IllegalStateException("This protocol requires completed NO_MATCH validation evidence");
        if(report.path("smoke").asBoolean()!=p.path("smoke").asBoolean()) throw new IllegalStateException("Cannot mix synthetic smoke and research evidence");
        for(String field:INHERITED) if(!p.path(field).equals(lock.path("protocol").path(field)))
            throw new IllegalStateException("Phase A training/scenario/hyperparameters changed: "+field);
        var inherited=lock.path("protocol");var partitions=ResearchExperiments.seeds(inherited.path("validation").path("partitionSeeds"));
        var seeds=ResearchExperiments.seeds(inherited.path("validation").path("seeds"));
        Set<String> expected=new HashSet<>(),seen=new HashSet<>();Map<String,List<String>> paired=new HashMap<>();
        ObjectNode sharedPools=null;
        for(long partition:partitions) for(long seed:seeds) for(int row=1;row<=7;row++) expected.add(partition+":"+seed+":M"+row);
        for(var result:report.path("results")) {
            String policy=result.path("policy").asText();String cell=result.path("partitionSeed").asText()+":"+result.path("trainingScenarioSeed").asText();
            if(!seen.add(cell+":"+policy)||!result.path("finalEvaluationSplit").asText().equals("proxy")||
                    !result.path("provenance").path("runtimeIdentity").equals(lock.path("runtimeIdentity"))||
                    !result.path("provenance").path("protocol").equals(inherited)||!policy.matches("M[1-7]"))
                throw new IllegalStateException("Invalid or unpaired Phase A evidence");
            double lambda=policy.equals("M7")?.3:inherited.path("fixedLambdas").get(Integer.parseInt(policy.substring(1))-1).asDouble();
            if(!result.path("configuredLambda").isNumber()||result.path("configuredLambda").asDouble()!=lambda)
                throw new IllegalStateException("Phase A policy coefficient differs from its protocol");
            List<String> hashes=new ArrayList<>();for(String key:List.of("initialModelHash","scenarioTraceHash","partitionManifestHash")) {
                String hash=result.path(key).asText();if(!hash.matches("[a-f0-9]{64}")) throw new IllegalStateException("Missing Phase A hash: "+key);hashes.add(hash);
            }
            if(!paired.computeIfAbsent(cell,ignored->hashes).equals(hashes)) throw new IllegalStateException("Phase A initial/partition/scenario pairs differ");
            String id=result.path("experimentId").asText();if(!id.matches("[A-Za-z0-9_-]{1,60}")) throw new IllegalStateException("Invalid Phase A experiment identity");
            var exported=json.readTree(Files.readString(reportPath.getParent().resolve("runs").resolve(id).resolve("experiment.json")));
            var manifest=exported.path("snapshot").path("manifest");
            if(!ResearchProvenance.hash(manifest).equals(result.path("partitionManifestHash").asText())||manifest.path("alpha").asDouble()!=.5||
                    !manifest.path("strategy").asText().equals("dirichlet_label_skew")||!manifest.path("dataset").asText().equals(p.path("smoke").asBoolean()?"synthetic":"covertype"))
                throw new IllegalStateException("Phase A exported partition manifest mismatch");
            var pools=json.createObjectNode();for(String file:List.of("features.npy","labels.npy","splits.npz")) {
                var hash=manifest.path("hashes").path(file);if(!hash.asText().matches("[a-f0-9]{64}")) throw new IllegalStateException("Phase A pool hashes missing");pools.set(file,hash);
            }
            if(sharedPools==null) sharedPools=pools;else if(!sharedPools.equals(pools)) throw new IllegalStateException("Phase A pool/scaler inputs differ between partitions");
        }
        if(!seen.equals(expected)) throw new IllegalStateException("Phase A matrix is incomplete or includes held-out partitions");
        var evidence=json.createObjectNode().put("status","NO_MATCH").put("reportSha256",ResearchProvenance.hash(reportPath)).put("lockSha256",ResearchProvenance.hash(lockPath))
                .put("validationRuns",seen.size()).put("policiesChosenFromValidationOnly",true);
        evidence.set("sharedPools",sharedPools);evidence.set("historicalRuntimeIdentity",lock.path("runtimeIdentity"));return evidence;
    }
    static Path inside(Path root,String value) {
        Path path=root.resolve(value).normalize();if(!path.startsWith(root)) throw new IllegalArgumentException("Evidence path outside workspace");return path;
    }
    static ObjectNode auditReadiness(Path root,JsonNode p,JsonNode runtime,ObjectMapper json) {
        var out=json.createObjectNode().put("ready",false).put("determinismClaimed",false);out.set("currentRuntimeIdentity",runtime);
        try {
            Path path=inside(root,p.path("auditReportPath").asText());
            if(!Files.exists(path)) return out.put("reason","E0_MISSING: run E0 on this frozen build before the held-out experiment");
            var audit=json.readTree(Files.readString(path));out.put("auditReportSha256",ResearchProvenance.hash(path));
            if(!audit.path("complete").asBoolean()||!audit.path("deterministicReplayPassed").asBoolean()||!audit.path("savedStateReplayPassed").asBoolean()||
                    !audit.path("conditionalTrainingPassed").asBoolean()||audit.path("smoke").asBoolean()!=p.path("smoke").asBoolean())
                return out.put("reason","E0_NOT_TRUSTWORTHY: incomplete, failed or incompatible audit");
            if(!audit.path("runtimeIdentity").equals(runtime)) return out.put("reason","E0_RUNTIME_MISMATCH: historical E0 does not certify the current Java/Python build");
            if(audit.path("completedRuns").asInt()<12||audit.path("completedRuns").asInt()!=audit.path("expectedRuns").asInt()||
                    audit.path("runs").size()!=audit.path("completedRuns").asInt()||audit.path("repeatSummaryByGroup").size()!=4)
                return out.put("reason","E0_INSUFFICIENT_REPEAT_EVIDENCE");
            for(var run:audit.path("runs")) if(!run.path("savedStateAndTimingReplayPassed").asBoolean()) return out.put("reason","E0_SAVED_STATE_REPLAY_FAILED");
            for(var group:audit.path("repeatSummaryByGroup")) if(group.path("metrics").path("accuracy").path("n").asInt()<3)
                return out.put("reason","E0_REQUIRES_THREE_REPEATS");
            var audited=audit.path("runs").get(0).path("config").path("provenance").path("protocol");
            for(String key:List.of("baseConfig","heterogeneousScenario","fuzzySelection","timing")) if(!audited.path(key).equals(p.path(key)))
                return out.put("reason","E0_PROTOCOL_MISMATCH: "+key);
            return out.put("ready",true).put("determinismClaimed",true).put("reason","E0 passed for this CPU/runtime and declared protocol; physical overhead remains measured");
        } catch(Exception e) {return out.put("reason","E0_UNREADABLE: "+e.getMessage());}
    }
}
