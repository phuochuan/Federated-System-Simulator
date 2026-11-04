package com.huanphan.ferderatedsystem.selection.fuzzy;

import java.util.*;

/** Scheduler boundary: a future Lyapunov implementation can replace credit without replacing TOPSIS. */
public interface FairnessScheduler {
    record Decision(List<Integer> selected,Map<Integer,Double> normalizedDeficits,Map<Integer,Double> finalScores,List<Integer> quotaIds) {}
    Decision select(Map<Integer,Double> closeness,FairnessCreditState state,FuzzySelectionConfig settings,int k);
    void afterRound(FairnessCreditState state,FuzzySelectionConfig settings,SelectionHistory history,
                    Collection<Integer> feasible,Set<Integer> selected,int k,int round);
}
