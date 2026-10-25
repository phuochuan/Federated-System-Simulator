package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ScenarioTraceTests {
    @TempDir Path root;
    private final ObjectMapper json=new ObjectMapper();
    @Test void fullPopulationTraceIsStableIndependentOfMethodAndSelection() throws Exception {
        var base=(ObjectNode)json.readTree(Files.readString(Path.of("../configurations/resource-aware-fedlbw.json")));
        base.put("rounds",3);base.put("scenarioTracePath","trace.json");
        var first=json.treeToValue(base,ExperimentConfig.class);
        var expected=ScenarioTrace.generate(first,json);
        base.put("selection","random");base.put("aggregation","fedavg");base.put("architecture","mlp_54_128_64_7");
        var second=json.treeToValue(base,ExperimentConfig.class);
        assertEquals(expected,ScenarioTrace.generate(second,json));
        assertEquals(100,expected.path("rounds").get(0).path("clients").size());
        Files.writeString(root.resolve("trace.json"),json.writeValueAsString(expected));
        assertEquals(ScenarioTrace.load(first,json,root).hash(),ScenarioTrace.load(second,json,root).hash());
        ((ObjectNode)expected.path("rounds").get(0).path("clients").get(99)).put("dropoutEvent",true);
        // Change guaranteed even if original event happened to be true.
        ((ObjectNode)expected.path("rounds").get(0).path("clients").get(99)).put("jitterMultiplier",1.234);
        Files.writeString(root.resolve("trace.json"),json.writeValueAsString(expected));
        assertThrows(IllegalArgumentException.class,()->ScenarioTrace.load(first,json,root));
    }
    @Test void fairnessSeparatesPopulationAndRamFeasibleCoverage() {
        var clients=new ArrayList<ClientProfile>();
        for(int i=0;i<100;i++) clients.add(new ClientProfile(i,100,100,"heterogeneous"));
        clients.get(50).completionCount=1;clients.get(50).feasibleOpportunityCount=1;
        var fairness=RoundCoordinator.resourceFairness(clients,1,600);
        assertEquals(.01,(double)fairness.get("populationCoverage"));
        assertEquals(60,fairness.get("ramFeasiblePopulation"));
        assertEquals(1.0/60,(double)fairness.get("ramFeasibleCoverage"));
        assertEquals(1.0,(double)fairness.get("estimatedFeasibleCoverage"));
        assertNull(RoundCoordinator.resourceFairness(clients,1,10000).get("ramFeasibleCoverage"));
    }
}
