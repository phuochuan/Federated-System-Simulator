package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.validation.Validator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.net.URLEncoder;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

/** Controlled A/B/C comparisons, fuzzy selection F group and lambda-policy L ablation. */
@Component
public class ControlledExperiments {
    private static final Logger log=LoggerFactory.getLogger(ControlledExperiments.class);
    private static final String SMALL="mlp_54_128_64_7", LARGE="mlp_54_256_128_7";
    private final RoundCoordinator coordinator;
    private final ExperimentRepository repository;
    private final PythonMLClient worker;
    private final ObjectMapper json;
    private final Environment env;
    private final Validator validator;
    private final String batch=LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss"))+"-"+UUID.randomUUID().toString().substring(0,8);
    private Settings settings;
    private boolean ready;

    public ControlledExperiments(RoundCoordinator coordinator,ExperimentRepository repository,PythonMLClient worker,
                                 ObjectMapper json,Environment env,Validator validator) {
        this.coordinator=coordinator;this.repository=repository;this.worker=worker;
        this.json=json;this.env=env;this.validator=validator;
    }

    public enum Row {
        A1(SMALL,"fedavg","random",true), A2(LARGE,"fedavg","random",true),
        B1(LARGE,"fedavg","random",false), B2(LARGE,"fedlbw","random",false),
        C1(LARGE,"fedavg","random",false), C2(LARGE,"fedavg","resource_aware",false),
        C3(LARGE,"fedlbw","random",false), C4(LARGE,"fedlbw","resource_aware",false),
        C5(LARGE,"fedavg","feasible_random",false), C6(LARGE,"fedavg","resource_aware",false),
        F1(LARGE,"fedavg","feasible_random",false),F2(LARGE,"fedavg","resource_aware",false),
        F3(LARGE,"fedavg","fuzzy_topsis",false),F4(LARGE,"fedavg","fuzzy_topsis_fair",false),
        F5(LARGE,"fedavg","adaptive_fuzzy_topsis_fair",false),
        L0(LARGE,"fedavg","fuzzy_topsis",false),L1(LARGE,"fedavg","fuzzy_topsis_fair",false),
        L2(LARGE,"fedavg","fuzzy_topsis_fair",false),L3(LARGE,"fedavg","fuzzy_topsis_fair",false),
        L4(LARGE,"fedavg","fuzzy_topsis_fair",false),L5(LARGE,"fedavg","adaptive_fuzzy_topsis_fair",false),
        M1(LARGE,"fedavg","fuzzy_topsis_fair",false),M2(LARGE,"fedavg","fuzzy_topsis_fair",false),
        M3(LARGE,"fedavg","fuzzy_topsis_fair",false),M4(LARGE,"fedavg","fuzzy_topsis_fair",false),
        M5(LARGE,"fedavg","fuzzy_topsis_fair",false),M6(LARGE,"fedavg","fuzzy_topsis_fair",false),
        M7(LARGE,"fedavg","adaptive_fuzzy_topsis_fair",false),
        P1(LARGE,"fedavg","fuzzy_topsis_fair",false),P2(LARGE,"fedavg","fuzzy_topsis_fair",false),
        P3(LARGE,"fedavg","fuzzy_topsis_fair",false),P4(LARGE,"fedavg","adaptive_fuzzy_topsis_fair",false);
        final String architecture,aggregation,selection;
        final boolean iid;
        Row(String architecture,String aggregation,String selection,boolean iid) {
            this.architecture=architecture;this.aggregation=aggregation;this.selection=selection;this.iid=iid;
        }
    }
    public record RunResult(Row row,ExperimentConfig config,JsonNode experiment,JsonNode result,List<JsonNode> rounds) {}
    private record Settings(Path root,Path source,String iid,String nonIid,List<Long> seeds,List<Double> targets,ObjectNode base,ObjectNode heterogeneous,JsonNode fuzzy,JsonNode lambda,Path output) {}
    static final List<Row> LAMBDA_ROWS=List.of(Row.L0,Row.L1,Row.L2,Row.L3,Row.L4,Row.L5);
    @FunctionalInterface private interface Runner {RunResult run(long seed) throws Exception;}

    // Nine row functions; C5 isolates resource-aware ranking from feasibility filtering.
    public RunResult runA1(long seed) throws Exception {return run(Row.A1,seed);}
    public RunResult runA2(long seed) throws Exception {return run(Row.A2,seed);}
    public RunResult runB1(long seed) throws Exception {return run(Row.B1,seed);}
    public RunResult runB2(long seed) throws Exception {return run(Row.B2,seed);}
    public RunResult runC1(long seed) throws Exception {return run(Row.C1,seed);}
    public RunResult runC2(long seed) throws Exception {return run(Row.C2,seed);}
    public RunResult runC3(long seed) throws Exception {return run(Row.C3,seed);}
    public RunResult runC4(long seed) throws Exception {return run(Row.C4,seed);}
    public RunResult runC5(long seed) throws Exception {return run(Row.C5,seed);}
    public RunResult runC6(long seed) throws Exception {return run(Row.C6,seed);}
    /** Retains the working-tree application entry point requested by the user. */
    public Path compareClientSelectionC5C6() throws Exception {return compare("C5-C6-feasible-selection","Feasible Random vs Resource-aware","selection",this::runC5,this::runC6);}
    public RunResult runF1(long seed) throws Exception {return run(Row.F1,seed);}
    public RunResult runF2(long seed) throws Exception {return run(Row.F2,seed);}
    public RunResult runF3(long seed) throws Exception {return run(Row.F3,seed);}
    public RunResult runF4(long seed) throws Exception {return run(Row.F4,seed);}
    public RunResult runF5(long seed) throws Exception {return run(Row.F5,seed);}
    public RunResult runL0(long seed) throws Exception {return run(Row.L0,seed);}
    public RunResult runL1(long seed) throws Exception {return run(Row.L1,seed);}
    public RunResult runL2(long seed) throws Exception {return run(Row.L2,seed);}
    public RunResult runL3(long seed) throws Exception {return run(Row.L3,seed);}
    public RunResult runL4(long seed) throws Exception {return run(Row.L4,seed);}
    public RunResult runL5(long seed) throws Exception {return run(Row.L5,seed);}

    public Path runReproducibilityAudit() throws Exception {return research().audit();}
    public Path runFairnessMatchedValidation() throws Exception {return research().validation();}
    public Path runFairnessMatchedEvaluation() throws Exception {return research().evaluation();}
    public Path runHeldoutParetoEvaluation() throws Exception {return research().pareto(false);}
    public Path preflightHeldoutParetoEvaluation() throws Exception {return research().pareto(true);}
    /** Run all three prepared stages in one process, sharing the configured database and runtime. */
    public Path runParetoWorkflow() throws Exception {
        log.info("pareto.workflow stage=1/3 action=preflight");
        preflightHeldoutParetoEvaluation();
        // A missing E0 is expected here: the next stage creates the audit evidence.
        log.info("pareto.workflow stage=2/3 action=reproducibility_audit");
        runReproducibilityAudit();
        // Evaluation rechecks audit readiness and stops before training if E0 did not pass.
        log.info("pareto.workflow stage=3/3 action=heldout_pareto");
        return runHeldoutParetoEvaluation();
    }
    private ResearchExperiments research() {return new ResearchExperiments(this,worker,json,env,validator);}

    public Path compareFixedLambdaAblation() throws Exception {
        Settings s=loadSettings();Map<Row,List<RunResult>> runs=new LinkedHashMap<>();
        LAMBDA_ROWS.forEach(row->runs.put(row,new ArrayList<>()));
        Exception failure=null;
        try {
            // Validate the complete protocol before spending compute on its first run.
            for(var row:LAMBDA_ROWS) for(long seed:s.seeds()) configFor(row,seed);
            for(long seed:s.seeds()) {
                for(var row:LAMBDA_ROWS) {
                    var completed=run(row,seed);runs.get(row).add(completed);
                    int index=runs.get(row).size()-1;
                    if(row!=Row.L0) validatePair(runs.get(Row.L0).get(index),completed,"lambdaPolicy");
                }
            }
        } catch(Exception e) {failure=e;}
        Path report=s.output().resolve("L-fixed-lambda-ablation.txt");
        int window=s.lambda().path("stabilityWindow").asInt(10);
        write(report,LambdaAblationReport.render(s.source().toString(),s.seeds(),s.targets(),window,runs,failure));
        log.info("matrix.report_saved comparison=L-lambda complete={} path={}",failure==null,report);
        if(failure!=null) throw new IllegalStateException("Lambda ablation failed; see "+report,failure);
        return report;
    }

    public Path compareFuzzyClientSelection() throws Exception {
        Settings s=loadSettings();Map<Row,List<RunResult>> runs=new LinkedHashMap<>();
        for(var row:List.of(Row.F1,Row.F2,Row.F3,Row.F4,Row.F5)) runs.put(row,new ArrayList<>());
        Exception failure=null;
        try {
            for(long seed:s.seeds()) {
                for(var row:runs.keySet()) runs.get(row).add(run(row,seed));
                int index=runs.get(Row.F1).size()-1;
                for(var row:runs.keySet()) if(row!=Row.F1) validatePair(runs.get(Row.F1).get(index),runs.get(row).get(index),"selection");
            }
        } catch(Exception e) {failure=e;}
        var out=new StringBuilder("F: FUZZY TOPSIS / FAIRNESS CREDIT / ADAPTIVE FEEDBACK\nStatus: "+(failure==null?"COMPLETED":"INCOMPLETE")+"\n");
        out.append("Protocol: fixed partition and initial model per seed, FedAvg aggregation. No claim of superiority or Lyapunov guarantee.\n");
        for(var pair:List.of(new Row[]{Row.F1,Row.F2},new Row[]{Row.F1,Row.F3},new Row[]{Row.F3,Row.F4},
                new Row[]{Row.F4,Row.F5},new Row[]{Row.F1,Row.F5},new Row[]{Row.F2,Row.F5})) {
            out.append("\n=== ").append(pair[0]).append(" VS ").append(pair[1]).append(" ===\n");
            out.append(ComparisonReport.render(pair[0]+" vs "+pair[1]+": performance / selection fairness / completion fairness", "selection",
                    s.source().toString(),s.seeds(),s.targets(),runs.get(pair[0]),runs.get(pair[1]),failure));
        }
        Path report=s.output().resolve("F-fuzzy-client-selection.txt");write(report,out.toString());
        log.info("matrix.report_saved comparison=F-fuzzy complete={} path={}",failure==null,report);
        if(failure!=null) throw new IllegalStateException("Fuzzy comparison failed; see "+report,failure);
        return report;
    }

    public Path compareModelSizes() throws Exception {
        return compare("A-model-size","MLP lớn có cải thiện kết quả so với MLP nhỏ?", "architecture", this::runA1,this::runA2);
    }
    public Path compareAggregations() throws Exception {
        return compare("B-aggregation","FedLBW khác FedAvg thế nào trên cùng dữ liệu Non-IID?", "aggregation", this::runB1,this::runB2);
    }
    public Path compareClientSelection() throws Exception {
        Settings s=loadSettings();
        List<RunResult> c1=new ArrayList<>(),c2=new ArrayList<>(),c3=new ArrayList<>(),c4=new ArrayList<>(),c5=new ArrayList<>();
        Exception failure=null;
        try {
            for(long seed:s.seeds()) {
                var a=runC1(seed);c1.add(a);var b=runC2(seed);c2.add(b);
                var c=runC3(seed);c3.add(c);var d=runC4(seed);c4.add(d);
                var feasibleRandom=runC5(seed);c5.add(feasibleRandom);
                validatePair(a,b,"selection");validatePair(c,d,"selection");
                validatePair(a,c,"aggregation");validatePair(b,d,"aggregation");
                validatePair(feasibleRandom,b,"selection");
            }
        } catch(Exception e) {failure=e;}
        Path report=s.output().resolve("C-client-selection.txt");
        write(report,FactorialReport.render(s.source().toString(),s.seeds(),s.targets(),c1,c2,c3,c4,c5,failure));
        log.info("matrix.report_saved comparison=C-factorial complete={} path={}",failure==null,report);
        if(failure!=null) throw new IllegalStateException("Factorial comparison failed; see "+report,failure);
        return report;
    }

    ExperimentConfig configFor(Row row,long seed) throws Exception {
        Settings s=loadSettings();
        var node=s.base().deepCopy();
        boolean lambdaRow=row.name().startsWith("L");
        if(row.name().startsWith("C")||row.name().startsWith("F")||lambdaRow) node.setAll(s.heterogeneous());
        if(row.name().startsWith("F")||lambdaRow) {
            if(!s.fuzzy().isObject()) throw new IllegalArgumentException("F/L protocols require fuzzySelection settings");
            node.set("fuzzySelection",s.fuzzy().deepCopy());
        }
        if(lambdaRow) {
            checkLambdaProtocol(s);
            if(row!=Row.L5) ((ObjectNode)node.path("fuzzySelection").path("fairness")).put("lambda",s.lambda().path("fixedLambdas").get(row.ordinal()-Row.L0.ordinal()).asDouble());
        }
        node.put("experimentId","matrix-"+batch+"-"+row+"-s"+seed);
        node.put("manifestPath",row.iid?s.iid():s.nonIid());
        node.put("seed",seed);node.put("architecture",row.architecture);
        node.put("aggregation",row.aggregation);node.put("selection",row.selection);
        var config=json.treeToValue(node,ExperimentConfig.class);
        var violations=validator.validate(config);
        if(!violations.isEmpty()) throw new IllegalArgumentException("Invalid matrix config: "+violations);
        config.check();
        if(!config.simulationEnabled()) throw new IllegalArgumentException("Controlled matrix requires simulationEnabled=true");
        String group=row.name().substring(0,1);
        Path trace=s.output().resolve("traces").resolve(group+"-s"+seed+".json");
        var traceDocument=ScenarioTrace.generate(config,json);
        if(!Files.exists(trace)) write(trace,json.writerWithDefaultPrettyPrinter().writeValueAsString(traceDocument));
        else if(!json.readTree(Files.readString(trace)).equals(traceDocument)) throw new IllegalArgumentException("Trace config changed: "+trace);
        node.put("scenarioTracePath",s.root().relativize(trace).toString().replace('\\','/'));
        return json.treeToValue(node,ExperimentConfig.class);
    }

    private RunResult run(Row row,long seed) throws Exception {
        preflight();
        var config=configFor(row,seed);
        log.info("matrix.run_started batch={} row={} seed={} experiment={} architecture={} selection={} aggregation={}",
                batch,row,seed,config.experimentId(),config.architecture(),config.selection(),config.aggregation());
        return runPrepared(row,config,loadSettings().output().resolve("runs").resolve(config.experimentId()));
    }

    /** Shared execution/export path; research identities permit safe completed-run reuse. */
    RunResult runPrepared(Row row,ExperimentConfig config,Path folder) throws Exception {
        config.check();
        if(!validator.validate(config).isEmpty()) throw new IllegalArgumentException("Invalid experiment config");
        Map<String,Object> prior=null;
        try {prior=repository.find(config.experimentId());} catch(NoSuchElementException ignored) {}
        if(prior==null) coordinator.startAndAwait(config);
        else {
            var stored=(ObjectNode)json.readTree((String)prior.get("config"));var requested=(ObjectNode)json.readTree(json.writeValueAsString(config));
            var storedProvenance=stored.path("provenance");
            stored=stored.deepCopy();requested=requested.deepCopy();stored.remove("provenance");requested.remove("provenance");
            if(!config.hasProvenance() || !stored.equals(requested)||
                    !storedProvenance.path("runtimeIdentity").equals(config.provenance().path("runtimeIdentity"))||
                    !storedProvenance.path("configHash").equals(config.provenance().path("configHash")))
                throw new IllegalStateException("Run identity/config/build provenance mismatch: "+config.experimentId());
            if(!"COMPLETED".equals(prior.get("status")))
                throw new IllegalStateException("Existing run is "+prior.get("status")+"; resume via API, then rerun the batch: "+config.experimentId());
            // Preserve the original Git/launch metadata when reusing a completed identity.
            config=json.readValue((String)prior.get("config"),ExperimentConfig.class);
        }
        var state=repository.find(config.experimentId());
        var experiment=json.valueToTree(state);
        ((ObjectNode)experiment).set("config",json.readTree((String)state.get("config")));
        ((ObjectNode)experiment).set("snapshot",json.readTree((String)state.get("snapshot")));
        if(config.hasProvenance()) {
            if(!config.provenance().equals(experiment.path("snapshot").path("executionProvenance")))
                throw new IllegalStateException("Persisted snapshot/config execution provenance differs");
            ResearchProvenance.verify(config.provenance(),worker,json);
            var current=worker.get("/datasets/manifest?manifestPath="+URLEncoder.encode(config.manifestPath(),StandardCharsets.UTF_8)+"&verify=true");
            if(!experiment.path("snapshot").path("manifest").equals(current)) throw new IllegalStateException("Partition changed during/reusing run");
        }
        var result=repository.result(config.experimentId());
        var rounds=repository.rounds(config.experimentId());
        if(rounds.size()!=config.rounds() || result.path("roundId").asInt()!=config.rounds())
            throw new IllegalStateException("Incomplete round evidence for "+config.experimentId());
        if(!config.architecture().equals(result.path("evaluation").path("architecture").asText()))
            throw new IllegalStateException("Worker returned an unexpected architecture for "+config.experimentId());
        for(var entry:Map.of("experiment.json",experiment,"result.json",result).entrySet()) {
            Path file=folder.resolve(entry.getKey());
            if(Files.exists(file)) {
                try(var in=Files.newInputStream(file)) {
                    if(!ResearchProvenance.hash(json.readTree(in)).equals(ResearchProvenance.hash(entry.getValue()))) throw new IllegalStateException("Export changed: "+file);
                }
            } else ResearchProvenance.saveJson(file,entry.getValue(),json);
        }
        Path roundFile=folder.resolve("rounds.json");
        if(Files.exists(roundFile)) {
            var exported=new IndexedRoundEvidence(roundFile,json);
            if(exported.size()!=rounds.size()) throw new IllegalStateException("Export changed: "+roundFile);
            for(int i=0;i<rounds.size();i++)
                if(!ResearchProvenance.hash(exported.get(i)).equals(ResearchProvenance.hash(rounds.get(i))))
                    throw new IllegalStateException("Export changed: "+roundFile);
        } else ResearchProvenance.saveJson(roundFile,rounds,json);
        // Research matrices retain many runs. Keep only an index, not every round tree.
        List<JsonNode> retained=config.hasProvenance()?new IndexedRoundEvidence(roundFile,json):List.copyOf(rounds);
        log.info("matrix.run_completed row={} seed={} evidence={}",row,config.seed(),folder);
        return new RunResult(row,config,experiment,result,retained);
    }

    private Path compare(String name,String question,String changedField,Runner left,Runner right) throws Exception {
        Settings s=loadSettings();
        List<RunResult> first=new ArrayList<>(),second=new ArrayList<>();
        Path report=s.output().resolve(name+".txt");
        Exception failure=null;
        try {
            for(long seed:s.seeds()) {
                var a=left.run(seed);first.add(a);
                var b=right.run(seed);second.add(b);
                validatePair(a,b,changedField);
            }
        } catch(Exception e) {failure=e;}
        write(report,ComparisonReport.render(question,changedField,s.source().toString(),s.seeds(),s.targets(),first,second,failure));
        log.info("matrix.report_saved comparison={} complete={} path={}",name,failure==null,report);
        if(failure!=null) throw new IllegalStateException("Comparison failed; see "+report,failure);
        return report;
    }

    private Settings loadSettings() throws Exception {
        if(settings!=null) return settings;
        String workspace=env.getProperty("minifls.launch.workspace","");
        Path root=workspace.isBlank()?Path.of("").toAbsolutePath().normalize():Path.of(workspace).toAbsolutePath().normalize();
        if(workspace.isBlank() && !Files.isDirectory(root.resolve("configurations")) && root.getParent()!=null) root=root.getParent();
        boolean fuzzyMode="fuzzy_matrix".equals(env.getProperty("minifls.launch.method","none"));
        boolean lambdaMode="lambda_ablation".equals(env.getProperty("minifls.launch.method","none"));
        Path source=root.resolve(lambdaMode?env.getProperty("minifls.lambda.matrix.config","configurations/lambda-ablation.json"):
                fuzzyMode?env.getProperty("minifls.fuzzy.matrix.config","configurations/fuzzy-matrix.json"):
                env.getProperty("minifls.matrix.config","configurations/controlled-matrix.json")).normalize();
        JsonNode document=json.readTree(Files.readString(source));
        if(!(document.path("baseConfig") instanceof ObjectNode base) || !document.path("seeds").isArray())
            throw new IllegalArgumentException("Matrix requires baseConfig and seeds array");
        List<Long> seeds=new ArrayList<>();
        for(var seed:document.path("seeds")) {
            if(!seed.isIntegralNumber() || !seed.canConvertToLong() || seed.asLong()<0 || seed.asLong()>1000000000L)
                throw new IllegalArgumentException("Invalid matrix seed");
            seeds.add(seed.asLong());
        }
        if(seeds.isEmpty() || new HashSet<>(seeds).size()!=seeds.size()) throw new IllegalArgumentException("Matrix seeds must be nonempty and distinct");
        String iid=document.path("iidManifestPath").asText(),nonIid=document.path("nonIidManifestPath").asText();
        if(iid.isBlank() || nonIid.isBlank()) throw new IllegalArgumentException("Matrix requires both manifest paths");
        String rounds=env.getProperty("minifls.matrix.rounds","");
        if(!rounds.isBlank()) base.put("rounds",Integer.parseInt(rounds));
        Path output=root.resolve("artifacts/comparisons").resolve(batch);
        List<Double> targets=new ArrayList<>();
        for(var target:document.path("accuracyTargets")) {
            if(!target.isNumber() || !Double.isFinite(target.asDouble()) || target.asDouble()<0 || target.asDouble()>1)
                throw new IllegalArgumentException("Invalid accuracy target");
            targets.add(target.asDouble());
        }
        if(targets.isEmpty() || new HashSet<>(targets).size()!=targets.size()) throw new IllegalArgumentException("Distinct accuracyTargets are required");
        if(!(document.path("heterogeneousScenario") instanceof ObjectNode heterogeneous) || !"heterogeneous".equals(heterogeneous.path("resourceProfile").asText()))
            throw new IllegalArgumentException("C requires resourceProfile=heterogeneous");
        var required=Set.of("resourceProfile","availability","dropout","deadlineSeconds","requiredRamMb","jitter");
        var fields=new HashSet<String>();heterogeneous.fieldNames().forEachRemaining(fields::add);
        if(!fields.equals(required)) throw new IllegalArgumentException("heterogeneousScenario must define exactly "+required);
        settings=new Settings(root,source,iid,nonIid,List.copyOf(seeds),List.copyOf(targets),base,heterogeneous,document.path("fuzzySelection"),document.path("lambdaAblation"),output);
        log.info("matrix.configured batch={} source={} seeds={} output={}",batch,source,seeds,output);
        return settings;
    }

    private void preflight() throws Exception {
        if(ready) return;
        Settings s=loadSettings();
        for(var row:Row.values()) if(!row.name().startsWith("F")&&!row.name().startsWith("L")&&!row.name().startsWith("M")&&!row.name().startsWith("P")) for(long seed:s.seeds()) configFor(row,seed);
        var iid=worker.get("/datasets/manifest?manifestPath="+URLEncoder.encode(s.iid(),StandardCharsets.UTF_8));
        var nonIid=worker.get("/datasets/manifest?manifestPath="+URLEncoder.encode(s.nonIid(),StandardCharsets.UTF_8));
        if(!"iid_equal".equals(iid.path("strategy").asText()) || !"dirichlet_label_skew".equals(nonIid.path("strategy").asText()))
            throw new IllegalArgumentException("Matrix expects iid_equal and dirichlet_label_skew manifests");
        if(nonIid.path("alpha").asDouble()!=0.5) throw new IllegalArgumentException("Matrix C requires Non-IID alpha=0.5");
        for(String field:List.of("dataset","seed","counts","totalClients"))
            if(!iid.has(field) || !iid.get(field).equals(nonIid.get(field))) throw new IllegalArgumentException("Manifest mismatch: "+field);
        for(String file:List.of("features.npy","labels.npy","splits.npz"))
            if(!iid.path("hashes").has(file) || !iid.path("hashes").get(file).equals(nonIid.path("hashes").get(file)))
                throw new IllegalArgumentException("Matrix datasets must share the same data/splits: "+file);
        if(iid.path("totalClients").asInt()!=configFor(Row.A1,s.seeds().get(0)).totalClients())
            throw new IllegalArgumentException("Matrix client count does not match manifests");
        var capabilities=worker.get("/methods").path("methods");
        for(String required:List.of("fedavg","fedlbw")) {
            boolean found=false;for(var method:capabilities) if(required.equals(method.asText())) found=true;
            if(!found) throw new IllegalArgumentException("Python worker does not implement "+required);
        }
        ready=true;
    }

    void validatePair(RunResult a,RunResult b,String changedField) {
        var ca=(ObjectNode)json.valueToTree(a.config());var cb=(ObjectNode)json.valueToTree(b.config());
        if(a.config().hasProvenance() || b.config().hasProvenance()) {
            if(!a.config().hasProvenance() || !b.config().hasProvenance() ||
                    !a.config().provenance().path("runtimeIdentity").equals(b.config().provenance().path("runtimeIdentity")))
                throw new IllegalStateException("Paired runtime provenance differs");
            ca.remove("provenance");cb.remove("provenance");
        }
        if(changedField.equals("lambdaPolicy")) {
            for(var config:List.of(ca,cb)) {
                config.remove(List.of("experimentId","selection"));
                ((ObjectNode)config.path("fuzzySelection").path("fairness")).remove("lambda");
            }
        } else {ca.remove(List.of("experimentId",changedField));cb.remove(List.of("experimentId",changedField));}
        if(!ca.equals(cb)) throw new IllegalStateException("Uncontrolled configuration differences");
        var sa=a.experiment().path("snapshot");var sb=b.experiment().path("snapshot");
        if(a.rounds().size()!=b.rounds().size() || a.rounds().size()!=a.config().rounds()) throw new IllegalStateException("Incomplete paired rounds");
        if(!sa.path("manifest").equals(sb.path("manifest"))) throw new IllegalStateException("Partition manifests differ");
        for(String field:List.of("scenarioTraceHash","initializationMethod"))
            if(sa.path(field).asText().isBlank() || !sa.path(field).equals(sb.path(field))) throw new IllegalStateException("Paired evidence mismatch: "+field);
        if(sa.path("initializationSeed").asLong(-1)!=a.config().seed() || sb.path("initializationSeed").asLong(-1)!=b.config().seed())
            throw new IllegalStateException("Initialization seed mismatch");
        if(a.config().architecture().equals(b.config().architecture()) &&
                (sa.path("initialModelStateHash").asText().isBlank() || !sa.path("initialModelStateHash").equals(sb.path("initialModelStateHash"))))
            throw new IllegalStateException("Initial global model weights differ");
        for(int i=0;i<a.rounds().size();i++)
            if(!a.rounds().get(i).has("scenarioTrace") || !a.rounds().get(i).path("scenarioTrace").equals(b.rounds().get(i).path("scenarioTrace")))
                throw new IllegalStateException("Per-client/round scenario traces differ");
    }

    private void checkLambdaProtocol(Settings s) {
        var values=s.lambda().path("fixedLambdas");
        if(!values.isArray()||values.size()!=5||!values.get(0).isNumber()||values.get(0).asDouble()!=0)
            throw new IllegalArgumentException("lambdaAblation.fixedLambdas must contain five ascending values starting at 0");
        double previous=-1;
        for(var value:values) {
            if(!value.isNumber()||!Double.isFinite(value.asDouble())||value.asDouble()<0||value.asDouble()<=previous)
                throw new IllegalArgumentException("Fixed lambdas must be finite, nonnegative and strictly ascending");
            previous=value.asDouble();
        }
        var window=s.lambda().path("stabilityWindow");
        if(!window.isIntegralNumber()||!window.canConvertToInt()||window.asInt()<2) throw new IllegalArgumentException("stabilityWindow must be an integer >=2");
        var fuzzy=s.fuzzy();var fairness=fuzzy.path("fairness");
        if(!"credit_score".equals(fairness.path("mode").asText())) throw new IllegalArgumentException("Lambda ablation requires credit_score");
        var weights=fuzzy.path("weights");
        if(weights.path("fairnessDeficit").asDouble()!=0||weights.path("selectionStaleness").asDouble()!=0)
            throw new IllegalArgumentException("Lambda-only ablation must not add fairness criteria to the decision matrix");
    }

    private static void write(Path path,String content) throws Exception {
        Files.createDirectories(path.getParent());
        Files.writeString(path,content,StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
    }
}
