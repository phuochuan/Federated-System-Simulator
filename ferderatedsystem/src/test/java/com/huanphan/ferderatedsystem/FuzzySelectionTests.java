package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.huanphan.ferderatedsystem.selection.fuzzy.*;
import org.junit.jupiter.api.Test;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class FuzzySelectionTests {
    final ObjectMapper json=new ObjectMapper();
    ExperimentConfig config(String method) throws Exception {
        var file=json.readTree(Files.readString(Path.of("../configurations/fuzzy-matrix.json")));
        var node=(ObjectNode)file.path("baseConfig").deepCopy();node.set("fuzzySelection",file.path("fuzzySelection"));
        node.put("selection",method);node.put("selectedPerRound",2);
        var c=json.treeToValue(node,ExperimentConfig.class);c.check();return c;
    }
    List<ClientProfile> clients(int n) {
        List<ClientProfile> result=new ArrayList<>();for(int i=0;i<n;i++) result.add(new ClientProfile(i,100,100,"homogeneous"));return result;
    }
    @Test void tfnArithmeticAndVertexDistanceHaveIndependentExpectedValues() {
        var a=new TriangularFuzzyNumber(1,2,3);var b=new TriangularFuzzyNumber(2,4,6);
        assertEquals(b,a.multiply(2));assertEquals(a,b.divide(2));
        assertEquals(new TriangularFuzzyNumber(3,6,9),a.add(b));assertEquals(Math.sqrt(14.0/3),a.vertexDistance(b),1e-12);
        assertThrows(IllegalArgumentException.class,()->a.divide(0));
        assertThrows(IllegalArgumentException.class,()->new TriangularFuzzyNumber(2,1,3));
        assertThrows(IllegalArgumentException.class,()->new TriangularFuzzyNumber(0,1,Double.NaN));
        assertThrows(IllegalArgumentException.class,()->new TriangularFuzzyNumber(0,1,Double.POSITIVE_INFINITY));
    }
    @Test void normalizesBenefitAndCostAndZeroColumns() {
        var column=List.of(new TriangularFuzzyNumber(1,2,4),new TriangularFuzzyNumber(2,3,8));
        var normalizer=new CriterionNormalizer();
        assertEquals(new TriangularFuzzyNumber(.125,.25,.5),normalizer.normalize(column,FuzzyDecisionMatrix.Type.BENEFIT,1e-9).get(0));
        assertEquals(new TriangularFuzzyNumber(.25,.5,1),normalizer.normalize(column,FuzzyDecisionMatrix.Type.COST,1e-9).get(0));
        assertEquals(List.of(new TriangularFuzzyNumber(1,1,1)),normalizer.normalize(List.of(new TriangularFuzzyNumber(0,0,0)),FuzzyDecisionMatrix.Type.COST,1e-9));
    }
    @Test void topsisNumericalMatrixUsesFuzzyIdealsAndVertexDistances() {
        var criteria=List.of(new FuzzyDecisionMatrix.Criterion("benefit",FuzzyDecisionMatrix.Type.BENEFIT,.5),new FuzzyDecisionMatrix.Criterion("cost",FuzzyDecisionMatrix.Type.COST,.5));
        var matrix=new FuzzyDecisionMatrix(criteria,Map.of(
                0,List.of(new TriangularFuzzyNumber(1,2,3),new TriangularFuzzyNumber(2,3,4)),
                1,List.of(new TriangularFuzzyNumber(2,3,4),new TriangularFuzzyNumber(1,2,3)),
                2,List.of(new TriangularFuzzyNumber(1,3,4),new TriangularFuzzyNumber(1,3,4))));
        var result=new FuzzyTopsisEngine().rank(matrix,1e-9);
        assertEquals(new TriangularFuzzyNumber(.25,.375,.5),result.positiveIdeal().get(0));
        assertEquals(new TriangularFuzzyNumber(.125,1.0/6,.25),result.negativeIdeal().get(1));
        assertEquals(0,result.scores().get(0),1e-12);assertEquals(1,result.scores().get(1),1e-12);
        // Hand-derived: D+ = (1/8 + sqrt(5)/24)/sqrt(3); D- = (sqrt(2)/8 + 1/4)/sqrt(3).
        double plus=(1.0/8+Math.sqrt(5)/24)/Math.sqrt(3),minus=(Math.sqrt(2)/8+.25)/Math.sqrt(3);
        assertEquals(minus/(plus+minus),result.scores().get(2),1e-12);
        assertEquals(plus,result.distances().get(2).positive(),1e-12);
    }
    @Test void tiesColdStartEmptyAndSmallPoolsAreDeterministic() throws Exception {
        var c=config("fuzzy_topsis");var history=new SelectionHistory();var state=FairnessCreditState.initial(c.selection(),c.fuzzySelection());
        var selector=new FuzzyClientSelector();var pool=clients(4);Collections.reverse(pool);
        var decision=selector.select(pool,c,1,history,state);
        assertEquals(List.of(0,1),decision.selected().stream().map(p->p.clientId).toList());
        assertTrue(((Map<?,?>)decision.metrics().get("fuzzyTopsisScores")).values().stream().allMatch(v->(double)v==.5));
        assertTrue(selector.select(List.of(),c,1,history,state).selected().isEmpty());
        assertEquals(1,selector.select(List.of(pool.get(0)),c,1,history,state).selected().size());
        var raw=new ClientCriteriaExtractor().extract(pool,c,1,history,state);
        assertEquals(.5,raw.observations().get(0).get("reliability"));assertEquals(.5,raw.observations().get(0).get("learningUtility"));
        pool.get(0).estimatedSeconds=Double.NaN;
        assertThrows(IllegalArgumentException.class,()->selector.select(pool,c,1,history,state));
    }
    @Test void creditAccumulatesOnlyForFeasibleClientsAndRepaysSelection() throws Exception {
        var c=config("fuzzy_topsis_fair");var state=FairnessCreditState.initial(c.selection(),c.fuzzySelection());var history=new SelectionHistory();
        var scheduler=new CreditFairnessScheduler();history.observe(List.of(1,2,3,4),Set.of(1),Set.of(),1);
        scheduler.afterRound(state,c.fuzzySelection(),history,List.of(1,2,3,4),Set.of(1),1,1);
        assertEquals(0,state.deficits.get(1));assertEquals(.25,state.deficits.get(2));assertFalse(state.deficits.containsKey(99));
        history.observe(List.of(2,3,4),Set.of(2),Set.of(2),1);
        scheduler.afterRound(state,c.fuzzySelection(),history,List.of(2,3,4),Set.of(2),1,2);
        assertEquals(0,state.deficits.get(2));assertEquals(.25+1.0/3,state.deficits.get(3),1e-12);
    }
    @Test void equalOpportunityCreditAvoidsStarvationInControlledCase() throws Exception {
        var c=config("fuzzy_topsis_fair");var pool=clients(12);var state=FairnessCreditState.initial(c.selection(),c.fuzzySelection());var history=new SelectionHistory();
        Set<Integer> seen=new HashSet<>();
        for(int round=1;round<=12;round++) {
            var selected=new FuzzyClientSelector().select(pool,c,round,history,state).selected().stream().map(p->p.clientId).toList();
            seen.addAll(selected);history.observe(pool.stream().map(p->p.clientId).toList(),Set.copyOf(selected),Set.copyOf(selected),2);
            new CreditFairnessScheduler().afterRound(state,c.fuzzySelection(),history,pool.stream().map(p->p.clientId).toList(),Set.copyOf(selected),2,round);
        }
        assertEquals(12,seen.size());
    }
    @Test void adaptiveUsesCompletedOpportunityHistoryAndBoundsNextRoundLambda() throws Exception {
        var c=config("adaptive_fuzzy_topsis_fair");var state=FairnessCreditState.initial(c.selection(),c.fuzzySelection());var history=new SelectionHistory();
        new FuzzyClientSelector().select(clients(4),c,1,history,state);
        assertEquals(.30,state.currentLambda);assertNull(state.smoothedFeasibleGini);
        history.observe(List.of(0,1,2,3),Set.of(0),Set.of(),1);
        new CreditFairnessScheduler().afterRound(state,c.fuzzySelection(),history,List.of(0,1,2,3),Set.of(0),1,1);
        assertEquals(.75,state.smoothedFeasibleGini,1e-12);assertEquals(.31,state.currentLambda,1e-12);
        c.fuzzySelection().fairness.lambdaMax=.312;
        new CreditFairnessScheduler().afterRound(state,c.fuzzySelection(),history,List.of(0,1,2,3),Set.of(0),1,2);
        assertEquals(.312,state.currentLambda,1e-12);
        c.fuzzySelection().fairness.targetFeasibleGini=1;c.fuzzySelection().fairness.lambdaMin=.31;
        new CreditFairnessScheduler().afterRound(state,c.fuzzySelection(),history,List.of(0,1,2,3),Set.of(0),1,3);
        assertEquals(.31,state.currentLambda,1e-12);
    }
    @Test void quotaIsSeparateFromScoreAndNeverDuplicates() throws Exception {
        var c=config("fuzzy_topsis_fair");c.fuzzySelection().fairness.mode="credit_quota";c.fuzzySelection().fairness.fairnessQuota=1;c.check();
        var state=FairnessCreditState.initial(c.selection(),c.fuzzySelection());state.deficits.put(2,5.);
        var result=new CreditFairnessScheduler().select(Map.of(1,.9,2,.1,3,.5),state,c.fuzzySelection(),2);
        assertEquals(List.of(2,1),result.selected());assertEquals(.1,result.finalScores().get(2));
        assertEquals(result.selected().size(),new HashSet<>(result.selected()).size());
    }
    @Test void snapshotRoundTripReplaysNextDecisionAndBaselineLegacyStillReads() throws Exception {
        var c=config("adaptive_fuzzy_topsis_fair");var snapshot=new RoundCoordinator.Snapshot();
        snapshot.selectionHistory=new SelectionHistory();snapshot.fuzzySelectionState=FairnessCreditState.initial(c.selection(),c.fuzzySelection());snapshot.clients=clients(10);
        for(int round=1;round<=4;round++) {
            var decision=new FuzzyClientSelector().select(snapshot.clients,c,round,snapshot.selectionHistory,snapshot.fuzzySelectionState);
            var selected=Set.copyOf(decision.selected().stream().map(p->p.clientId).toList());
            var feasible=snapshot.clients.stream().map(p->p.clientId).toList();snapshot.selectionHistory.observe(feasible,selected,selected,2);
            new CreditFairnessScheduler().afterRound(snapshot.fuzzySelectionState,c.fuzzySelection(),snapshot.selectionHistory,feasible,selected,2,round);snapshot.round=round;
        }
        var restored=json.readValue(json.writeValueAsString(snapshot),RoundCoordinator.Snapshot.class);
        var continuous=new FuzzyClientSelector().select(snapshot.clients,c,5,snapshot.selectionHistory,snapshot.fuzzySelectionState);
        var resumed=new FuzzyClientSelector().select(restored.clients,c,5,restored.selectionHistory,restored.fuzzySelectionState);
        assertEquals(continuous.selected().stream().map(p->p.clientId).toList(),resumed.selected().stream().map(p->p.clientId).toList());
        assertEquals(continuous.metrics(),resumed.metrics());
        assertNull(json.readValue("{\"round\":2,\"clients\":[]}",RoundCoordinator.Snapshot.class).fuzzySelectionState);
    }
    @Test void configValidationRejectsInvalidWeightsAndDoubleCounting() throws Exception {
        var c=config("fuzzy_topsis_fair");c.fuzzySelection().weights.put("fairnessDeficit",.2);
        assertThrows(IllegalArgumentException.class,c::check);
        c.fuzzySelection().weights=Map.of("estimatedTime",.8,"fairnessDeficit",.2);
        assertThrows(IllegalArgumentException.class,c::check);
        c.fuzzySelection().allowFairnessDoubleCounting=true;assertDoesNotThrow(c::check);
        c.fuzzySelection().fairness.initialLambda=Double.NaN;assertThrows(IllegalArgumentException.class,c::check);
    }
    @Test void infeasibleClientNeverSelectedAndDecisionDoesNotReadEvaluation() throws Exception {
        var c=config("fuzzy_topsis_fair");var pool=clients(3);pool.get(0).ramMb=512;pool.get(1).estimatedSeconds=100.;
        var history=new SelectionHistory();var state=FairnessCreditState.initial(c.selection(),c.fuzzySelection());
        var decision=new FuzzyClientSelector().select(pool,c,1,history,state);
        assertEquals(List.of(2),decision.selected().stream().map(p->p.clientId).toList());
        // Selector accepts only profiles/history/state: no evaluation, dropout or jitter argument exists.
        assertTrue(history.clients.isEmpty());assertTrue(state.deficits.isEmpty());
        assertEquals(decision.metrics(),new FuzzyClientSelector().select(pool,c,1,history,state).metrics());
    }

    @Test void configurableUncertaintyIsBoundedAndBookkeepingRemainsExactInEveryMode() throws Exception {
        var c=config("fuzzy_topsis");var cfg=c.fuzzySelection();
        cfg.weights=Map.of("estimatedTime",.25,"reliability",.25,"fairnessDeficit",.25,"selectionStaleness",.25);
        cfg.uncertaintyFallback=.4;cfg.uncertaintyMax=.05;
        var state=FairnessCreditState.initial(c.selection(),cfg);var history=new SelectionHistory();
        for(String mode:List.of("history_based","fixed","crisp")) {
            cfg.uncertaintyMode=mode;
            var row=new ClientCriteriaExtractor().extract(clients(1),c,1,history,state).matrix().rows().get(0);
            double width=mode.equals("crisp")?0:.05;
            assertEquals(.05*(1-width),row.get(0).lower(),1e-12);
            assertEquals(.5-width,row.get(1).lower(),1e-12);
            assertEquals(row.get(2).lower(),row.get(2).upper());
            assertEquals(row.get(3).lower(),row.get(3).upper());
        }
    }

    @Test void missingAndInvalidFuzzyConfigAreRejectedAndBaselineConfigStaysOptional() throws Exception {
        var c=config("fuzzy_topsis_fair");
        var node=(ObjectNode)json.valueToTree(c);node.remove("fuzzySelection");
        assertThrows(IllegalArgumentException.class,()->json.treeToValue(node,ExperimentConfig.class).check());
        node.put("selection","random");assertDoesNotThrow(()->json.treeToValue(node,ExperimentConfig.class).check());
        c.fuzzySelection().fairness.lambdaMin=.9;assertThrows(IllegalArgumentException.class,c::check);
    }

    @Test void changingFutureDropoutAndJitterCannotAffectCurrentDecision() throws Exception {
        var c=config("adaptive_fuzzy_topsis_fair");var node=(ObjectNode)json.valueToTree(c);
        node.put("dropout",1);node.put("jitter",.9);node.put("seed",99);
        var alternate=json.treeToValue(node,ExperimentConfig.class);alternate.check();
        var pool=clients(10);var history=new SelectionHistory();var state=FairnessCreditState.initial(c.selection(),c.fuzzySelection());
        var a=new FuzzyClientSelector().select(pool,c,1,history,state);
        var b=new FuzzyClientSelector().select(pool,alternate,1,history,state);
        assertEquals(a.metrics(),b.metrics());
        assertEquals(a.selected(),b.selected());
        pool.get(0).recentTrainingLoss=Double.POSITIVE_INFINITY;
        assertThrows(IllegalArgumentException.class,()->new FuzzyClientSelector().select(pool,c,1,history,state));
    }

    @Test void replacementCountUsesRawTopsisOnSameHistoryAndCountsEachSlotOnce() throws Exception {
        var c=config("fuzzy_topsis_fair");var state=FairnessCreditState.initial(c.selection(),c.fuzzySelection());
        state.deficits.put(2,2.);
        var d=new FuzzyClientSelector().select(clients(3),c,1,new SelectionHistory(),state);
        assertEquals(List.of(0,1),d.metrics().get("topsisTopKClientIds"));
        assertEquals(List.of(2,0),d.selected().stream().map(p->p.clientId).toList());
        assertEquals(1L,d.metrics().get("slotsChangedVsTopsis"));assertEquals(.5,d.metrics().get("slotsChangedVsTopsisRatio"));
        c.fuzzySelection().fairness.initialLambda=0;state.currentLambda=0;
        var zero=new FuzzyClientSelector().select(clients(3),c,1,new SelectionHistory(),state);
        assertEquals(List.of(0,1),zero.selected().stream().map(p->p.clientId).toList());assertEquals(0L,zero.metrics().get("slotsChangedVsTopsis"));
        var empty=new FuzzyClientSelector().select(List.of(),c,1,new SelectionHistory(),state);
        assertEquals(0L,empty.metrics().get("slotsChangedVsTopsis"));assertNull(empty.metrics().get("slotsChangedVsTopsisRatio"));
    }
}
