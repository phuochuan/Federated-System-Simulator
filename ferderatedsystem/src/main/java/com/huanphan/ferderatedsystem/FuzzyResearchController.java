package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.huanphan.ferderatedsystem.selection.fuzzy.*;
import org.springframework.web.bind.annotation.*;
import java.util.*;

/** Read-only diagnostics using exactly the production extractors/engines. */
@RestController
public class FuzzyResearchController {
    private final ObjectMapper json;
    private final PythonMLClient worker;
    public FuzzyResearchController(ObjectMapper json,PythonMLClient worker) {this.json=json;this.worker=worker;}
    @GetMapping("/research/worker-status") public Object workerStatus() {return worker.retryStatus();}
    @GetMapping("/research/runtime") public Object runtime() throws Exception {return ResearchProvenance.runtime(worker,json);}
    @PostMapping("/research/trace") public Object trace(@RequestBody ExperimentConfig config) {config.check();return ScenarioTrace.generate(config,json);}
    @PostMapping("/research/replay") public Object replay(@RequestBody JsonNode request) throws Exception {
        var template=(ObjectNode)request.path("config").deepCopy();
        var input=request.path("selectorInput");
        var clients=Arrays.asList(json.treeToValue(input.path("eligibleClients"),ClientProfile[].class));
        var history=input.has("history")?json.treeToValue(input.get("history"),SelectionHistory.class):new SelectionHistory();
        int round=request.path("round").asInt();if(round<1) throw new IllegalArgumentException("Replay round required");
        var output=json.createObjectNode();
        for(String policy:List.of("C1","C2","C3","C4","C5")) {
            template.put("selection","fuzzy_topsis");
            ((ObjectNode)template.get("fuzzySelection")).put("uncertaintyMode",switch(policy) {
                case "C1","C2" -> "crisp";case "C3" -> "fixed";case "C4" -> "history_based";default -> "error_calibrated";
            });
            var config=json.treeToValue(template,ExperimentConfig.class);config.check();
            long started=System.nanoTime();
            var feasible=Policies.feasibleClients(clients,config,round);
            var extracted=new ClientCriteriaExtractor().extract(feasible,config,round,history,null);
            var scores=policy.equals("C1")?new CrispTopsisEngine().rank(extracted.matrix(),config.fuzzySelection().epsilon)
                    :new FuzzyTopsisEngine().rank(extracted.matrix(),config.fuzzySelection().epsilon).scores();
            var entry=output.putObject(policy);entry.set("scores",json.valueToTree(scores));
            entry.set("ranking",json.valueToTree(CrispTopsisEngine.order(scores)));
            entry.put("selectorMs",(System.nanoTime()-started)/1e6);
        }
        return output;
    }
}
