package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.validation.Validation;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.ArgumentCaptor;
import org.springframework.mock.env.MockEnvironment;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class ControlledExperimentsTests {
    @TempDir Path root;
    private final ObjectMapper json=new ObjectMapper();
    private ValidatorFactory validation;
    private RoundCoordinator coordinator;
    private ExperimentRepository repository;
    private PythonMLClient worker;
    private ControlledExperiments matrix;
    private final Map<String,Map<String,Object>> states=new HashMap<>();
    private final Map<String,List<JsonNode>> evidence=new HashMap<>();

    @BeforeEach void setup() throws Exception {
        validation=Validation.buildDefaultValidatorFactory();
        coordinator=mock(RoundCoordinator.class);repository=mock(ExperimentRepository.class);worker=mock(PythonMLClient.class);
        var config=(ObjectNode)json.readTree(Files.readString(Path.of("../configurations/controlled-matrix.json")));
        config.put("iidManifestPath","iid");config.put("nonIidManifestPath","non-iid");
        config.set("seeds",json.valueToTree(List.of(42,43,44)));
        config.set("fuzzySelection",json.readTree(Files.readString(Path.of("../configurations/fuzzy-matrix.json"))).get("fuzzySelection"));
        ((ObjectNode)config.path("baseConfig")).put("rounds",2);
        Files.writeString(root.resolve("matrix.json"),json.writeValueAsString(config));
        var env=new MockEnvironment().withProperty("minifls.launch.workspace",root.toString())
                .withProperty("minifls.matrix.config","matrix.json");
        matrix=new ControlledExperiments(coordinator,repository,worker,json,env,validation.getValidator());
        when(worker.get("/datasets/manifest?manifestPath=iid")).thenReturn(manifest("iid_equal"));
        when(worker.get("/datasets/manifest?manifestPath=non-iid")).thenReturn(manifest("dirichlet_label_skew"));
        when(worker.get("/methods")).thenReturn(json.readTree("{\"methods\":[\"fedavg\",\"fedlbw\"]}"));
        doAnswer(invocation -> {complete(invocation.getArgument(0));return null;}).when(coordinator).startAndAwait(any());
        when(repository.find(anyString())).thenAnswer(i->states.get(i.getArgument(0)));
        when(repository.rounds(anyString())).thenAnswer(i->evidence.get(i.getArgument(0)));
        when(repository.result(anyString())).thenAnswer(i->{var rounds=evidence.get(i.getArgument(0));return rounds.get(rounds.size()-1);});
    }

    @AfterEach void close() {validation.close();}

    private JsonNode manifest(String strategy) throws Exception {
        var node=(ObjectNode)json.readTree("""
                {"dataset":"synthetic","seed":42,"counts":{"train":5250,"proxy":350,"test":1400},
                 "totalClients":100,"alpha":0.5,"hashes":{"features.npy":"x","labels.npy":"y","splits.npz":"split"}}
                """);
        node.put("strategy",strategy);return node;
    }

    private void complete(ExperimentConfig config) throws Exception {
        // Independent known values: paired right-minus-left Macro-F1 is +0.05 for every seed.
        boolean right=config.experimentId().contains("-A2-") || config.experimentId().contains("-B2-") || config.experimentId().contains("-C2-") || config.experimentId().contains("-C4-");
        double f1=.6+.1*(config.seed()-42)+(right?.05:0);
        var snapshot=json.createObjectNode();snapshot.put("checkpointPath","artifacts/model.pt");
        snapshot.putNull("timeToTargetSeconds");snapshot.put("gitCommit","test");snapshot.put("gitDirty",false);
        snapshot.put("initialModelStateHash",config.architecture()+"-"+config.seed());snapshot.put("initializationMethod","pytorch-default-linear-v1");
        snapshot.put("initializationSeed",config.seed());snapshot.putObject("initialEvaluation").put("accuracy",0.3);
        var trace=ScenarioTrace.load(config,json,root);snapshot.put("scenarioTraceHash",trace.hash());
        snapshot.set("manifest",manifest(config.manifestPath().equals("iid")?"iid_equal":"dirichlet_label_skew"));
        states.put(config.experimentId(),Map.of("status","COMPLETED","config",json.writeValueAsString(config),"snapshot",json.writeValueAsString(snapshot)));
        List<JsonNode> rounds=new ArrayList<>();
        for(int round=1;round<=config.rounds();round++) {
            var metrics=(ObjectNode)json.readTree("""
                    {"roundId":1,"modelVersion":1,"outcome":"COMMITTED","evaluation":{"accuracy":0.75,"macroF1":0.6,
                    "loss":0.7,"worstClassRecall":0.1,"perClassRecall":[0.1,0.2,0.3,0.4,0.5,0.6,0.7],
                    "perClassPrecision":[0.1,0.2,0.3,0.4,0.5,0.6,0.7],"confusionMatrix":[]},
                    "fairness":{"coverage":0.2,"participationGini":0.4,"ramFeasiblePopulation":60,"ramFeasibleCoverage":0.333333,
                    "estimatedFeasiblePopulation":60,"estimatedFeasibleCoverage":0.333333},"cumulativeVirtualSeconds":4.0,
                    "wallClockSeconds":3.0,"proxyEvaluationMs":100,"proxyEvaluationWallMs":120,"weightCalculationMs":2,
                    "aggregationMs":10,"serverAggregationOverheadMs":132,"logicalModelBytesDispatched":1000,"logicalUpdateBytesAccepted":1000,
                    "acceptedIds":[0,1],"selectedIds":[0,1]}
                    """);
            metrics.put("roundId",round);metrics.put("modelVersion",round);
            metrics.set("scenarioTrace",trace.round(round));
            ((ObjectNode)metrics.path("evaluation")).put("architecture",config.architecture()).put("macroF1",f1);
            rounds.add(metrics);
        }
        evidence.put(config.experimentId(),rounds);
    }

    @Test void pairedConfigurationsChangeOnlyTheIntendedFactor() throws Exception {
        for(var pair:List.of(new Object[]{ControlledExperiments.Row.A1,ControlledExperiments.Row.A2,"architecture"},
                new Object[]{ControlledExperiments.Row.B1,ControlledExperiments.Row.B2,"aggregation"},
                new Object[]{ControlledExperiments.Row.C1,ControlledExperiments.Row.C2,"selection"},
                new Object[]{ControlledExperiments.Row.C3,ControlledExperiments.Row.C4,"selection"},
                new Object[]{ControlledExperiments.Row.C1,ControlledExperiments.Row.C3,"aggregation"},
                new Object[]{ControlledExperiments.Row.C2,ControlledExperiments.Row.C4,"aggregation"},
                new Object[]{ControlledExperiments.Row.C5,ControlledExperiments.Row.C2,"selection"})) {
            var a=matrix.configFor((ControlledExperiments.Row)pair[0],42);
            var b=matrix.configFor((ControlledExperiments.Row)pair[1],42);
            assertTrue(a.simulationEnabled());assertTrue(b.simulationEnabled());
            var first=(ObjectNode)json.valueToTree(a);var second=(ObjectNode)json.valueToTree(b);
            assertNotEquals(first.get((String)pair[2]),second.get((String)pair[2]));
            first.remove(List.of("experimentId",(String)pair[2]));second.remove(List.of("experimentId",(String)pair[2]));
            assertEquals(first,second);
        }
        assertEquals("iid",matrix.configFor(ControlledExperiments.Row.A1,42).manifestPath());
        assertEquals("non-iid",matrix.configFor(ControlledExperiments.Row.B1,42).manifestPath());
        for(var row:List.of(ControlledExperiments.Row.C1,ControlledExperiments.Row.C2,ControlledExperiments.Row.C3,ControlledExperiments.Row.C4,ControlledExperiments.Row.C5))
            assertEquals("heterogeneous",matrix.configFor(row,42).resourceProfile());
        assertEquals("feasible_random",matrix.configFor(ControlledExperiments.Row.C5,42).selection());
    }

    @Test void threeComparisonsRunAllRowsAndExportPairedStatistics() throws Exception {
        var reports=List.of(matrix.compareModelSizes(),matrix.compareAggregations(),matrix.compareClientSelection());
        var configs=ArgumentCaptor.forClass(ExperimentConfig.class);
        verify(coordinator,times(27)).startAndAwait(configs.capture());
        verify(coordinator,never()).start(any());
        assertEquals(27,configs.getAllValues().stream().map(ExperimentConfig::experimentId).distinct().count());
        assertEquals(3,configs.getAllValues().stream().filter(c->c.experimentId().contains("-C2-")).count());
        assertEquals(3,configs.getAllValues().stream().filter(c->c.selection().equals("feasible_random")).count());
        assertTrue(configs.getAllValues().get(0).experimentId().contains("-A1-s42"));
        assertTrue(configs.getAllValues().get(1).experimentId().contains("-A2-s42"));
        for(Path report:reports) {
            String content=Files.readString(report);
            assertTrue(content.contains("Status: COMPLETED"));
            assertTrue(content.contains("0.050000 +/- 0.000000"));
            assertTrue(content.contains("NOT_REACHED"));
            assertTrue(content.contains("seed=44"));
            assertTrue(content.contains("MEAN RECALL PER CLASS"));
        }
        assertTrue(Files.readString(reports.get(2)).contains("FEASIBLE RANDOM VS RESOURCE-AWARE UNDER FEDAVG"));
        assertTrue(Files.readString(reports.get(2)).contains("Question: Does resource-aware ranking"));
        try(var files=Files.walk(reports.get(0).getParent().resolve("runs"))) {
            assertEquals(27,files.filter(p->p.getFileName().toString().equals("result.json")).count());
        }
    }

    @Test void failedSecondRunProducesIncompleteReportAndNoWinner() throws Exception {
        doAnswer(i->{ExperimentConfig c=i.getArgument(0);
            if(c.experimentId().contains("-A2-")) throw new IllegalStateException("worker unavailable");
            complete(c);return null;
        }).when(coordinator).startAndAwait(any());
        assertThrows(IllegalStateException.class,matrix::compareModelSizes);
        try(var files=Files.walk(root.resolve("artifacts/comparisons"))) {
            Path report=files.filter(p->p.getFileName().toString().equals("A-model-size.txt")).findFirst().orElseThrow();
            String content=Files.readString(report);
            assertTrue(content.contains("Status: INCOMPLETE"));assertTrue(content.contains("worker unavailable"));
            assertFalse(content.contains("OBSERVED COMPARISON"));
        }
        verify(coordinator,times(2)).startAndAwait(any());
    }

    @Test void mismatchedTestSplitsAreRejectedBeforeTraining() throws Exception {
        var mismatch=(ObjectNode)manifest("dirichlet_label_skew");
        ((ObjectNode)mismatch.path("hashes")).put("splits.npz","different-test-pool");
        when(worker.get("/datasets/manifest?manifestPath=non-iid")).thenReturn(mismatch);
        assertThrows(IllegalStateException.class,matrix::compareAggregations);
        verifyNoInteractions(coordinator);
    }

    @Test void sameSeedWithDifferentInitialWeightsIsRejected() throws Exception {
        var a=matrix.runB1(42);var b=matrix.runB2(42);
        ((ObjectNode)b.experiment().path("snapshot")).put("initialModelStateHash","different-weights");
        assertThrows(IllegalStateException.class,()->matrix.validatePair(a,b,"aggregation"));
    }

    @Test void changedCounterfactualTraceIsRejectedEvenForUnselectedClient() throws Exception {
        var a=matrix.runC1(42);var b=matrix.runC2(42);
        var event=(ObjectNode)b.rounds().get(0).path("scenarioTrace").path("clients").get(99);
        event.put("available",!event.path("available").asBoolean());
        assertThrows(IllegalStateException.class,()->matrix.validatePair(a,b,"selection"));
    }

    @Test void targetsKeepNonReachedCensoredAndUseFirstCrossing() throws Exception {
        var run=matrix.runB1(42);
        assertFalse(ComparisonReport.targetTime(run,.8).reached());
        assertTrue(Double.isNaN(ComparisonReport.targetTime(run,.8).virtual()));
        ((ObjectNode)run.rounds().get(0).path("evaluation")).put("accuracy",.67);
        ((ObjectNode)run.rounds().get(1).path("evaluation")).put("accuracy",.69);
        var reached=ComparisonReport.targetTime(run,.68);
        assertEquals(2,reached.round());assertEquals(6,reached.wall());assertEquals(4,reached.virtual());
        assertEquals(-1,ComparisonReport.sustainedFromRound(run,.70));
        assertEquals(2,ComparisonReport.sustainedFromRound(run,.68));
        ((ObjectNode)run.experiment().path("snapshot").path("initialEvaluation")).put("accuracy",.72);
        assertEquals(0,ComparisonReport.targetTime(run,.70).virtual());
    }

    @Test void fuzzyMatrixPreservesEveryControlledFactorAndExportsSixPairs() throws Exception {
        var first=(ObjectNode)json.valueToTree(matrix.configFor(ControlledExperiments.Row.F1,42));
        first.remove(List.of("experimentId","selection"));
        for(var row:List.of(ControlledExperiments.Row.F2,ControlledExperiments.Row.F3,ControlledExperiments.Row.F4,ControlledExperiments.Row.F5)) {
            var next=(ObjectNode)json.valueToTree(matrix.configFor(row,42));
            next.remove(List.of("experimentId","selection"));assertEquals(first,next);
        }
        var report=Files.readString(matrix.compareFuzzyClientSelection());
        verify(coordinator,times(15)).startAndAwait(any());
        for(String pair:List.of("F1 VS F2","F1 VS F3","F3 VS F4","F4 VS F5","F1 VS F5","F2 VS F5"))
            assertTrue(report.contains(pair));
        assertTrue(report.contains("Status: COMPLETED"));
        assertTrue(report.contains("selectorSeconds"));
    }

    @Test void interactionUsesDifferenceInDifferences() throws Exception {
        var c1=matrix.runC1(42);var c2=matrix.runC2(42);var c3=matrix.runC3(42);var c4=matrix.runC4(42);
        ((ObjectNode)c1.result().path("evaluation")).put("macroF1",.60);
        ((ObjectNode)c2.result().path("evaluation")).put("macroF1",.64);
        ((ObjectNode)c3.result().path("evaluation")).put("macroF1",.62);
        ((ObjectNode)c4.result().path("evaluation")).put("macroF1",.69);
        assertEquals(.03,FactorialReport.interaction(c1,c2,c3,c4,"macroF1"),1e-10);
    }
}
