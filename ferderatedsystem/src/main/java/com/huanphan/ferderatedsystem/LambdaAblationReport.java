package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
import static com.huanphan.ferderatedsystem.ControlledExperiments.*;

/** Descriptive, paired lambda-policy outcomes. Reporting metrics never feed selection or tuning. */
final class LambdaAblationReport {
    static final List<String> METRICS=List.of("accuracy","macroF1","accuracyTailMean","accuracyTailSd","macroF1TailSd",
            "maxAccuracyDropPp","finalAccuracyChangePp","coverage","ramFeasibleCoverage","feasibleSelectionCoverage",
            "feasibleCompletionCoverage","feasibleOpportunityAdjustedGini","ramFeasibleCompletionGini",
            "maxFeasibleSelectionStaleness","meanFeasibleSelectionStaleness","acceptedSelectedRatio",
            "virtualSeconds","virtualSecondsWithSelector","wallSeconds","selectorSeconds","fairnessUpdateSeconds",
            "slotsChangedVsTopsis","slotsChangedVsTopsisRatio","meanAppliedLambda");

    private LambdaAblationReport() {}

    static String render(String source,List<Long> seeds,List<Double> targets,int window,Map<Row,List<RunResult>> runs,Exception failure) {
        boolean complete=failure==null&&LAMBDA_ROWS.stream().allMatch(row->runs.get(row).size()==seeds.size());
        var out=new StringBuilder("L: FIXED LAMBDA ABLATION\nStatus: "+(complete?"COMPLETED":"INCOMPLETE")+"\n");
        out.append("Question: Does adaptive feedback improve the trade-off beyond fixed fairness coefficients? Either outcome is valid.\n")
                .append("Config: ").append(source).append("\nSeeds: ").append(seeds).append("\n")
                .append("Only selection method and configured initial lambda may differ. Engine/criteria/uncertainty/credit rule/training/aggregation/partition/scenario are controlled.\n")
                .append("L0: pure TOPSIS, applied lambda=0 (no credit scheduler); L1-L4: fixed credit score; L5: adaptive feedback.\n")
                .append("Tail window is predeclared: last min(").append(window).append(", completed rounds) rounds. Sample SD requires >=2 observations; otherwise N/A.\n")
                .append("accuracyTailSd and macroF1TailSd are within-run variability in ratio units; summary SD is across-seed sample SD. Tail mean never replaces final accuracy.\n")
                .append("maxAccuracyDropPp: largest positive consecutive-round accuracy decrease; initial evaluation excluded. finalAccuracyChangePp: last minus penultimate, in percentage points.\n")
                .append("slotsChangedVsTopsis = selected slots absent from raw-CC Top-K on THE SAME pre-round history, counting replacements once. Ratio uses total selected slots, not requested K*rounds.\n")
                .append("This is a factual-state ranking contrast, not a counterfactual full training trajectory without credit.\n")
                .append("coverage is population completion coverage; feasibleSelectionCoverage and feasibleCompletionCoverage use valid opportunity populations. LOW RAM-impossible clients are excluded only from conditional denominators.\n")
                .append("virtualSeconds excludes selector/bookkeeping; virtualSecondsWithSelector includes both. Measured training times may change ranking and estimated candidate pools despite identical exogenous traces.\n")
                .append("No monotonic coverage assumption, best-checkpoint selection, significance, equivalence or adaptive-superiority claim. Test metrics are reporting only; tune on separate validation.\n");
        if(failure!=null) out.append("ERROR: ").append(failure).append("\n");
        for(var row:LAMBDA_ROWS) {
            out.append("\n=== ").append(row).append(" RUNS ===\n");
            for(var run:runs.get(row)) {
                var c=run.config();var snap=run.experiment().path("snapshot");
                out.append("seed=").append(c.seed()).append(" experiment=").append(c.experimentId()).append(" selection=").append(c.selection())
                        .append(" initialLambda=").append(c.fuzzySelection().fairness.initialLambda).append(" rounds=").append(c.rounds())
                        .append(" tailObservations=").append(Math.min(window,run.rounds().size())).append("\n")
                        .append(" manifest=").append(c.manifestPath()).append(" dataSeed=").append(snap.path("manifest").path("seed"))
                        .append(" alpha=").append(snap.path("manifest").path("alpha"))
                        .append(" initialModelHash=").append(snap.path("initialModelStateHash"))
                        .append(" scenarioHash=").append(snap.path("scenarioTraceHash")).append("\n");
                for(String metric:METRICS) out.append(" ").append(metric).append("=").append(format(value(run,metric,window)));
                out.append("\n perClassRecall=").append(run.result().path("evaluation").path("perClassRecall"))
                        .append("\n appliedLambdaFirst/Last/Next=").append(run.rounds().get(0).path("currentFairnessLambda")).append("/")
                        .append(run.result().path("currentFairnessLambda")).append("/").append(run.result().path("nextFairnessLambda")).append("\n");
            }
        }
        if(!complete) return out.append("\nNo final comparison: incomplete batch. Completed runs above remain available as evidence.\n").toString();
        out.append("\nSUMMARY: MEAN +/- SAMPLE SD ACROSS SEEDS\n");
        for(String metric:METRICS) {
            out.append(metric);
            for(var row:LAMBDA_ROWS) out.append(" | ").append(row).append(": ").append(ComparisonReport.stats(runs.get(row).stream().map(r->value(r,metric,window)).toList()));
            out.append("\n");
        }
        // Every fixed policy vs adaptive, and every nonzero fixed policy vs pure TOPSIS.
        List<Row[]> pairs=new ArrayList<>();
        for(var row:LAMBDA_ROWS) if(row!=Row.L5) pairs.add(new Row[]{row,Row.L5});
        for(var row:List.of(Row.L1,Row.L2,Row.L3,Row.L4)) pairs.add(new Row[]{Row.L0,row});
        for(var pair:pairs) {
            out.append("\n=== ").append(pair[0]).append(" VS ").append(pair[1]).append(" ===\nPAIRED DIFFERENCES: RIGHT MINUS LEFT\n");
            var left=runs.get(pair[0]);var right=runs.get(pair[1]);
            for(String metric:METRICS) {
                List<Double> diffs=new ArrayList<>();out.append(metric);
                for(int i=0;i<seeds.size();i++) {
                    if(left.get(i).config().seed()!=seeds.get(i)||right.get(i).config().seed()!=seeds.get(i)) throw new IllegalStateException("Unpaired seed order");
                    double delta=value(right.get(i),metric,window)-value(left.get(i),metric,window);diffs.add(delta);
                    out.append(" seed=").append(seeds.get(i)).append(":").append(format(delta));
                }
                out.append(" | meanDelta +/- sampleSD = ").append(ComparisonReport.stats(diffs)).append("\n");
            }
            for(int i=0;i<seeds.size();i++) {
                var a=left.get(i);var b=right.get(i);int changed=0;
                for(int r=0;r<a.rounds().size();r++) if(!a.rounds().get(r).path("estimatedFeasibleIds").equals(b.rounds().get(r).path("estimatedFeasibleIds"))) changed++;
                out.append("seed=").append(seeds.get(i)).append(" roundsWithDifferentEstimatedCandidateSets=").append(changed).append("\n");
            }
        }
        out.append("\nTIME TO TARGET: FIRST CROSSING AND SUSTAINED THROUGH FINAL ROUND\n");
        for(var row:LAMBDA_ROWS) for(var run:runs.get(row)) for(double target:targets) {
            var time=ComparisonReport.targetTime(run,target);int sustained=ComparisonReport.sustainedFromRound(run,target);
            out.append(row).append(" seed=").append(run.config().seed()).append(" target=").append(target)
                    .append(" first=").append(time.reached()?"round="+time.round()+" virtual="+time.virtual()+" wall="+time.wall():"NOT_REACHED")
                    .append(" sustainedFrom=").append(sustained<0?"NOT_SUSTAINED":sustained).append("\n");
        }
        out.append("\nPARETO INTERPRETATION: compare accuracy/Macro-F1/coverage upward; Gini/staleness/instability/time downward. Paired estimates do not establish equality or superiority.\n")
                .append("If a fixed policy matches adaptive coverage/Gini and learning outcomes, adaptive feedback's added value is not established by this batch.\n")
                .append("This batch has ONE fixed partition; repeat the full protocol on additional partition manifests and report each separately before cross-partition claims.\n");
        if(seeds.size()<3) out.append("SMOKE TEST ONLY: fewer than three seeds; not research evidence.\n");
        return out.toString();
    }

    static double value(RunResult run,String metric,int window) {
        var rounds=run.rounds();var tail=rounds.subList(Math.max(0,rounds.size()-window),rounds.size());
        return switch(metric) {
            case "accuracyTailMean" -> tail.stream().mapToDouble(r->number(r.path("evaluation").path("accuracy"))).average().orElse(Double.NaN);
            case "accuracyTailSd","macroF1TailSd" -> sampleSd(tail.stream().mapToDouble(r->number(r.path("evaluation").path(metric.equals("accuracyTailSd")?"accuracy":"macroF1"))).toArray());
            case "maxAccuracyDropPp" -> {
                if(rounds.size()<2) yield Double.NaN;
                double largest=0;for(int i=1;i<rounds.size();i++) largest=Math.max(largest,accuracy(rounds.get(i-1))-accuracy(rounds.get(i)));
                yield largest*100;
            }
            case "finalAccuracyChangePp" -> rounds.size()<2?Double.NaN:100*(accuracy(rounds.get(rounds.size()-1))-accuracy(rounds.get(rounds.size()-2)));
            case "slotsChangedVsTopsis" -> rounds.stream().mapToDouble(r->number(r.path("slotsChangedVsTopsis"))).sum();
            case "slotsChangedVsTopsisRatio" -> {
                double selected=rounds.stream().mapToInt(r->r.path("selectedIds").size()).sum();
                yield selected==0?Double.NaN:value(run,"slotsChangedVsTopsis",window)/selected;
            }
            case "meanAppliedLambda" -> rounds.stream().mapToDouble(r->number(r.path("currentFairnessLambda"))).average().orElse(Double.NaN);
            default -> ComparisonReport.value(run,metric);
        };
    }
    private static double accuracy(JsonNode round) {return number(round.path("evaluation").path("accuracy"));}
    private static double number(JsonNode v) {
        if(!v.isNumber()||!Double.isFinite(v.asDouble())) throw new IllegalStateException("Missing/invalid ablation metric: "+v);
        return v.asDouble();
    }
    private static double sampleSd(double[] values) {
        if(values.length<2) return Double.NaN;
        double mean=Arrays.stream(values).average().orElseThrow();
        return Math.sqrt(Arrays.stream(values).map(v->(v-mean)*(v-mean)).sum()/(values.length-1));
    }
    private static String format(double value) {return Double.isFinite(value)?String.format(Locale.ROOT,"%.6f",value):"N/A";}
}
