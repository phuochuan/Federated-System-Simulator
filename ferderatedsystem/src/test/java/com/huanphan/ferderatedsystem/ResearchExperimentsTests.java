package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import jakarta.validation.Validation;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.env.MockEnvironment;
import java.nio.file.*;
import java.util.*;
import static com.huanphan.ferderatedsystem.ControlledExperiments.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ResearchExperimentsTests {
    @TempDir Path root;
    final ObjectMapper json=new ObjectMapper();
    ObjectNode protocol() throws Exception {return (ObjectNode)json.readTree(Files.readString(Path.of("../configurations/fairness-matched-lambda.json")));}
    RunResult run(Row row,int partition,long seed,double coverage,double gini) throws Exception {
        var p=protocol();var c=(ObjectNode)p.path("baseConfig").deepCopy();c.put("experimentId","fixture-"+row+"-p"+partition+"-s"+seed).put("rounds",2).put("seed",seed)
                .put("selection",row.selection).put("architecture",row.architecture).put("evaluationSplit","proxy");c.set("fuzzySelection",p.path("fuzzySelection").deepCopy());
        if(row.name().startsWith("P")) ((ObjectNode)c.path("fuzzySelection").path("fairness")).put("lambda",ParetoProtocol.LAMBDAS.get(row.ordinal()-Row.P1.ordinal()));
        else if(row!=Row.M7) ((ObjectNode)c.path("fuzzySelection").path("fairness")).put("lambda",p.path("fixedLambdas").get(row.ordinal()-Row.M1.ordinal()).asDouble());
        c.putObject("provenance").put("configHash","config").putObject("runtimeIdentity").put("build","fixture");
        var config=json.treeToValue(c,ExperimentConfig.class);
        var experiment=json.createObjectNode();experiment.set("config",json.valueToTree(config));var snapshot=experiment.putObject("snapshot");
        snapshot.put("initialModelStateHash","a".repeat(64)).put("initializationMethod","fixture").put("initializationSeed",seed).put("scenarioTraceHash","trace");
        snapshot.putObject("manifest").put("partitionSeed",partition).put("seed",42).put("alpha",.5);
        snapshot.putObject("initialEvaluation").put("accuracy",.3);
        var clients=snapshot.putArray("clients");for(int id=0;id<100;id++) clients.addObject().put("clientId",id).put("selectionCount",id>=40?1:0).put("completionCount",id>=40?1:0).put("cpu",1);
        var history=snapshot.putObject("selectionHistory").putObject("clients");for(int id=40;id<100;id++) history.putObject(Integer.toString(id)).put("selections",1);
        List<JsonNode> rounds=new ArrayList<>();
        for(int r=1;r<=2;r++) {
            var metrics=json.createObjectNode().put("roundId",r).put("modelVersion",r).put("modelStateHash","b".repeat(64))
                    .put("cumulativeVirtualSeconds",r*2).put("cumulativeVirtualSecondsWithSelector",r*2+.1).put("wallClockSeconds",3)
                    .put("selectorComputationMs",2).put("fairnessUpdateMs",1).put("slotsChangedVsTopsis",1)
                    .put("slotsChangedVsTopsisRatio",.2).put("currentFairnessLambda",.3).put("nextFairnessLambda",.3).put("simulatedTrainingRoundSeconds",1);
            var evaluation=metrics.putObject("evaluation").put("architecture",config.architecture()).put("accuracy",r==1?.6:.5).put("macroF1",.4).put("loss",.7).put("worstClassRecall",.1);
            evaluation.set("perClassRecall",json.valueToTree(List.of(.1,.2,.3,.4,.5,.6,.7)));metrics.set("trajectoryEvaluation",evaluation.deepCopy());
            metrics.putObject("fairness").put("feasibleSelectionCoverage",coverage).put("feasibleCompletionCoverage",coverage)
                    .put("feasibleOpportunityAdjustedGini",gini).put("feasibleCompletionOpportunityAdjustedGini",gini)
                    .put("maxFeasibleSelectionStaleness",3).put("meanFeasibleSelectionStaleness",1).put("selectionGini",.6)
                    .put("completionGini",.6).put("ramFeasibleCompletionGini",.3).put("ramFeasiblePopulation",60).put("feasibleOpportunityPopulation",60);
            metrics.set("selectedIds",json.valueToTree(List.of(40,41,42,43,44)));metrics.set("acceptedIds",json.valueToTree(List.of(40,41,42,43,44)));
            metrics.putObject("criteriaObservations");metrics.putObject("fairnessCredits");metrics.putObject("fairnessCreditsAfterRound");metrics.putObject("selectorInput").putObject("history");metrics.putArray("participants");
            rounds.add(metrics);
        }
        experiment.put("status","COMPLETED");return new RunResult(row,config,experiment,rounds.get(1),rounds);
    }
    @Test void validationRejectsOverlapBadToleranceAndInsufficientAuditRepetitions() throws Exception {
        var p=protocol();ResearchExperiments.validate(p,false);
        ((ObjectNode)p.path("evaluation")).set("partitionSeeds",p.path("validation").path("partitionSeeds"));
        assertThrows(IllegalArgumentException.class,()->ResearchExperiments.validate(p,false));
        var invalid=protocol();((ObjectNode)invalid.path("matching")).put("selectionGiniMeanAbs",-1);
        assertThrows(IllegalArgumentException.class,()->ResearchExperiments.validate(invalid,false));
        var a=(ObjectNode)json.readTree(Files.readString(Path.of("../configurations/reproducibility-audit.json")));
        ResearchExperiments.validate(a,true);((ObjectNode)a.path("audit")).put("repetitions",2);
        assertThrows(IllegalArgumentException.class,()->ResearchExperiments.validate(a,true));
    }
    @Test void matchingPrioritizesEquivalentCoverageNeverUsesLearningScoresAndChecksAllFairnessDimensions() throws Exception {
        var adaptive=run(Row.M7,1001,42,1,.35);var badCoverage=run(Row.M1,1001,42,.9,.35);var good=run(Row.M2,1001,42,1,.36);
        var rows=List.of(adaptive,badCoverage,good);var tolerance=protocol().path("matching");
        var result=FairnessMatchedReport.match(rows,tolerance,json);assertEquals("M2",result.path("selectedPolicy").asText());
        ((ObjectNode)good.result().path("evaluation")).put("accuracy",.01).put("macroF1",.01);
        assertEquals(result,FairnessMatchedReport.match(rows,tolerance,json));
        ((ObjectNode)good.result().path("fairness")).put("feasibleCompletionOpportunityAdjustedGini",.9);
        assertEquals("NO_MATCH",FairnessMatchedReport.match(rows,tolerance,json).path("status").asText());
    }
    @Test void incompletePairsAndDifferentOpportunityPopulationsCannotBeCalledMatched() throws Exception {
        var adaptive=run(Row.M7,1001,42,1,.35);var incomplete=run(Row.M1,1001,43,1,.35);
        assertThrows(IllegalStateException.class,()->FairnessMatchedReport.match(List.of(adaptive,incomplete),protocol().path("matching"),json));
        var fixed=run(Row.M1,1001,42,1,.35);
        ((ObjectNode)fixed.experiment().path("snapshot").path("selectionHistory").path("clients")).remove("40");
        assertEquals("NO_MATCH",FairnessMatchedReport.match(List.of(adaptive,fixed),protocol().path("matching"),json).path("status").asText());
    }
    @Test void lockRejectsHyperparameterRuntimeAndPolicyEdits() throws Exception {
        var p=protocol();var runtime=json.createObjectNode().put("build","one");var lock=json.createObjectNode().put("status","MATCHED").put("protocolHash",ResearchProvenance.hash(p));
        lock.set("protocol",p.deepCopy());lock.set("adaptiveHyperparameters",p.path("fuzzySelection").deepCopy());lock.set("runtimeIdentity",runtime);
        lock.putObject("matching").put("selectedPolicy","M1").put("selectedLambda",.6);
        lock.put("lockHash",ResearchProvenance.hash(lock));
        ResearchExperiments.validateLock(lock,p,runtime);
        assertThrows(IllegalStateException.class,()->ResearchExperiments.validateLock(lock,p,json.createObjectNode().put("build","two")));
        var altered=p.deepCopy();((ObjectNode)altered.path("fuzzySelection").path("fairness")).put("adaptationRate",.9);
        assertThrows(IllegalStateException.class,()->ResearchExperiments.validateLock(lock,altered,runtime));
        ((ObjectNode)lock.path("matching")).put("selectedLambda",.7);
        assertThrows(IllegalStateException.class,()->ResearchExperiments.validateLock(lock,p,runtime));
    }
    @Test void provenanceUsesCanonicalContentAndImmutableWrites() throws Exception {
        assertEquals(ResearchProvenance.hash(json.readTree("{\"a\":1,\"b\":2}")),ResearchProvenance.hash(json.readTree("{\"b\":2,\"a\":1}")));
        var file=root.resolve("provenance.json");var value=json.createObjectNode().put("build","a");
        ResearchProvenance.save(file,value,json,true);String before=ResearchProvenance.hash(file);
        ResearchProvenance.save(file,value,json,true);assertEquals(before,ResearchProvenance.hash(file));
        assertThrows(IllegalStateException.class,()->ResearchProvenance.save(file,json.createObjectNode().put("build","b"),json,true));
    }
    @Test void reportSeparatesFinalTestFromProxyTailAndUsesSampleSd() throws Exception {
        var a=run(Row.M1,1001,42,1,.35);var b=run(Row.M7,1001,42,1,.35);
        ((ObjectNode)b.result().path("evaluation")).put("accuracy",.8);
        assertEquals(.55,FairnessMatchedReport.metric(b,"accuracyTailMean",10,json),1e-12);
        assertEquals(Math.sqrt(.005),FairnessMatchedReport.metric(b,"accuracyTailSd",10,json),1e-12);
        assertEquals(.8,FairnessMatchedReport.metric(b,"accuracy",10,json));
        var outcome=FairnessMatchedReport.outcome(b,"evaluation",protocol(),json);
        assertFalse(outcome.path("targets").path("0.65").path("reached").asBoolean());
        assertEquals(40,outcome.path("populationNeverSelected").asInt());assertEquals(60,outcome.path("observedFeasibleOpportunityDenominator").asInt());
        FairnessMatchedReport.write(root,"evaluation",List.of(a,b),protocol(),json,null);
        assertTrue(Files.readString(root.resolve("fairness-matched-summary.md")).contains("within-run"));
        var report=json.readTree(Files.readString(root.resolve("fairness-matched-results.json")));
        assertEquals(.3,report.path("pairedDifferences").get(0).path("accuracy").asDouble(),1e-12);
        assertTrue(Files.readString(root.resolve("fairness-matched-results.csv")).contains("populationNeverSelected"));
        assertTrue(FairnessMatchedReport.stats(List.of(.7),json).path("sampleSd").isNull());
    }
    @Test void auditFindsTheFirstModelAndMetricDivergenceWithoutAssumingEquality() throws Exception {
        var a=run(Row.M1,1001,42,1,.35);var b=run(Row.M1,1001,42,1,.35);
        assertTrue(ReproducibilityAuditReport.compare(a,b,json).path("exactDecisionModelMetricReplay").asBoolean());
        ((ObjectNode)b.rounds().get(1)).put("modelStateHash","c".repeat(64));
        ((ObjectNode)b.rounds().get(1).path("evaluation")).put("accuracy",.2);
        var comparison=ReproducibilityAuditReport.compare(a,b,json);
        assertEquals(2,comparison.path("firstGlobalModelDifference").asInt());assertEquals(2,comparison.path("firstLearningMetricsDifference").asInt());
        assertFalse(comparison.path("exactDecisionModelMetricReplay").asBoolean());
    }
    @Test void auditReportsConditionalRepeatSdSeparatelyFromSeedAndTailVariability() throws Exception {
        var a=run(Row.M1,1001,42,1,.35);var b=run(Row.M1,1001,42,1,.35);
        ((ObjectNode)b.result().path("evaluation")).put("accuracy",.7);
        var protocol=json.readTree(Files.readString(Path.of("../configurations/reproducibility-audit.json")));
        var report=ReproducibilityAuditReport.create(Map.of("measured:42:fixed",List.of(a,b)),protocol,json,null);
        var s=report.path("repeatSummaryByGroup").get(0).path("metrics").path("accuracy");
        assertEquals(.6,s.path("mean").asDouble(),1e-12);assertEquals(Math.sqrt(.02),s.path("sampleSd").asDouble(),1e-12);
        assertEquals(2,s.path("n").asInt());assertFalse(report.path("complete").asBoolean());
    }
    @Test void completedIdentityIsReusedAndDifferentRuntimeIsRejected() throws Exception {
        var fixture=run(Row.M1,1001,42,1,.35);var repo=mock(ExperimentRepository.class);var coordinator=mock(RoundCoordinator.class);var worker=mock(PythonMLClient.class);
        var python=json.createObjectNode().put("executionDevice","cpu").put("sourceFilesUnchanged",true);python.putObject("sourceHashes");python.putObject("packages");
        when(worker.get("/runtime")).thenReturn(python);
        var config=(ObjectNode)json.valueToTree(fixture.config());((ObjectNode)config.path("provenance")).set("runtimeIdentity",ResearchProvenance.runtime(worker,json));
        var run=new RunResult(fixture.row(),json.treeToValue(config,ExperimentConfig.class),fixture.experiment(),fixture.result(),fixture.rounds());
        ((ObjectNode)run.experiment().path("snapshot")).set("executionProvenance",run.config().provenance());
        when(worker.get(startsWith("/datasets/manifest"))).thenReturn(run.experiment().path("snapshot").path("manifest"));
        when(repo.find(run.config().experimentId())).thenReturn(Map.of("status","COMPLETED","config",json.writeValueAsString(run.config()),"snapshot",json.writeValueAsString(run.experiment().path("snapshot"))));
        when(repo.rounds(run.config().experimentId())).thenReturn(run.rounds());when(repo.result(run.config().experimentId())).thenReturn(run.result());
        try(var factory=Validation.buildDefaultValidatorFactory()) {
            var controlled=new ControlledExperiments(coordinator,repo,worker,json,new MockEnvironment(),factory.getValidator());
            var retained=controlled.runPrepared(Row.M1,run.config(),root.resolve("runs"));
            assertInstanceOf(IndexedRoundEvidence.class,retained.rounds());
            assertEquals(run.rounds(),retained.rounds());
            assertEquals(FairnessMatchedReport.outcome(run,"validation",protocol(),json),
                    FairnessMatchedReport.outcome(retained,"validation",protocol(),json));
            controlled.runPrepared(Row.M1,run.config(),root.resolve("runs"));
            verify(coordinator,never()).startAndAwait(any());
            var altered=(ObjectNode)json.valueToTree(run.config());((ObjectNode)altered.path("provenance").path("runtimeIdentity")).put("build","different");
            assertThrows(IllegalStateException.class,()->controlled.runPrepared(Row.M1,json.treeToValue(altered,ExperimentConfig.class),root.resolve("runs")));
            var changed=(ObjectNode)run.rounds().get(0).deepCopy();changed.put("roundId",999);
            ResearchProvenance.saveJson(root.resolve("runs/rounds.json"),List.of(changed,run.rounds().get(1)),json);
            var failure=assertThrows(IllegalStateException.class,()->controlled.runPrepared(Row.M1,run.config(),root.resolve("runs")));
            assertTrue(failure.getMessage().contains("Export changed"));
        }
    }
}
