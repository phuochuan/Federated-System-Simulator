package com.huanphan.ferderatedsystem.selection.fuzzy;

import java.util.*;

public final class CreditFairnessScheduler implements FairnessScheduler {
    public Decision select(Map<Integer,Double> cc,FairnessCreditState state,FuzzySelectionConfig settings,int k) {
        boolean credit=FuzzySelectionConfig.usesCredit(state.method);
        double max=cc.keySet().stream().mapToDouble(id->state.deficits.getOrDefault(id,0.)).max().orElse(0);
        Map<Integer,Double> normalized=new TreeMap<>(),scores=new TreeMap<>();
        for(var entry:cc.entrySet()) {
            double q=credit&&max>0?state.deficits.getOrDefault(entry.getKey(),0.)/max:0;
            normalized.put(entry.getKey(),q);scores.put(entry.getKey(),entry.getValue()+(credit&&settings.fairness.mode.equals("credit_score")?state.currentLambda*q:0));
        }
        Comparator<Integer> scoreOrder=Comparator.<Integer>comparingDouble(scores::get).reversed().thenComparingInt(Integer::intValue);
        List<Integer> selected=new ArrayList<>(),quotaIds=new ArrayList<>();
        if(credit&&settings.fairness.mode.equals("credit_quota")) {
            quotaIds=cc.keySet().stream().sorted(Comparator.<Integer>comparingDouble(id->state.deficits.getOrDefault(id,0.)).reversed().thenComparingInt(Integer::intValue))
                    .limit(Math.min(k,settings.fairness.fairnessQuota)).toList();selected.addAll(quotaIds);
        }
        Set<Integer> reserved=new HashSet<>(selected);
        selected.addAll(cc.keySet().stream().filter(id->!reserved.contains(id)).sorted(scoreOrder).limit(Math.max(0,k-selected.size())).toList());
        return new Decision(List.copyOf(selected),Collections.unmodifiableMap(normalized),Collections.unmodifiableMap(scores),List.copyOf(quotaIds));
    }
    public void afterRound(FairnessCreditState state,FuzzySelectionConfig settings,SelectionHistory history,
                           Collection<Integer> feasible,Set<Integer> selected,int k,int round) {
        if(FuzzySelectionConfig.usesCredit(state.method)) {
            double share=feasible.isEmpty()?0:Math.min(k,feasible.size())/(double)feasible.size();
            for(int id:feasible) state.deficits.put(id,Math.max(0,state.deficits.getOrDefault(id,0.)+share-(selected.contains(id)?1:0)));
            if(state.method.equals("adaptive_fuzzy_topsis_fair")&&!history.clients.isEmpty()) {
                var observed=history.clients.values().stream().filter(a->a.opportunities>0).toList();
                if(!observed.isEmpty()) {
                    double gini=SelectionHistory.gini(observed.stream().mapToDouble(a->a.selections/(double)a.opportunities).toArray());
                    double smoothed=state.smoothedFeasibleGini==null?gini:settings.fairness.smoothing*state.smoothedFeasibleGini+(1-settings.fairness.smoothing)*gini;
                    state.smoothedFeasibleGini=smoothed;
                    double delta=Math.max(-settings.fairness.maxUpdate,Math.min(settings.fairness.maxUpdate,settings.fairness.adaptationRate*(smoothed-settings.fairness.targetFeasibleGini)));
                    state.currentLambda=Math.max(settings.fairness.lambdaMin,Math.min(settings.fairness.lambdaMax,state.currentLambda+delta));
                }
            }
        }
        state.lastCommittedRound=round;
    }
}
