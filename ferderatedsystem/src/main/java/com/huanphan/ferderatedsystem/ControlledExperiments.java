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

/** Eight matrix rows; A/B paired experiments and C factorial 2x2, three TXT reports. */
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
        C3(LARGE,"fedlbw","random",false), C4(LARGE,"fedlbw","resource_aware",false);
        final String architecture,aggregation,selection;
        final boolean iid;
        Row(String architecture,String aggregation,String selection,boolean iid) {
            this.architecture=architecture;this.aggregation=aggregation;this.selection=selection;this.iid=iid;
        }
    }
    public record RunResult(Row row,ExperimentConfig config,JsonNode experiment,JsonNode result,List<JsonNode> rounds) {}
    private record Settings(Path root,Path source,String iid,String nonIid,List<Long> seeds,List<Double> targets,ObjectNode base,ObjectNode heterogeneous,Path output) {}
    @FunctionalInterface private interface Runner {RunResult run(long seed) throws Exception;}

    // Eight row functions; C includes both aggregation and selection factors.
    public RunResult runA1(long seed) throws Exception {return run(Row.A1,seed);}
    public RunResult runA2(long seed) throws Exception {return run(Row.A2,seed);}
    public RunResult runB1(long seed) throws Exception {return run(Row.B1,seed);}
    public RunResult runB2(long seed) throws Exception {return run(Row.B2,seed);}
    public RunResult runC1(long seed) throws Exception {return run(Row.C1,seed);}
    public RunResult runC2(long seed) throws Exception {return run(Row.C2,seed);}
    public RunResult runC3(long seed) throws Exception {return run(Row.C3,seed);}
    public RunResult runC4(long seed) throws Exception {return run(Row.C4,seed);}

    public Path compareModelSizes() throws Exception {
        return compare("A-model-size","MLP lớn có cải thiện kết quả so với MLP nhỏ?", "architecture", this::runA1,this::runA2);
    }
    public Path compareAggregations() throws Exception {
        return compare("B-aggregation","FedLBW khác FedAvg thế nào trên cùng dữ liệu Non-IID?", "aggregation", this::runB1,this::runB2);
    }
    public Path compareClientSelection() throws Exception {
        Settings s=loadSettings();
        List<RunResult> c1=new ArrayList<>(),c2=new ArrayList<>(),c3=new ArrayList<>(),c4=new ArrayList<>();
        Exception failure=null;
        try {
            for(long seed:s.seeds()) {
                var a=runC1(seed);c1.add(a);var b=runC2(seed);c2.add(b);
                var c=runC3(seed);c3.add(c);var d=runC4(seed);c4.add(d);
                validatePair(a,b,"selection");validatePair(c,d,"selection");
                validatePair(a,c,"aggregation");validatePair(b,d,"aggregation");
            }
        } catch(Exception e) {failure=e;}
        Path report=s.output().resolve("C-client-selection.txt");
        write(report,FactorialReport.render(s.source().toString(),s.seeds(),s.targets(),c1,c2,c3,c4,failure));
        log.info("matrix.report_saved comparison=C-factorial complete={} path={}",failure==null,report);
        if(failure!=null) throw new IllegalStateException("Factorial comparison failed; see "+report,failure);
        return report;
    }

    ExperimentConfig configFor(Row row,long seed) throws Exception {
        Settings s=loadSettings();
        var node=s.base().deepCopy();
        if(row.name().startsWith("C")) node.setAll(s.heterogeneous());
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
        coordinator.startAndAwait(config);
        var state=repository.find(config.experimentId());
        var experiment=json.valueToTree(state);
        ((ObjectNode)experiment).set("config",json.readTree((String)state.get("config")));
        ((ObjectNode)experiment).set("snapshot",json.readTree((String)state.get("snapshot")));
        var result=repository.result(config.experimentId());
        var rounds=repository.rounds(config.experimentId());
        if(rounds.size()!=config.rounds() || result.path("roundId").asInt()!=config.rounds())
            throw new IllegalStateException("Incomplete round evidence for "+config.experimentId());
        if(!config.architecture().equals(result.path("evaluation").path("architecture").asText()))
            throw new IllegalStateException("Worker returned an unexpected architecture for "+config.experimentId());
        Path folder=loadSettings().output().resolve("runs").resolve(config.experimentId());
        write(folder.resolve("experiment.json"),json.writerWithDefaultPrettyPrinter().writeValueAsString(experiment));
        write(folder.resolve("rounds.json"),json.writerWithDefaultPrettyPrinter().writeValueAsString(rounds));
        write(folder.resolve("result.json"),json.writerWithDefaultPrettyPrinter().writeValueAsString(result));
        log.info("matrix.run_completed row={} seed={} evidence={}",row,seed,folder);
        return new RunResult(row,config,experiment,result,List.copyOf(rounds));
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
        Path source=root.resolve(env.getProperty("minifls.matrix.config","configurations/controlled-matrix.json")).normalize();
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
        settings=new Settings(root,source,iid,nonIid,List.copyOf(seeds),List.copyOf(targets),base,heterogeneous,output);
        log.info("matrix.configured batch={} source={} seeds={} output={}",batch,source,seeds,output);
        return settings;
    }

    private void preflight() throws Exception {
        if(ready) return;
        Settings s=loadSettings();
        for(var row:Row.values()) for(long seed:s.seeds()) configFor(row,seed);
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
        ca.remove(List.of("experimentId",changedField));cb.remove(List.of("experimentId",changedField));
        if(!ca.equals(cb)) throw new IllegalStateException("Uncontrolled configuration differences");
        var sa=a.experiment().path("snapshot");var sb=b.experiment().path("snapshot");
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

    private static void write(Path path,String content) throws Exception {
        Files.createDirectories(path.getParent());
        Files.writeString(path,content,StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
    }
}
