package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.env.MockEnvironment;
import java.nio.file.*;
import java.util.*;
import static com.huanphan.ferderatedsystem.ControlledExperiments.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ParetoTradeoffTests {
    @TempDir Path root;
    final ObjectMapper json=new ObjectMapper();
    ObjectNode protocol() throws Exception {
        var p=(ObjectNode)json.readTree(Files.readString(Path.of("../configurations/pareto-tradeoff.json")));
        p.put("smoke",true).put("largeAccuracyDropPp",5);
        ((ObjectNode)p.path("baseConfig")).put("rounds",2);
        ((ObjectNode)p.path("validation")).set("partitionSeeds",json.valueToTree(List.of(1001)));
        ((ObjectNode)p.path("validation")).set("seeds",json.valueToTree(List.of(42)));
        ((ObjectNode)p.path("evaluation")).set("partitionSeeds",json.valueToTree(List.of(2001,2002)));
        ((ObjectNode)p.path("evaluation")).set("seeds",json.valueToTree(List.of(42,43)));
        return p;
    }
    ObjectNode vector() {var v=json.createObjectNode();ParetoTradeoffReport.OBJECTIVES.keySet().forEach(k->v.put(k,1.0));return v;}
    @Test void everyObjectiveUsesTheCorrectDirectionAndEqualityDoesNotDominate() {
        var base=vector();assertFalse(ParetoTradeoffReport.dominates(base,base,ParetoTradeoffReport.OBJECTIVES));
        for(var direction:ParetoTradeoffReport.OBJECTIVES.entrySet()) {
            var better=base.deepCopy();better.put(direction.getKey(),direction.getValue()==ParetoTradeoffReport.Direction.MAXIMIZE?1.1:.9);
            assertTrue(ParetoTradeoffReport.dominates(better,base,ParetoTradeoffReport.OBJECTIVES),direction.getKey());
            assertFalse(ParetoTradeoffReport.dominates(base,better,ParetoTradeoffReport.OBJECTIVES));
        }
        var trade=base.deepCopy().put("accuracy",1.1).put("virtualSecondsWithSelector",1.1);
        assertFalse(ParetoTradeoffReport.dominates(trade,base,ParetoTradeoffReport.OBJECTIVES));
        assertFalse(ParetoTradeoffReport.dominates(base,trade,ParetoTradeoffReport.OBJECTIVES));
    }
    @Test void missingObjectivesAreUnassessedAndNumericZeroTiesArePreserved() {
        var a=vector();var b=a.deepCopy();a.put("accuracyTailSd",0.0);b.put("accuracyTailSd",-0.0);
        assertFalse(ParetoTradeoffReport.dominates(a,b,ParetoTradeoffReport.OBJECTIVES));
        b.remove("macroF1");var point=json.createObjectNode().put("policy","P4").put("dataComplete",true);point.set("means",b);
        var ranked=ParetoTradeoffReport.rank(List.of(point),ParetoTradeoffReport.OBJECTIVES,json);
        assertEquals("P4",ranked.path("unassessedPolicies").get(0).asText());assertTrue(ranked.path("nondominatedPolicies").isEmpty());
    }
    @Test void policiesAndHeldoutPartitionsAreLocked() throws Exception {
        var p=protocol();ResearchExperiments.validate(p,false);ParetoProtocol.validate(p);
        ((ObjectNode)p.path("policies").get(0)).put("lambda",.7);
        assertThrows(IllegalArgumentException.class,()->ParetoProtocol.validate(p));
        var overlap=protocol();((ObjectNode)overlap.path("evaluation")).set("partitionSeeds",overlap.path("validation").path("partitionSeeds"));
        assertThrows(IllegalArgumentException.class,()->ResearchExperiments.validate(overlap,false));
        var production=(ObjectNode)json.readTree(Files.readString(Path.of("../configurations/pareto-tradeoff.json")));
        ((ObjectNode)production.path("evaluation")).set("seeds",json.valueToTree(List.of(42)));
        assertThrows(IllegalArgumentException.class,()->ParetoProtocol.validate(production));
    }
    ObjectNode evidenceProtocol() throws Exception {
        var p=protocol();var source=p.deepCopy();source.remove(List.of("phaseA","policies","analysisType","largeAccuracyDropPp"));
        var runtime=json.createObjectNode().put("javaBuildHash","old-build");
        var report=json.createObjectNode().put("complete",true).put("phase","validation").put("smoke",true);report.putObject("fairnessMatching").put("status","NO_MATCH");
        var manifest=json.createObjectNode().put("alpha",.5).put("strategy","dirichlet_label_skew").put("dataset","synthetic");
        manifest.putObject("hashes").put("features.npy","a".repeat(64)).put("labels.npy","b".repeat(64)).put("splits.npz","c".repeat(64));
        var rows=report.putArray("results");for(int i=1;i<=7;i++) {
            var row=rows.addObject().put("experimentId","phase-a-M"+i).put("policy","M"+i).put("partitionSeed",1001).put("trainingScenarioSeed",42).put("finalEvaluationSplit","proxy")
                    .put("configuredLambda",i==7?.3:source.path("fixedLambdas").get(i-1).asDouble())
                    .put("initialModelHash","a".repeat(64)).put("scenarioTraceHash","b".repeat(64)).put("partitionManifestHash",ResearchProvenance.hash(manifest));
            var provenance=row.putObject("provenance");provenance.set("runtimeIdentity",runtime);provenance.set("protocol",source);
            var exported=json.createObjectNode();exported.putObject("snapshot").set("manifest",manifest);
            ResearchProvenance.save(root.resolve("runs/phase-a-M"+i+"/experiment.json"),exported,json,false);
        }
        Path reportPath=root.resolve("phase-a.json"),lockPath=root.resolve("lock.json");ResearchProvenance.save(reportPath,report,json,false);
        var lock=json.createObjectNode().put("status","NO_MATCH").put("protocolHash",ResearchProvenance.hash(source)).put("validationReportHash",ResearchProvenance.hash(reportPath));
        lock.set("protocol",source);lock.set("runtimeIdentity",runtime);lock.set("adaptiveHyperparameters",source.path("fuzzySelection"));lock.put("lockHash",ResearchProvenance.hash(lock));ResearchProvenance.save(lockPath,lock,json,false);
        p.putObject("phaseA").put("reportPath","phase-a.json").put("lockPath","lock.json").put("reportSha256",ResearchProvenance.hash(reportPath)).put("lockSha256",ResearchProvenance.hash(lockPath));return p;
    }
    @Test void sourceValidationMustBeCompletePinnedAndInheritedWithoutTuning() throws Exception {
        var p=evidenceProtocol();assertEquals("NO_MATCH",ParetoProtocol.phaseAEvidence(root,p,json).path("status").asText());
        var tuned=p.deepCopy();((ObjectNode)tuned.path("fuzzySelection").path("fairness")).put("smoothing",.5);
        assertThrows(IllegalStateException.class,()->ParetoProtocol.phaseAEvidence(root,tuned,json));
        Files.writeString(root.resolve("phase-a.json"),"{}");
        assertThrows(IllegalStateException.class,()->ParetoProtocol.phaseAEvidence(root,p,json));
    }
    @Test void missingHistoricalOrDifferentRuntimeAuditBlocksDeterminismClaims() throws Exception {
        var p=protocol();p.put("auditReportPath","audit.json");var runtime=json.createObjectNode().put("javaBuildHash","new-build");
        assertFalse(ParetoProtocol.auditReadiness(root,p,runtime,json).path("ready").asBoolean());
        var audit=json.createObjectNode().put("complete",true).put("deterministicReplayPassed",true).put("savedStateReplayPassed",true).put("conditionalTrainingPassed",true).put("smoke",true).put("completedRuns",12).put("expectedRuns",12);
        audit.set("runtimeIdentity",json.createObjectNode().put("javaBuildHash","old-build"));var summaries=audit.putArray("repeatSummaryByGroup");for(int i=0;i<4;i++) summaries.addObject().putObject("metrics").putObject("accuracy").put("n",3);
        var runs=audit.putArray("runs");for(int i=0;i<12;i++) runs.addObject().put("savedStateAndTimingReplayPassed",true).putObject("config").putObject("provenance").set("protocol",p);
        ResearchProvenance.save(root.resolve("audit.json"),audit,json,false);
        assertFalse(ParetoProtocol.auditReadiness(root,p,runtime,json).path("determinismClaimed").asBoolean());
        audit.set("runtimeIdentity",runtime);ResearchProvenance.save(root.resolve("audit.json"),audit,json,false);
        assertTrue(ParetoProtocol.auditReadiness(root,p,runtime,json).path("ready").asBoolean());
    }
    List<RunResult> runs() throws Exception {
        List<RunResult> runs=new ArrayList<>();var factory=new ResearchExperimentsTests();
        for(int partition:List.of(2001,2002)) for(int seed:List.of(42,43)) for(var policy:ParetoProtocol.ROWS) {
            var run=factory.run(policy,partition,seed,1,.3);boolean strong=(partition==2001&&policy==Row.P1)||(partition==2002&&policy==Row.P4);
            var last=(ObjectNode)run.result();last.put("evaluationSplit","test").put("cumulativeVirtualSecondsWithSelector",strong?1:2);
            ((ObjectNode)last.path("evaluation")).put("accuracy",strong?.8:.6).put("macroF1",strong?.6:.4);
            ((ObjectNode)last.path("fairness")).put("feasibleOpportunityAdjustedGini",strong?.2:.4);
            if(strong) for(var r:run.rounds()) ((ObjectNode)r.path("trajectoryEvaluation")).put("accuracy",.6);
            runs.add(run);
        }
        return runs;
    }
    @Test void reportPairsP4AgainstAllThreeFixedPoliciesAndExposesPartitionInconsistency() throws Exception {
        var p=protocol();var runs=runs();ResearchProvenance.save(root.resolve("pareto-tradeoff-config.json"),p,json,true);
        ParetoTradeoffReport.write(root,runs,p,json,null);
        var report=json.readTree(Files.readString(root.resolve("pareto-tradeoff-results.json")));
        assertEquals(16,report.path("completedRuns").asInt());assertEquals(12,report.path("pairedDifferences").size());assertEquals("PARETO_COMPARISON",report.path("analysisType").asText());assertFalse(report.has("fairnessMatching"));
        for(var delta:report.path("pairedDifferences")) assertEquals(delta.path("partitionSeed").asInt()==2001&&delta.path("policy").asText().equals("P1")?-.2:delta.path("partitionSeed").asInt()==2002?.2:0,delta.path("accuracy").asDouble(),1e-12);
        var frontier=report.path("frontier");var p4=frontier.path("partitionConsistency").get(3);assertTrue(p4.path("inconsistentAcrossPartitions").asBoolean());
        assertEquals("DOMINATED",p4.path("statusByPartition").path("2001").asText());assertEquals("NONDOMINATED",p4.path("statusByPartition").path("2002").asText());
        assertEquals(2,frontier.path("crossPartition").path("multiObjective").path("points").get(0).path("statisticsAcrossPartitionMeans").path("accuracy").path("n").asInt());
        assertFalse(report.path("largeAccuracyDrops").isEmpty());assertTrue(Files.readString(root.resolve("pareto-tradeoff-summary.md")).contains("not statistical equivalence"));
        assertTrue(Files.exists(root.resolve("pareto-tradeoff-frontier.json")));assertTrue(Files.exists(root.resolve("pareto-tradeoff-trajectory-data.csv")));
    }
    @Test void missingCellsStayIncompleteRatherThanProducingAFinalConclusion() throws Exception {
        var p=protocol();var runs=new ArrayList<>(runs());runs.remove(runs.size()-1);ResearchProvenance.save(root.resolve("pareto-tradeoff-config.json"),p,json,true);
        ParetoTradeoffReport.write(root,runs,p,json,null);
        var result=json.readTree(Files.readString(root.resolve("pareto-tradeoff-results.json")));
        assertFalse(result.path("complete").asBoolean());assertTrue(result.path("pairedDifferences").isEmpty());
    }
    @Test void twoDimensionalFrontierCanBeAssessedWhenAnUnrelatedObjectiveIsMissing() throws Exception {
        var p=protocol();var records=json.createArrayNode();
        for(var run:runs()) {var record=FairnessMatchedReport.outcome(run,"pareto",p,json);if(run.row()==Row.P4) record.putNull("virtualSecondsWithSelector");records.add(record);}
        var part=ParetoTradeoffReport.frontier(records,p,json).path("perPartition").get(0);
        assertEquals("P4",part.path("multiObjective").path("unassessedPolicies").get(0).asText());
        assertTrue(part.path("accuracyGini2D").path("unassessedPolicies").isEmpty());
    }
    @Test void explicitParetoCliModeDoesNotInvokeTheOldManualSequence() throws Exception {
        var controlled=mock(ControlledExperiments.class);var paper=mock(PaperExperiments.class);
        new FerderatedsystemApplication().paperExperiment(paper,controlled,new MockEnvironment().withProperty("minifls.launch.method","heldout_pareto")).run(null);
        verify(controlled).runHeldoutParetoEvaluation();verifyNoMoreInteractions(controlled);verifyNoInteractions(paper);
    }
    @Test void workflowRunsThreeStagesInOrderAndReturnsEvaluationReport() throws Exception {
        var controlled=mock(ControlledExperiments.class);
        doCallRealMethod().when(controlled).runParetoWorkflow();
        var report=root.resolve("pareto-tradeoff-summary.md");
        when(controlled.runHeldoutParetoEvaluation()).thenReturn(report);
        assertEquals(report,controlled.runParetoWorkflow());
        var order=inOrder(controlled);
        order.verify(controlled).runParetoWorkflow();
        order.verify(controlled).preflightHeldoutParetoEvaluation();
        order.verify(controlled).runReproducibilityAudit();
        order.verify(controlled).runHeldoutParetoEvaluation();
        order.verifyNoMoreInteractions();
    }
    @Test void workflowStopsWhenAuditFails() throws Exception {
        var controlled=mock(ControlledExperiments.class);
        doCallRealMethod().when(controlled).runParetoWorkflow();
        var failure=new IllegalStateException("Incomplete audit; results retained");
        when(controlled.runReproducibilityAudit()).thenThrow(failure);
        assertSame(failure,assertThrows(IllegalStateException.class,controlled::runParetoWorkflow));
        verify(controlled).preflightHeldoutParetoEvaluation();
        verify(controlled,never()).runHeldoutParetoEvaluation();
    }
    @Test void workflowCliModeBypassesTheOldMatchedEvaluation() throws Exception {
        var controlled=mock(ControlledExperiments.class);var paper=mock(PaperExperiments.class);
        new FerderatedsystemApplication().paperExperiment(paper,controlled,new MockEnvironment().withProperty("minifls.launch.method","pareto_workflow")).run(null);
        verify(controlled).runParetoWorkflow();verifyNoMoreInteractions(controlled);verifyNoInteractions(paper);
    }
}
