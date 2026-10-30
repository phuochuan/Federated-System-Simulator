package com.huanphan.ferderatedsystem.selection.fuzzy;

import com.huanphan.ferderatedsystem.*;
import java.util.*;

public final class FuzzyClientSelector {
    public record Decision(List<ClientProfile> selected,Map<String,Object> metrics) {}
    public Decision select(List<ClientProfile> eligible,ExperimentConfig c,int round,SelectionHistory history,FairnessCreditState state) {
        state.check(c.selection(),round-1,c.fuzzySelection());
        for(var p:eligible) {FuzzySelectionConfig.nonnegative(p.estimate(c));FuzzySelectionConfig.positive(p.ramMb);FuzzySelectionConfig.positive(p.cpu);}
        var feasible=Policies.feasibleClients(eligible,c,round);
        var extracted=new ClientCriteriaExtractor().extract(feasible,c,round,history,state);
        var ranked=new FuzzyTopsisEngine().rank(extracted.matrix(),c.fuzzySelection().epsilon);
        var scheduled=new CreditFairnessScheduler().select(ranked.scores(),state,c.fuzzySelection(),Math.min(c.selectedPerRound(),feasible.size()));
        var byId=new HashMap<Integer,ClientProfile>();feasible.forEach(p->byId.put(p.clientId,p));
        Map<String,Object> metrics=new LinkedHashMap<>();
        metrics.put("fuzzyTopsisScores",ranked.scores());metrics.put("fairnessCredits",Map.copyOf(state.deficits));
        metrics.put("normalizedFairnessDeficits",scheduled.normalizedDeficits());metrics.put("finalSelectionScores",scheduled.finalScores());
        metrics.put("currentFairnessLambda",state.currentLambda);metrics.put("fairnessQuotaIds",scheduled.quotaIds());
        metrics.put("fairnessMode",FuzzySelectionConfig.usesCredit(c.selection())?c.fuzzySelection().fairness.mode:"none");
        metrics.put("criteriaObservations",extracted.observations());metrics.put("fuzzyDecisionMatrix",extracted.matrix());metrics.put("fuzzyTopsisDetails",ranked);
        metrics.put("selectorVersion",state.version);
        var topsisTopK=ranked.scores().keySet().stream().sorted(Comparator.<Integer>comparingDouble(ranked.scores()::get).reversed()
                .thenComparingInt(Integer::intValue)).limit(scheduled.selected().size()).toList();
        var original=new HashSet<>(topsisTopK);
        long changed=scheduled.selected().stream().filter(id->!original.contains(id)).count();
        metrics.put("topsisTopKClientIds",topsisTopK);metrics.put("slotsChangedVsTopsis",changed);
        metrics.put("slotsChangedVsTopsisRatio",scheduled.selected().isEmpty()?null:changed/(double)scheduled.selected().size());
        return new Decision(scheduled.selected().stream().map(byId::get).toList(),metrics);
    }
}
