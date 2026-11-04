package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import jakarta.validation.Validator;
import org.springframework.core.env.Environment;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import static com.huanphan.ferderatedsystem.ControlledExperiments.*;

/** Small orchestration layer over the existing controlled execution/export path. */
final class ResearchExperiments {
    private final ControlledExperiments controlled;
    private final PythonMLClient worker;
    private final ObjectMapper json;
    private final Environment env;
    private final Validator validator;
    ResearchExperiments(ControlledExperiments controlled,PythonMLClient worker,ObjectMapper json,Environment env,Validator validator) {
        this.controlled=controlled;this.worker=worker;this.json=json;this.env=env;this.validator=validator;
    }
    private record Setup(Path root,Path output,ObjectNode protocol,ObjectNode provenance) {}
    private Setup setup(boolean audit) throws Exception {
        return setup(audit,false);
    }
    private Setup setup(boolean audit,boolean pareto) throws Exception {
        String workspace=env.getProperty("minifls.launch.workspace","");
        Path root=workspace.isBlank()?Path.of("").toAbsolutePath().normalize():Path.of(workspace).toAbsolutePath().normalize();
        if(workspace.isBlank()&&!Files.isDirectory(root.resolve("configurations"))) root=root.getParent();
        String source=pareto?env.getProperty("minifls.pareto.config","configurations/pareto-tradeoff.json"):
                env.getProperty(audit?"minifls.audit.config":"minifls.matched.config",audit?"configurations/reproducibility-audit.json":"configurations/fairness-matched-lambda.json");
        var protocol=(ObjectNode)json.readTree(Files.readString(root.resolve(source)));
        validate(protocol,audit);
        if(pareto) ParetoProtocol.validate(protocol);
        var provenance=ResearchProvenance.capture(root,worker,json);
        String outputPath=env.getProperty(audit?"minifls.audit.output":"minifls.matched.output","");
        if(outputPath.isBlank()) outputPath=env.getProperty("minifls.research.output",env.getProperty("MINIFLS_RESEARCH_OUTPUT",""));
        if(outputPath.isBlank()) outputPath=audit?"artifacts/research/reproducibility-audit":"artifacts/research/fairness-matched";
        if(pareto) outputPath=env.getProperty("minifls.pareto.output","artifacts/research/pareto-tradeoff");
        Path output=root.resolve(outputPath).normalize();
        if(!output.startsWith(root)) throw new IllegalArgumentException("Research output must stay in workspace");
        Files.createDirectories(output);
        var identity=json.createObjectNode();identity.set("protocol",protocol);identity.set("runtimeIdentity",provenance.path("runtimeIdentity"));
        ResearchProvenance.save(output.resolve("batch-provenance.json"),identity,json,true);
        var setup=new Setup(root,output,protocol,provenance);
        // Validate every policy before preparing partitions or spending training compute.
        long firstSeed=seeds(audit?protocol.path("seeds"):protocol.path("validation").path("seeds")).get(0);
        for(var row:pareto?ParetoProtocol.ROWS:audit?List.of(Row.L3,Row.L5):List.of(Row.M1,Row.M2,Row.M3,Row.M4,Row.M5,Row.M6,Row.M7))
            config(setup,row,firstSeed,protocol.path("nonIidManifestPath").asText(),pareto?"pareto":audit?"audit":"validation","deterministic",0);
        return setup;
    }
    static List<Long> seeds(JsonNode values) {
        if(!values.isArray()||values.isEmpty()) throw new IllegalArgumentException("Nonempty seed list required");
        List<Long> out=new ArrayList<>();
        for(var v:values) {
            if(!v.isIntegralNumber()||!v.canConvertToLong()||v.asLong()<0||v.asLong()>1_000_000_000)
                throw new IllegalArgumentException("Invalid seed: "+v);
            if(out.contains(v.asLong())) throw new IllegalArgumentException("Duplicate seed");out.add(v.asLong());
        }
        return out;
    }
    static void validate(JsonNode p,boolean audit) {
        var base=p.path("baseConfig");boolean smoke=p.path("smoke").asBoolean(false);
        if(!base.isObject()||!p.path("fuzzySelection").isObject()) throw new IllegalArgumentException("Reuse lambda-ablation baseConfig/fuzzySelection schema");
        for(String field:List.of("rounds","totalClients","selectedPerRound","localEpochs","batchSize"))
            if(!base.path(field).isIntegralNumber()) throw new IllegalArgumentException("Integer required: "+field);
        if(base.path("totalClients").asInt()!=100||base.path("selectedPerRound").asInt()!=5||(!smoke&&base.path("rounds").asInt()!=70))
            throw new IllegalArgumentException("Research protocol requires 100 clients, K=5, 70 rounds (or explicit smoke)");
        if(base.path("rounds").asInt()<2||!"fedavg".equals(base.path("aggregation").asText())||base.path("localEpochs").asInt()!=1||
                base.path("batchSize").asInt()!=32||base.path("learningRate").asDouble()!=.01||!base.path("simulationEnabled").asBoolean())
            throw new IllegalArgumentException("Controlled FedAvg training settings changed");
        if(!"heterogeneous".equals(p.path("heterogeneousScenario").path("resourceProfile").asText())) throw new IllegalArgumentException("Heterogeneous resources required");
        var fuzzy=p.path("fuzzySelection");var weights=fuzzy.path("weights");
        if(weights.size()!=3||weights.path("estimatedTime").asDouble()!=.4||weights.path("reliability").asDouble()!=.35||weights.path("learningUtility").asDouble()!=.25||
                !"credit_score".equals(fuzzy.path("fairness").path("mode").asText())||fuzzy.path("fairness").path("lambda").asDouble()!=.3)
            throw new IllegalArgumentException("Keep existing criteria weights, credit scheduler and adaptive initial lambda=.3");
        if(!p.path("timing").isObject()) throw new IllegalArgumentException("Explicit research timing config required");
        if(audit) {
            if(seeds(p.path("seeds")).size()!=1) throw new IllegalArgumentException("E0 requires one shared training/scenario seed per audit protocol");
            if(!p.path("audit").path("repetitions").isIntegralNumber()||p.path("audit").path("repetitions").asInt()<3)
                throw new IllegalArgumentException("E0 requires >=3 repetitions per configuration");
            var modes=p.path("audit").path("durationModes");Set<String> seen=new HashSet<>();modes.forEach(v->seen.add(v.asText()));
            if(modes.size()!=2||!seen.equals(Set.of("deterministic","measured"))) throw new IllegalArgumentException("Audit both duration modes separately");
        } else {
            if(!"deterministic".equals(p.path("timing").path("mode").asText())) throw new IllegalArgumentException("Main E1 protocol uses deterministic duration");
            var a=seeds(p.path("validation").path("partitionSeeds"));var b=seeds(p.path("evaluation").path("partitionSeeds"));
            if(a.stream().anyMatch(b::contains)) throw new IllegalArgumentException("Validation/held-out partitions overlap");
            for(String phase:List.of("validation","evaluation")) seeds(p.path(phase).path("seeds"));
            var fixed=p.path("fixedLambdas");double last=-1;
            if(!fixed.isArray()||fixed.size()!=6) throw new IllegalArgumentException("M1-M6 require six fixed lambdas");
            for(var value:fixed) {double d=value.asDouble(Double.NaN);if(!value.isNumber()||!Double.isFinite(d)||d<=last||d<0||d>1) throw new IllegalArgumentException("Fixed lambdas must be finite, ascending and in [0,1]");last=d;}
            if(!p.path("splitSeed").isIntegralNumber()||p.path("splitSeed").asLong()<0) throw new IllegalArgumentException("Explicit splitSeed required");
            if(!p.path("stabilityWindow").isIntegralNumber()||p.path("stabilityWindow").asInt()<2) throw new IllegalArgumentException("Tail window >=2 required");
            if(!p.path("partitionPattern").asText().contains("{partitionSeed}")) throw new IllegalArgumentException("Separate partition paths required");
            for(String key:FairnessMatchedReport.TOLERANCES) {
                var value=p.path("matching").path(key);
                if(!value.isNumber()||!Double.isFinite(value.asDouble())||value.asDouble()<0) throw new IllegalArgumentException("Invalid fairness tolerance: "+key);
            }
        }
    }
    private ExperimentConfig config(Setup s,Row row,long seed,String manifest,String phase,String mode,int replicate) throws Exception {
        ObjectNode node=((ObjectNode)s.protocol().path("baseConfig")).deepCopy();
        node.setAll((ObjectNode)s.protocol().path("heterogeneousScenario"));
        node.set("fuzzySelection",s.protocol().path("fuzzySelection").deepCopy());
        node.set("timing",s.protocol().path("timing").deepCopy());((ObjectNode)node.path("timing")).put("mode",mode);
        node.put("manifestPath",manifest).put("seed",seed).put("architecture","mlp_54_256_128_7").put("selection",row.selection);
        if(row==Row.L3) ((ObjectNode)node.path("fuzzySelection").path("fairness")).put("lambda",.7);
        if(row.name().startsWith("M")&&row!=Row.M7)
            ((ObjectNode)node.path("fuzzySelection").path("fairness")).put("lambda",s.protocol().path("fixedLambdas").get(row.ordinal()-Row.M1.ordinal()).asDouble());
        if(row.name().startsWith("P"))
            ((ObjectNode)node.path("fuzzySelection").path("fairness")).put("lambda",s.protocol().path("policies").get(row.ordinal()-Row.P1.ordinal()).path("lambda").asDouble());
        node.put("evaluationSplit","proxy");
        if(phase.equals("evaluation")||phase.equals("pareto")) node.put("finalEvaluationSplit","test");
        node.put("experimentId","research-template");
        var c=json.treeToValue(node,ExperimentConfig.class);c.check();
        if(!validator.validate(c).isEmpty()) throw new IllegalArgumentException("Invalid research configuration");
        var normalized=(ObjectNode)json.valueToTree(c);normalized.remove(List.of("experimentId","scenarioTracePath","provenance"));
        String configHash=ResearchProvenance.hash(normalized);
        var identity=json.createObjectNode().put("phase",phase).put("replicate",replicate).put("configHash",configHash);
        if(row.name().startsWith("P")) identity.put("paretoProtocolHash",ResearchProvenance.hash(s.protocol()));
        identity.set("runtime",s.provenance().path("runtimeIdentity"));
        String id="research-"+ResearchProvenance.hash(identity).substring(0,40);
        node.put("experimentId",id);
        Path trace=s.output().resolve("traces/s"+seed+".json");
        var document=ScenarioTrace.generate(c,json);ResearchProvenance.save(trace,document,json,true);
        node.put("scenarioTracePath",s.root().relativize(trace).toString().replace('\\','/'));
        var provenance=s.provenance().deepCopy();provenance.put("configHash",configHash).put("runIdentity",id)
                .put("buildConfigHash",ResearchProvenance.hash(identity)).put("scenarioTraceHash",ResearchProvenance.hash(trace));
        provenance.put("phase",phase).put("replicate",replicate+1);
        provenance.set("protocol",s.protocol());node.set("provenance",provenance);
        return json.treeToValue(node,ExperimentConfig.class);
    }
    private RunResult run(Setup s,Row row,long seed,String manifest,String phase,String mode,int replicate) throws Exception {
        if(Files.exists(s.output().resolve("STOP"))) throw new IllegalStateException("Research STOP file present");
        var c=config(s,row,seed,manifest,phase,mode,replicate);
        return controlled.runPrepared(row,c,s.output().resolve(phase).resolve("runs").resolve(c.experimentId()));
    }
    Path audit() throws Exception {
        Setup s=setup(true);Map<String,List<RunResult>> groups=new LinkedHashMap<>();Exception failure=null;
        try {
            for(var mode:s.protocol().path("audit").path("durationModes")) for(long seed:seeds(s.protocol().path("seeds"))) {
                for(int r=0;r<s.protocol().path("audit").path("repetitions").asInt();r++) for(var row:List.of(Row.L3,Row.L5)) {
                    var completed=run(s,row,seed,s.protocol().path("nonIidManifestPath").asText(),"audit",mode.asText(),r);
                    var group=groups.computeIfAbsent(mode.asText()+":"+seed+":"+row,ignored->new ArrayList<>());
                    group.add(completed);
                }
            }
        } catch(Exception e) {failure=e;}
        var report=ReproducibilityAuditReport.create(groups,s.protocol(),json,failure);
        ResearchProvenance.save(s.output().resolve("reproducibility-audit.json"),report,json,false);
        ResearchProvenance.saveText(s.output().resolve("reproducibility-audit.md"),ReproducibilityAuditReport.markdown(report));
        if(failure!=null) throw new IllegalStateException("Incomplete E0; see reproducibility-audit.json",failure);
        return s.output().resolve("reproducibility-audit.md");
    }
    private void auditGate(Setup s) throws Exception {
        if(!s.protocol().path("requireAudit").asBoolean(true)) {
            if(!s.protocol().path("smoke").asBoolean()) throw new IllegalArgumentException("Only smoke may bypass E0 gate");return;
        }
        var report=json.readTree(Files.readString(s.root().resolve(s.protocol().path("auditReportPath").asText())));
        if(!report.path("complete").asBoolean()||!report.path("deterministicReplayPassed").asBoolean()||report.path("smoke").asBoolean())
            throw new IllegalStateException("Research E0 deterministic replay must pass before E1");
        if(!report.path("runtimeIdentity").equals(s.provenance().path("runtimeIdentity"))) throw new IllegalStateException("E0 runtime differs from E1 build/worker");
    }
    Path validation() throws Exception {
        Setup s=setup(false);auditGate(s);
        var runs=matrix(s,"validation",List.of(Row.M1,Row.M2,Row.M3,Row.M4,Row.M5,Row.M6,Row.M7));
        var match=FairnessMatchedReport.match(runs,s.protocol().path("matching"),json);
        var lock=json.createObjectNode().put("status",match.path("status").asText());
        lock.set("matching",match);lock.set("protocol",s.protocol());lock.set("runtimeIdentity",s.provenance().path("runtimeIdentity"));
        lock.set("adaptiveHyperparameters",s.protocol().path("fuzzySelection"));
        lock.put("protocolHash",ResearchProvenance.hash(s.protocol()));
        lock.put("validationRunIdentityHash",ResearchProvenance.hash(json.valueToTree(runs.stream().map(r->r.config().experimentId()).toList())));
        lock.put("validationReportHash",ResearchProvenance.hash(s.output().resolve("validation/fairness-matched-results.json")));
        lock.put("lockHash",ResearchProvenance.hash(lock));
        ResearchProvenance.save(s.output().resolve("policy-lock.json"),lock,json,true);
        return s.output().resolve("validation/fairness-matched-summary.md");
    }
    Path evaluation() throws Exception {
        Setup s=setup(false);auditGate(s);
        var lock=json.readTree(Files.readString(s.output().resolve("policy-lock.json")));
        validateLock(lock,s.protocol(),s.provenance().path("runtimeIdentity"));
        Path validation=s.output().resolve("validation/fairness-matched-results.json");
        if(!lock.path("validationReportHash").asText().equals(ResearchProvenance.hash(validation))||
                !lock.path("matching").equals(json.readTree(Files.readString(validation)).path("fairnessMatching")))
            throw new IllegalStateException("Phase A evidence differs from policy lock");
        var row=Row.valueOf(lock.path("matching").path("selectedPolicy").asText());
        var runs=matrix(s,"evaluation",List.of(row,Row.M7));
        ResearchProvenance.save(s.output().resolve("evaluation/heldout-fairness-check.json"),FairnessMatchedReport.match(runs,s.protocol().path("matching"),json),json,false);
        return s.output().resolve("evaluation/fairness-matched-summary.md");
    }
    Path pareto(boolean preflightOnly) throws Exception {
        Setup s=setup(false,true);
        var evidence=ParetoProtocol.phaseAEvidence(s.root(),s.protocol(),json);
        s.provenance().set("paretoSourcePools",evidence.path("sharedPools"));
        var manifest=json.createObjectNode().put("analysisType","PARETO_COMPARISON").put("phaseAStatus","NO_MATCH");
        manifest.set("protocol",s.protocol());manifest.set("runtimeIdentity",s.provenance().path("runtimeIdentity"));manifest.set("phaseAEvidence",evidence);
        manifest.put("policiesSelectedBeforeHeldout",true).put("usesHeldoutResultsForTuning",false);
        ResearchProvenance.save(s.output().resolve("pareto-tradeoff-config.json"),manifest,json,true);
        var readiness=ParetoProtocol.auditReadiness(s.root(),s.protocol(),s.provenance().path("runtimeIdentity"),json);
        ResearchProvenance.save(s.output().resolve("pareto-preflight.json"),readiness,json,false);
        if(!readiness.path("ready").asBoolean()||preflightOnly) {
            ResearchProvenance.saveText(s.output().resolve("pareto-preflight.md"),"# Held-out Pareto preflight\n\n"+readiness.toPrettyString()+"\n\nNo training was started.\n");
            if(!readiness.path("ready").asBoolean()&&!preflightOnly) throw new IllegalStateException("BLOCKED: "+readiness.path("reason").asText()+"; see "+s.output().resolve("pareto-preflight.json"));
            return s.output().resolve("pareto-preflight.json");
        }
        var execution=json.createObjectNode();execution.put("policyLockHash",ResearchProvenance.hash(s.output().resolve("pareto-tradeoff-config.json")));
        execution.set("auditReportSha256",readiness.path("auditReportSha256"));execution.set("runtimeIdentity",s.provenance().path("runtimeIdentity"));
        ResearchProvenance.save(s.output().resolve("pareto-execution-manifest.json"),execution,json,true);
        s.provenance().set("paretoExecution",execution);
        matrix(s,"pareto",ParetoProtocol.ROWS);
        ResearchProvenance.save(s.output().resolve("pareto-completion.json"),json.createObjectNode().put("status","COMPLETED")
                .put("resultsSha256",ResearchProvenance.hash(s.output().resolve("pareto-tradeoff-results.json"))),json,false);
        return s.output().resolve("pareto-tradeoff-summary.md");
    }
    static void validateLock(JsonNode lock,JsonNode protocol,JsonNode runtime) throws Exception {
        var content=(ObjectNode)lock.deepCopy();content.remove("lockHash");
        if(!lock.path("lockHash").asText().equals(ResearchProvenance.hash(content))) throw new IllegalStateException("Policy lock content hash differs");
        if(!"MATCHED".equals(lock.path("status").asText())) throw new IllegalStateException("No fairness-matched policy was locked; held-out evaluation is blocked");
        if(!lock.path("protocol").equals(protocol)||!lock.path("protocolHash").asText().equals(ResearchProvenance.hash(protocol))||
                !lock.path("adaptiveHyperparameters").equals(protocol.path("fuzzySelection"))||!lock.path("runtimeIdentity").equals(runtime))
            throw new IllegalStateException("Locked protocol, adaptive settings or runtime changed");
        String row=lock.path("matching").path("selectedPolicy").asText();
        if(!row.matches("M[1-6]")) throw new IllegalStateException("Invalid locked fixed policy");
        if(lock.path("matching").path("selectedLambda").asDouble()!=protocol.path("fixedLambdas").get(Integer.parseInt(row.substring(1))-1).asDouble())
            throw new IllegalStateException("Locked policy/lambda mismatch");
    }
    private List<RunResult> matrix(Setup s,String phase,List<Row> policies) throws Exception {
        List<RunResult> runs=new ArrayList<>();Exception failure=null;
        boolean pareto=phase.equals("pareto");var settings=s.protocol().path(pareto?"evaluation":phase);
        try {
            for(long partition:seeds(settings.path("partitionSeeds"))) {
                String path=s.protocol().path("partitionPattern").asText().replace("{partitionSeed}",Long.toString(partition));
                var manifest=worker.post("/datasets/prepare",Map.of("output",path,"dataset",s.protocol().path("smoke").asBoolean()?"synthetic":"covertype",
                        "clients",100,"seed",s.protocol().path("splitSeed").asLong(),"partitionSeed",partition,"alpha",.5));
                var pools=json.createObjectNode();for(String file:List.of("features.npy","labels.npy","splits.npz")) pools.set(file,manifest.path("hashes").path(file));
                if(pareto&&!pools.equals(s.provenance().path("paretoSourcePools"))) throw new IllegalStateException("Held-out data/splits/scaler inputs differ from Phase A");
                ResearchProvenance.save(s.output().resolve("shared-pools.json"),pools,json,true);
                for(long seed:seeds(settings.path("seeds"))) {
                    List<RunResult> cell=new ArrayList<>();var order=new ArrayList<>(policies);Collections.shuffle(order,new Random(partition*1000+seed));
                    for(var row:order) {
                        var completed=run(s,row,seed,path,phase,"deterministic",0);
                        if(!completed.experiment().path("snapshot").path("manifest").equals(manifest)) throw new IllegalStateException("Prepared partition changed");
                        if(!cell.isEmpty()) controlled.validatePair(cell.get(0),completed,"lambdaPolicy");
                        cell.add(completed);runs.add(completed);
                    }
                }
            }
        } catch(Exception e) {failure=e;}
        if(pareto&&failure==null) try {
            ParetoProtocol.phaseAEvidence(s.root(),s.protocol(),json);
            if(!ResearchProvenance.hash(ParetoProtocol.inside(s.root(),s.protocol().path("auditReportPath").asText())).equals(s.provenance().path("paretoExecution").path("auditReportSha256").asText()))
                throw new IllegalStateException("E0 evidence changed during held-out evaluation");
        } catch(Exception e) {failure=e;}
        if(pareto) ParetoTradeoffReport.write(s.output(),runs,s.protocol(),json,failure);
        else FairnessMatchedReport.write(s.output().resolve(phase),phase,runs,s.protocol(),json,failure);
        if(failure!=null) throw new IllegalStateException("Incomplete "+phase+"; results retained",failure);
        worker.post("/reports/research/plots",Map.of("resultsPath",s.root().relativize(pareto?s.output().resolve("pareto-tradeoff-results.json"):s.output().resolve(phase).resolve("fairness-matched-results.json")).toString().replace('\\','/')));
        return runs;
    }
}
