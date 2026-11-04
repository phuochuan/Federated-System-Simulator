package com.huanphan.ferderatedsystem.selection.fuzzy;

import java.util.*;

/** Diagnostics of valid opportunities; separate from baseline algorithm state. Serialized in snapshots. */
public class SelectionHistory {
    public int startRound=1;
    public Map<Integer,Account> clients=new TreeMap<>();
    public static class Account {
        public int opportunities,selections,completions,feasibleStaleness;
        public double entitlement;
    }
    public Account prior(int id) {return clients.getOrDefault(id,new Account());}
    public void observe(Collection<Integer> feasible,Set<Integer> selected,Set<Integer> accepted,int k) {
        double share=feasible.isEmpty()?0:Math.min(k,feasible.size())/(double)feasible.size();
        for(int id:feasible) {
            var a=clients.computeIfAbsent(id,ignored->new Account());a.opportunities++;a.entitlement+=share;
            if(selected.contains(id)) {a.selections++;a.feasibleStaleness=0;} else a.feasibleStaleness++;
            if(accepted.contains(id)) a.completions++;
        }
    }
    public static double gini(double[] values) {
        if(Arrays.stream(values).anyMatch(v->!Double.isFinite(v)||v<0)) throw new IllegalArgumentException("Invalid fairness observation");
        var sorted=values.clone();Arrays.sort(sorted);double sum=Arrays.stream(sorted).sum(),numerator=0;
        for(int i=0;i<sorted.length;i++) numerator+=(2.0*(i+1)-sorted.length-1)*sorted[i];
        return sum==0?0:numerator/(sorted.length*sum);
    }
    public Map<String,Object> metrics() {
        var observed=clients.values().stream().filter(a->a.opportunities>0).toList();
        Map<String,Object> metrics=new LinkedHashMap<>();metrics.put("feasibleHistoryStartRound",startRound);
        metrics.put("feasibleOpportunityPopulation",observed.size());
        metrics.put("feasibleSelectionCoverage",observed.isEmpty()?null:observed.stream().filter(a->a.selections>0).count()/(double)observed.size());
        metrics.put("feasibleCompletionCoverage",observed.isEmpty()?null:observed.stream().filter(a->a.completions>0).count()/(double)observed.size());
        metrics.put("feasibleOpportunityAdjustedGini",observed.isEmpty()?null:gini(observed.stream().mapToDouble(a->a.selections/(double)a.opportunities).toArray()));
        metrics.put("feasibleCompletionOpportunityAdjustedGini",observed.isEmpty()?null:gini(observed.stream().mapToDouble(a->a.completions/(double)a.opportunities).toArray()));
        metrics.put("maxFeasibleSelectionStaleness",observed.stream().mapToInt(a->a.feasibleStaleness).max().orElse(0));
        metrics.put("meanFeasibleSelectionStaleness",observed.stream().mapToInt(a->a.feasibleStaleness).average().orElse(0));
        return metrics;
    }
}
