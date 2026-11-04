package com.huanphan.ferderatedsystem.selection.fuzzy;

import java.util.*;

/** No static scheduler state: only the committed Snapshot owns this object. */
public class FairnessCreditState {
    public static final String VERSION="fuzzy-topsis-credit-v1";
    public String version=VERSION,method;
    public int lastCommittedRound;
    public double currentLambda;
    public Double smoothedFeasibleGini;
    public Map<Integer,Double> deficits=new TreeMap<>();
    public static FairnessCreditState initial(String method,FuzzySelectionConfig config) {
        var state=new FairnessCreditState();state.method=method;
        state.currentLambda=FuzzySelectionConfig.usesCredit(method)?config.fairness.initialLambda:0;
        return state;
    }
    public void check(String expected,int round,FuzzySelectionConfig config) {
        if(!VERSION.equals(version)||!expected.equals(method)||lastCommittedRound!=round) throw new IllegalStateException("Fuzzy selector snapshot method/version/round mismatch");
        FuzzySelectionConfig.nonnegative(currentLambda);
        if(FuzzySelectionConfig.usesCredit(method)&&(currentLambda<config.fairness.lambdaMin||currentLambda>config.fairness.lambdaMax))
            throw new IllegalStateException("Persisted lambda outside configured bounds");
        if(smoothedFeasibleGini!=null) FuzzySelectionConfig.unit(smoothedFeasibleGini);
        if(!FuzzySelectionConfig.usesCredit(method)&&(currentLambda!=0||!deficits.isEmpty()||smoothedFeasibleGini!=null))
            throw new IllegalStateException("Pure Fuzzy TOPSIS snapshot must not contain scheduler credit or feedback");
        deficits.values().forEach(FuzzySelectionConfig::nonnegative);
    }
}
