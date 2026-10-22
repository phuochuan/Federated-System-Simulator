package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;
import jakarta.validation.Validator;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

/** Các hàm gọi từ Application/IDE; Java điều phối, Python chứa từng phương pháp. */
@Component
public class PaperExperiments {
    private static final Logger log=LoggerFactory.getLogger(PaperExperiments.class);
    private final RoundCoordinator coordinator;
    private final PythonMLClient worker;
    private final ObjectMapper json;
    private final Environment env;
    private final Validator validator;

    public PaperExperiments(RoundCoordinator coordinator,PythonMLClient worker,ObjectMapper json,
                            Environment env,Validator validator) {
        this.coordinator=coordinator;this.worker=worker;this.json=json;this.env=env;this.validator=validator;
    }

    /** Không tự chạy training nếu MINIFLS_METHOD=none (mặc định). */
    public void runConfigured() throws Exception {
        String method=env.getProperty("minifls.launch.method","none");
        if(method.equals("none")) return;
        switch(method) {
            case "fedavg" -> runFedAvg();
            case "fedlbw" -> runFedLBW();
            case "fedprox" -> runFedProx();
            case "oort" -> runOort();
            case "fairfedcs" -> runFairFedCS();
            case "longfed" -> runLongFed();
            case "fedavgm" -> runFedAvgM();
            case "fednova" -> runFedNova();
            case "scaffold" -> runScaffold();
            default -> throw new IllegalArgumentException("Unknown MINIFLS_METHOD: "+method);
        }
    }

    public void runFedAvg() throws Exception {run("fedavg");}
    public void runFedLBW() throws Exception {run("fedlbw");}
    // Các điểm gọi đã đặt sẵn; worker sẽ báo rõ chưa triển khai, không chạy thay bằng FedAvg.
    public void runFedProx() throws Exception {run("fedprox");}
    public void runOort() throws Exception {run("oort");}
    public void runFairFedCS() throws Exception {run("fairfedcs");}
    public void runLongFed() throws Exception {run("longfed");}
    public void runFedAvgM() throws Exception {run("fedavgm");}
    public void runFedNova() throws Exception {run("fednova");}
    public void runScaffold() throws Exception {run("scaffold");}

    private void run(String method) throws Exception {
        // Kiểm tra trước khi tạo record hoặc chạy bất kỳ training job nào.
        var capabilities=worker.get("/methods");
        boolean supported=false;
        for(var name:capabilities.path("methods")) if(method.equals(name.asText())) supported=true;
        if(!supported) throw new IllegalArgumentException("Python method '"+method+"' is not implemented; see GET /methods");
        var config=loadConfig(method);
        coordinator.start(config);
        log.info("Started {} experiment {} (selection={}); inspect /experiments/{}",
                method,config.experimentId(),config.selection(),config.experimentId());
    }

    ExperimentConfig loadConfig(String method) throws Exception {
        Path root=workspace();
        String configured=env.getProperty("minifls.launch.config","");
        Path source=root.resolve(configured.isBlank()?"configurations/fedavg.json":configured).normalize();
        var document=json.readTree(Files.readString(source));
        if(!(document instanceof ObjectNode node)) throw new IllegalArgumentException("Experiment config must be a JSON object");
        node.put("aggregation",method);
        String id=env.getProperty("minifls.launch.experiment-id","");
        node.put("experimentId",id.isBlank()?method+"-"+UUID.randomUUID().toString():id);
        override(node,"manifestPath","manifest");
        override(node,"selection","selection");
        String rounds=env.getProperty("minifls.launch.rounds","");
        if(!rounds.isBlank()) node.put("rounds",Integer.parseInt(rounds));
        String seed=env.getProperty("minifls.launch.seed","");
        if(!seed.isBlank()) node.put("seed",Long.parseLong(seed));
        ExperimentConfig config=json.treeToValue(node,ExperimentConfig.class);
        var violations=validator.validate(config);
        if(!violations.isEmpty()) throw new IllegalArgumentException("Invalid launch config: "+violations);
        config.check();
        return config;
    }

    private void override(ObjectNode node,String field,String property) {
        String value=env.getProperty("minifls.launch."+property,"");
        if(!value.isBlank()) node.put(field,value);
    }

    private Path workspace() {
        String configured=env.getProperty("minifls.launch.workspace","");
        if(!configured.isBlank()) return Path.of(configured).toAbsolutePath().normalize();
        Path current=Path.of("").toAbsolutePath().normalize();
        if(Files.isDirectory(current.resolve("configurations"))) return current;
        if(current.getParent()!=null && Files.isDirectory(current.getParent().resolve("configurations"))) return current.getParent();
        throw new IllegalArgumentException("Set MINIFLS_WORKSPACE to the repository root");
    }
}
