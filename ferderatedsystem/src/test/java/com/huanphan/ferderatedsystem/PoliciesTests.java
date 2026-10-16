package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class PoliciesTests {
    @Test void fedAvgUsesSamples() {
        assertEquals(List.of(.25,.75),new Policies.FedAvg().weights(List.of(1,3),List.of()));
        assertThrows(IllegalArgumentException.class,() -> new Policies.FedAvg().weights(List.of(),List.of()));
        assertThrows(IllegalArgumentException.class,() -> new Policies.FedAvg().weights(List.of(0,3),List.of()));
    }
    @Test void fedLBWUsesInverseProxyLossWithStableZeroPolicy() {
        var policy=new Policies.FedLBW();
        assertEquals(List.of(2.0/3,1.0/3),policy.weights(List.of(100,1),List.of(1.0,2.0)));
        assertEquals(List.of(.5,.5),policy.weights(List.of(1,1),List.of(0.0,0.0)));
        assertThrows(IllegalArgumentException.class,() -> policy.weights(List.of(1),List.of(Double.NaN)));
    }
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
}
