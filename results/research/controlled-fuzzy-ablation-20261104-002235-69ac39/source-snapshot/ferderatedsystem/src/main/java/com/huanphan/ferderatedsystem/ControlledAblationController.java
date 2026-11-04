package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.huanphan.ferderatedsystem.selection.fuzzy.*;
import org.springframework.web.bind.annotation.*;
import java.util.*;

/** Paired read-only replay. All inputs are past observations, never round outcomes. */
@RestController
public class ControlledAblationController {
    private final ObjectMapper json;
    public ControlledAblationController(ObjectMapper json) {this.json=json;}
    @PostMapping("/research/controlled-replay")
    public ObjectNode replay(@RequestBody JsonNode request) throws Exception {
        int round=request.path("round").asInt();
        if(round<1) throw new IllegalArgumentException("Pre-selection round required");
        var input=request.path("selectorInput");
        var clients=Arrays.asList(json.treeToValue(input.path("eligibleClients"),ClientProfile[].class));
        var history=json.treeToValue(input.path("history"),SelectionHistory.class);
        if(history==null) throw new IllegalArgumentException("Immutable selection history required");
        var result=json.createObjectNode();
        for(int i=0;i<5;i++) {
            ObjectNode template=(ObjectNode)request.path("config").deepCopy();
            template.put("selection",i==0?"crisp_topsis":"fuzzy_topsis");
            var settings=(ObjectNode)template.path("fuzzySelection");
            settings.put("uncertaintyMode",switch(i) {case 0,1 -> "crisp";case 2 -> "fixed";case 3 -> "history_based";default -> "error_calibrated";});
            var config=json.treeToValue(template,ExperimentConfig.class);config.check();
            long start=System.nanoTime();
            var feasible=Policies.feasibleClients(clients,config,round);
            var extracted=new ClientCriteriaExtractor().extract(feasible,config,round,history,null);
            var scores=i==0?new CrispTopsisEngine().rank(extracted.matrix(),config.fuzzySelection().epsilon)
                :new FuzzyTopsisEngine().rank(extracted.matrix(),config.fuzzySelection().epsilon).scores();
            var r=result.putObject("A"+i);
            r.set("ranking",json.valueToTree(CrispTopsisEngine.order(scores)));
            r.set("scores",json.valueToTree(scores));r.set("widths",json.valueToTree(extracted.widths()));
            r.set("observations",json.valueToTree(extracted.observations()));
            r.set("matrix",json.valueToTree(extracted.matrix()));
            r.put("engine",i==0?"CrispTopsisEngine":"FuzzyTopsisEngine");
            r.put("selectorMs",(System.nanoTime()-start)/1e6);
        }
        return result;
    }
}
