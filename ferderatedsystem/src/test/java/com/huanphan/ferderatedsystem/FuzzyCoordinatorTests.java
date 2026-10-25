package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

/** Deterministic worker fixtures isolate persisted decisions from physical training-time noise.
 * The separate verify_fuzzy.py smoke uses real PyTorch training, not these fixtures. */
class FuzzyCoordinatorTests {
    private final ObjectMapper json=new ObjectMapper();

    @Test void sqliteResumeAfterPartialRoundEqualsUninterruptedForAllNewMethods() throws Exception {
        for(String method:List.of("fuzzy_topsis","fuzzy_topsis_fair","adaptive_fuzzy_topsis_fair")) {
            var full=execute(method,false);
            var resumed=execute(method,true);
            assertEquals(full,resumed,"Persisted scheduler decisions and state must replay exactly: "+method);
        }
    }

    @Test void oldBaselineHasNoSchedulerStateAndRetainsSeededChoices() throws Exception {
        assertEquals(execute("feasible_random",false),execute("feasible_random",true));
        assertEquals(execute("resource_aware",false),execute("resource_aware",true));
    }

    private JsonNode execute(String method,boolean interrupt) throws Exception {
        var node=(ObjectNode)json.readTree(Files.readString(Path.of("../configurations/fuzzy-matrix.json")));
        var base=(ObjectNode)node.get("baseConfig");
        base.set("fuzzySelection",node.get("fuzzySelection"));base.put("selection",method);
        base.put("experimentId","replay");base.put("manifestPath","fixture");
        base.put("rounds",5);base.put("totalClients",8);base.put("selectedPerRound",2);
        base.put("availability",1);base.put("dropout",0);base.put("deadlineSeconds",10);
        var config=json.treeToValue(base,ExperimentConfig.class);
        try(var source=new SingleConnectionDataSource("jdbc:sqlite::memory:",true)) {
            var db=new JdbcTemplate(source);
            var repository=new ExperimentRepository(db,json,new DataSourceTransactionManager(source));repository.initialize();
            var failed=new AtomicBoolean(false);
            var worker=mock(PythonMLClient.class);
            var manifest=json.createObjectNode().put("totalClients",8);
            var clients=manifest.putArray("clients");
            for(int id=0;id<8;id++) clients.addObject().put("clientId",id).put("numSamples",20+id);
            when(worker.get(anyString())).thenReturn(manifest);
            when(worker.aggregationWeights(anyString(),anyList(),anyList())).thenReturn(List.of(.5,.5));
            when(worker.post(anyString(),any())).thenAnswer(invocation->{
                String route=invocation.getArgument(0);var body=json.valueToTree(invocation.getArgument(1));
                if(route.equals("/models/initialize")) return json.createObjectNode().put("checkpointPath","initial.pt")
                        .put("modelStateHash","fixed-initial-hash").put("modelPayloadBytes",100).put("initializationSeed",42);
                if(route.equals("/models/evaluate")) return json.createObjectNode().put("accuracy",.6).put("loss",.7).put("macroF1",.6);
                if(route.equals("/train")) {
                    if(interrupt&&body.path("roundId").asInt()==3&&failed.compareAndSet(false,true))
                        throw new IllegalStateException("Injected interruption after two committed rounds");
                    int id=body.path("clientId").asInt();
                    var result=(ObjectNode)body.deepCopy();
                    return result.put("status","TRAINING_COMPLETED").put("numSamples",20+id)
                            .put("trainingLoss",.5+id*.1).put("actualTrainingMs",20+id*2)
                            .put("modelSchemaHash","schema").put("modelPayloadBytes",100).put("updatePath","update-"+id+".pt");
                }
                if(route.equals("/simulation/round")) {
                    var result=json.createObjectNode().put("virtualRoundSeconds",.1);var results=result.putArray("results");
                    for(var job:body.path("jobs")) results.addObject().put("clientId",job.path("clientId").asInt())
                            .put("status","COMPLETED").put("completionSeconds",.1);
                    return result;
                }
                if(route.equals("/models/aggregate")) return json.createObjectNode().put("modelVersion",body.path("baseModelVersion").asInt()+1)
                        .put("checkpointPath","round-"+body.path("roundId").asInt()+".pt");
                throw new IllegalArgumentException("Unexpected route "+route);
            });
            var coordinator=new RoundCoordinator(worker,repository,json);
            try {
                if(interrupt) {
                    var initialCoordinator=coordinator;
                    assertThrows(IllegalStateException.class,()->initialCoordinator.startAndAwait(config));
                    assertEquals(2,repository.rounds("replay").size());
                    var snapshot=json.readTree((String)repository.find("replay").get("snapshot"));
                    assertEquals(2,snapshot.path("round").asInt());
                    if(method.contains("fuzzy")) assertEquals(2,snapshot.path("fuzzySelectionState").path("lastCommittedRound").asInt());
                    coordinator.close(); // New coordinator: nothing is recovered from the failed task's memory.
                    coordinator=new RoundCoordinator(worker,repository,json);coordinator.resume("replay");
                    long deadline=System.nanoTime()+10_000_000_000L;
                    while(repository.find("replay").get("status").equals("RUNNING")&&System.nanoTime()<deadline) Thread.sleep(10);
                    assertEquals("COMPLETED",repository.find("replay").get("status"));
                } else coordinator.startAndAwait(config);
                var evidence=json.createObjectNode();var rounds=evidence.putArray("rounds");
                for(var round:repository.rounds("replay")) {
                    var record=rounds.addObject();
                    for(String field:List.of("selectedIds","acceptedIds","estimatedFeasibleIds","fuzzyTopsisScores","fairnessCredits",
                            "finalSelectionScores","currentFairnessLambda","nextFairnessLambda","fairnessCreditsAfterRound","fairness"))
                        record.set(field,round.path(field));
                }
                var snapshot=json.readTree((String)repository.find("replay").get("snapshot"));
                evidence.set("history",snapshot.path("selectionHistory"));evidence.set("state",snapshot.path("fuzzySelectionState"));
                if(!method.contains("fuzzy")) assertTrue(snapshot.path("fuzzySelectionState").isNull());
                assertEquals(5,rounds.size());return evidence;
            } finally {coordinator.close();}
        }
    }
}
