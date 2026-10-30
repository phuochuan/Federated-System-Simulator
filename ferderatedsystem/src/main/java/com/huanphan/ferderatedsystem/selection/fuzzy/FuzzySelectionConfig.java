package com.huanphan.ferderatedsystem.selection.fuzzy;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.*;

/** Explicit settings only consumed by the new selectors. No baseline defaults are changed. */
public class FuzzySelectionConfig {
    public Map<String,Double> weights;
    public String uncertaintyMode="history_based";
    public double uncertaintyFallback=.10;
    public ObservationUncertainty observationNoise;
    public int calibrationMinHistory=5,calibrationWindow=32;
    public double calibrationQuantile=.8;
    public double calibratedWidth(java.util.List<Double> residuals) {
        if(residuals.size()<calibrationMinHistory) return Math.min(uncertaintyMax,uncertaintyFallback);
        var sorted=residuals.stream().sorted().toList();
        return Math.min(uncertaintyMax,sorted.get(Math.min(sorted.size()-1,(int)Math.ceil(calibrationQuantile*sorted.size())-1)));
    }
    public double uncertaintyScale=1;
    public double uncertaintyMax=.45;
    public double reliabilityAlpha=1,reliabilityBeta=1;
    public double learningUtilityPrior=.5;
    public double epsilon=1e-9;
    public boolean allowFairnessDoubleCounting=false;
    public Fairness fairness=new Fairness();
    public static class Fairness {
        public String mode="credit_score";
        @JsonProperty("lambda") public double initialLambda=.30;
        public double lambdaMin=0,lambdaMax=1,adaptationRate=.05,targetFeasibleGini=.55;
        public double smoothing=.8,maxUpdate=.05;
        public int fairnessQuota=0;
    }
    public static boolean isFuzzy(String method) {return method!=null&&Set.of("fuzzy_topsis","fuzzy_topsis_fair","adaptive_fuzzy_topsis_fair").contains(method);}
    public static boolean usesCredit(String method) {return isFuzzy(method)&&!method.equals("fuzzy_topsis");}
    public void check(String method) {
        if(weights==null || weights.isEmpty()) throw new IllegalArgumentException("fuzzySelection.weights is required");
        double total=0;
        for(var entry:weights.entrySet()) {
            if(!Set.of("estimatedTime","reliability","learningUtility","fairnessDeficit","selectionStaleness").contains(entry.getKey()))
                throw new IllegalArgumentException("Unknown fuzzy criterion: "+entry.getKey());
            if(entry.getValue()==null) throw new IllegalArgumentException("Null fuzzy weight");
            nonnegative(entry.getValue());total+=entry.getValue();
        }
        if(!Double.isFinite(total)||Math.abs(total-1)>1e-9) throw new IllegalArgumentException("Fuzzy weights must sum to one");
        if(uncertaintyMode==null||!Set.of("history_based","fixed","crisp","error_calibrated").contains(uncertaintyMode)) throw new IllegalArgumentException("Unknown uncertaintyMode");
        unit(uncertaintyFallback);unit(uncertaintyMax);positive(uncertaintyScale);positive(reliabilityAlpha);positive(reliabilityBeta);
        unit(learningUtilityPrior);positive(epsilon);
        positive(reliabilityAlpha+reliabilityBeta);
        if(uncertaintyFallback>=1 || uncertaintyMax>=1 || epsilon>=1) throw new IllegalArgumentException("Uncertainty and epsilon must be <1");
        if(observationNoise!=null) observationNoise.check();
        unit(calibrationQuantile);
        if(calibrationQuantile<=0 || calibrationMinHistory<2 || calibrationWindow<calibrationMinHistory || calibrationWindow>256)
            throw new IllegalArgumentException("Invalid calibration history/quantile");
        if(fairness==null) throw new IllegalArgumentException("fairness settings required");
        var f=fairness;
        if(f.mode==null||!Set.of("credit_score","credit_quota").contains(f.mode)) throw new IllegalArgumentException("Unknown fairness mode");
        nonnegative(f.initialLambda);nonnegative(f.lambdaMin);nonnegative(f.lambdaMax);positive(f.adaptationRate);
        unit(f.targetFeasibleGini);unit(f.smoothing);positive(f.maxUpdate);
        if(f.lambdaMin>f.initialLambda || f.initialLambda>f.lambdaMax || f.smoothing>=1)
            throw new IllegalArgumentException("Invalid lambda bounds/smoothing");
        if(f.fairnessQuota<0 || (f.mode.equals("credit_score")&&f.fairnessQuota!=0) || (f.mode.equals("credit_quota")&&f.fairnessQuota<1))
            throw new IllegalArgumentException("Quota must be positive only in credit_quota mode");
        if("adaptive_fuzzy_topsis_fair".equals(method)&&!f.mode.equals("credit_score")) throw new IllegalArgumentException("Adaptive weighting requires credit_score mode");
        if(usesCredit(method)&&!allowFairnessDoubleCounting && (weights.getOrDefault("fairnessDeficit",0.)>0 || weights.getOrDefault("selectionStaleness",0.)>0))
            throw new IllegalArgumentException("Fairness criteria plus scheduler require explicit allowFairnessDoubleCounting ablation");
    }
    static void unit(double value) {nonnegative(value);if(value>1) throw new IllegalArgumentException("Expected value in [0,1]");}
    static void positive(double value) {if(!Double.isFinite(value)||value<=0) throw new IllegalArgumentException("Expected finite positive value");}
    static void nonnegative(double value) {if(!Double.isFinite(value)||value<0) throw new IllegalArgumentException("Expected finite nonnegative value");}
}
