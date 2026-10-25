package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class PoliciesTests {
    @Test void staleOrForeignUpdatesRejected() throws Exception {
        var mapper=new ObjectMapper();
        var update=mapper.readTree("""
            {"experimentId":"test","roundId":1,"baseModelVersion":0,"clientId":0,"numSamples":100,
             "status":"TRAINING_COMPLETED","trainingLoss":0.5,"actualTrainingMs":10,"modelSchemaHash":"abc","updatePath":"a.pt"}
            """);
        var profile=new ClientProfile(0,100,100,"homogeneous");
        assertDoesNotThrow(() -> RoundCoordinator.validateUpdate(update,"test",1,0,profile));
        assertThrows(IllegalArgumentException.class,() -> RoundCoordinator.validateUpdate(update,"test",1,1,profile));
        assertThrows(IllegalArgumentException.class,() -> RoundCoordinator.validateUpdate(update,"other",1,0,profile));
    }
    @Test void resourceSelectorFiltersMemoryAndUsesOnlyPreRoundHistory() throws Exception {
        var config=new ObjectMapper().readValue(java.nio.file.Files.readString(java.nio.file.Path.of("../configurations/resource-aware-fedlbw.json")),ExperimentConfig.class);
        var clients=new ArrayList<ClientProfile>();
        for(int i=0;i<100;i++) clients.add(new ClientProfile(i,100,100,"heterogeneous"));
        var selector=new Policies.ResourceAwareSelector();
        var selected=selector.select(clients,config,new Random(42));
        assertEquals(5,selected.size());
        assertEquals(5,new HashSet<>(selected).size());
        assertTrue(selected.stream().allMatch(p -> p.ramMb>=600));
        assertEquals(selected,selector.select(clients,config,new Random(42)));
    }
    @Test void feasibleRandomFiltersRamAndEstimatedDeadlineWithoutRanking() throws Exception {
        var config=new ObjectMapper().readValue(java.nio.file.Files.readString(java.nio.file.Path.of("../configurations/resource-aware-fedlbw.json")),ExperimentConfig.class);
        var clients=new ArrayList<ClientProfile>();
        for(int i=0;i<100;i++) clients.add(new ClientProfile(i,100,100,"heterogeneous"));
        clients.get(40).estimatedSeconds=config.deadlineSeconds()+1;
        var selector=new Policies.FeasibleRandomSelector();
        var selected=selector.select(clients,config,new Random(42));
        assertEquals(5,selected.size());assertEquals(5,new HashSet<>(selected).size());
        assertTrue(selected.stream().allMatch(p->p.ramMb>=600 && p.estimate(config)<=config.deadlineSeconds()));
        assertFalse(selected.contains(clients.get(40)));
        assertEquals(selected,selector.select(clients,config,new Random(42)));
        // A change in utility/reliability alone must not affect feasible random sampling.
        for(var p:clients) {p.completionCount=p.clientId%3;p.selectionCount=100+p.clientId;p.recentTrainingLoss=100.0/(p.clientId+1);}
        assertEquals(selected,selector.select(clients,config,new Random(42)));
        assertEquals(100,clients.size()); // Candidate list is not mutated.
    }
    @Test void feasibleRandomHandlesFewerThanKAndNoFeasibleCandidates() throws Exception {
        var config=new ObjectMapper().readValue(java.nio.file.Files.readString(java.nio.file.Path.of("../configurations/resource-aware-fedlbw.json")),ExperimentConfig.class);
        var low=new ClientProfile(0,100,100,"heterogeneous");
        var high=new ClientProfile(99,100,100,"heterogeneous");
        var selector=new Policies.FeasibleRandomSelector();
        assertEquals(List.of(high),selector.select(List.of(low,high),config,new Random(42)));
        assertTrue(selector.select(List.of(low),config,new Random(42)).isEmpty());
    }
}
