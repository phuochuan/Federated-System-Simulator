package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
import static com.huanphan.ferderatedsystem.ControlledExperiments.RunResult;

/** Báo cáo từ evidence đã commit; không tự tạo số đo hoặc tuyên bố ý nghĩa thống kê. */
final class ComparisonReport {
    static final List<String> METRICS=List.of("accuracy","macroF1","loss","worstClassRecall","virtualSeconds",
            "wallSeconds","coverage","ramFeasibleCoverage","estimatedFeasibleCoverage","ramFeasiblePopulation","estimatedFeasiblePopulation",
            "participationGini","acceptedUpdates","selectedClients","acceptedSelectedRatio","proxySeconds","proxyWallSeconds",
            "weightSeconds","aggregationSeconds","serverOverheadSeconds","logicalModelBytesDispatched","logicalUpdateBytesAccepted",
            "selectorSeconds","fairnessUpdateSeconds","virtualSecondsWithSelector","feasibleSelectionCoverage","feasibleCompletionCoverage",
            "selectionGini","completionGini","ramFeasibleCompletionGini","feasibleOpportunityAdjustedGini",
            "feasibleCompletionOpportunityAdjustedGini",
            "maxFeasibleSelectionStaleness","meanFeasibleSelectionStaleness");
    private ComparisonReport() {}

    static String render(String question,String changedField,String source,List<Long> seeds,List<Double> targets,
                         List<RunResult> left,List<RunResult> right,Exception failure) {
        boolean complete=failure==null && left.size()==seeds.size() && right.size()==seeds.size();
        StringBuilder out=new StringBuilder();
        out.append("CONTROLLED EXPERIMENT COMPARISON\nQuestion: ").append(question)
                .append("\nStatus: ").append(complete?"COMPLETED":"INCOMPLETE")
                .append("\nChanged factor: ").append(changedField).append("\nMatrix config: ").append(source)
                .append("\nTraining/selection seeds: ").append(seeds)
                .append("\nDataset partitions are fixed across these seeds; dataset seed is stored in each manifest.")
                .append("\nRatios use scale 0..1. Differences below are RIGHT minus LEFT.")
                .append("\nSD is sample standard deviation across seeds (n-1), not a confidence interval.")
                .append("\nWall seconds = sum of round wall times, including test evaluation, excluding initialization.")
                .append("\nVirtual seconds include proxy wall time + weight calculation + aggregation, exclude observer test evaluation.")
                .append("\nCommunication cost = NOT_MODELED. Logical payload counts measure dense tensor bytes, not WAN traffic/latency.")
                .append("\nRAM-feasible coverage uses a static common RAM denominator; estimated-feasible coverage also uses availability/deadline estimates and can be policy-dependent.")
                .append("\nShared traces are indexed by round/client, not by absolute virtual time. Job durations/deadline outcomes may differ.\n");
        out.append("Selector overhead: shared feasibility diagnostics + policy decision, measured consistently for every policy. Fairness bookkeeping is measured separately.\n")
                .append("virtualSeconds excludes selector/bookkeeping; virtualSecondsWithSelector includes both. N/A means unavailable legacy metric or empty denominator.\n")
                .append("Selection/completion Gini are population metrics; RAM/feasible-opportunity metrics exclude permanently impossible clients. Candidate sets may diverge with policy-specific timing histories.\n");
        if(failure!=null) out.append("\nERROR: ").append(failure).append("\nNo final comparison conclusion is produced for an incomplete pair.\n");
        appendRuns(out,"LEFT",left,targets);appendRuns(out,"RIGHT",right,targets);
        if(!complete) return out.toString();
        String a=left.get(0).row().name(),b=right.get(0).row().name();
        out.append("\nSUMMARY (mean +/- sample SD across ").append(seeds.size()).append(" seeds)\n");
        out.append(String.format(Locale.ROOT,"%-23s %-27s %-27s %-27s%n","Metric",a,b,b+" - "+a+" (paired)"));
        for(String metric:METRICS) {
            List<Double> first=new ArrayList<>(),second=new ArrayList<>(),deltas=new ArrayList<>();
            for(int i=0;i<seeds.size();i++) {
                double av=value(left.get(i),metric),bv=value(right.get(i),metric);
                first.add(av);second.add(bv);deltas.add(bv-av);
            }
            out.append(String.format(Locale.ROOT,"%-23s %-27s %-27s %-27s%n",metric,stats(first),stats(second),stats(deltas)));
        }
        out.append("\nPAIRED DIFFERENCES BY SEED (all metrics, right minus left)\n");
        for(int i=0;i<seeds.size();i++) {
            out.append("seed=").append(seeds.get(i));
            for(String metric:METRICS) out.append(" ").append(metric).append("=").append(format(value(right.get(i),metric)-value(left.get(i),metric)));
            int changedPools=0;
            for(int round=0;round<Math.min(left.get(i).rounds().size(),right.get(i).rounds().size());round++)
                if(!left.get(i).rounds().get(round).path("estimatedFeasibleIds").equals(right.get(i).rounds().get(round).path("estimatedFeasibleIds"))) changedPools++;
            out.append("\n  roundsWithDifferentEstimatedCandidateSets=").append(changedPools)
                    .append(" (same exogenous trace; observed training-time histories can change deadline feasibility)\n");
        }
        out.append("\nPAIRED QUALITY DIFFERENCES (percentage points)\n");
        for(int i=0;i<seeds.size();i++) out.append(String.format(Locale.ROOT,
                "seed=%d  deltaAccuracy=%+.4f pp  deltaMacroF1=%+.4f pp  deltaVirtualSeconds=%+.4f%n",seeds.get(i),
                100*(value(right.get(i),"accuracy")-value(left.get(i),"accuracy")),
                100*(value(right.get(i),"macroF1")-value(left.get(i),"macroF1")),
                value(right.get(i),"virtualSeconds")-value(left.get(i),"virtualSeconds")));
        out.append("\nMEAN RECALL PER CLASS (labels 0..6)\n");
        for(int label=0;label<7;label++) {
            final int index=label;
            double av=left.stream().mapToDouble(r->recall(r,index)).average().orElseThrow();
            double bv=right.stream().mapToDouble(r->recall(r,index)).average().orElseThrow();
            out.append(String.format(Locale.ROOT,"class=%d %s=%.6f %s=%.6f delta=%+.4f pp%n",label,a,av,b,bv,100*(bv-av)));
            List<Double> ar=new ArrayList<>(),br=new ArrayList<>(),dr=new ArrayList<>();
            for(int i=0;i<seeds.size();i++) {ar.add(recall(left.get(i),index));br.add(recall(right.get(i),index));dr.add(br.get(i)-ar.get(i));}
            out.append("  sample statistics: ").append(a).append("=").append(stats(ar)).append(" ").append(b).append("=").append(stats(br))
                    .append(" pairedDelta=").append(stats(dr)).append(" pairedBySeed=").append(dr).append("\n");
        }
        appendTargets(out,targets,left,right);
        double deltaF1=right.stream().mapToDouble(r->value(r,"macroF1")).average().orElseThrow()
                -left.stream().mapToDouble(r->value(r,"macroF1")).average().orElseThrow();
        out.append("\nOBSERVED COMPARISON\n");
        out.append(String.format(Locale.ROOT,"%s has %s mean Macro-F1 than %s by %.4f percentage points.%n",b,
                Math.abs(deltaF1)<1e-12?"the same":deltaF1>0?"higher":"lower",a,Math.abs(deltaF1)*100));
        out.append("Compare virtual time, class recall and coverage as separate trade-offs; no single overall winner is inferred.\n");
        if(seeds.size()<3) out.append("SMOKE TEST ONLY: fewer than three seeds do not establish repeatability or superiority.\n");
        else out.append("This is an exploratory comparison on the listed seeds and fixed partitions, not a statistical significance claim.\n");
        out.append("Test metrics are for reporting; do not choose hyperparameters or the best checkpoint using these test results.\n");
        return out.toString();
    }

    private static void appendRuns(StringBuilder out,String side,List<RunResult> runs,List<Double> targets) {
        out.append("\n").append(side).append(" RUNS\n");
        for(var run:runs) {
            var c=run.config();var snapshot=run.experiment().path("snapshot");
            String commit=snapshot.path("gitCommit").asText("unknown");
            boolean provenanceKnown=!commit.isBlank() && !commit.equals("unknown");
            out.append("\nrow=").append(run.row()).append(" seed=").append(c.seed()).append(" experimentId=").append(c.experimentId())
                    .append("\narchitecture=").append(c.architecture()).append(" manifest=").append(c.manifestPath())
                    .append(" aggregation=").append(c.aggregation()).append(" selection=").append(c.selection())
                    .append("\n  dataset=").append(snapshot.path("manifest").path("dataset").asText())
                    .append(" dataSeed=").append(snapshot.path("manifest").path("seed").asText())
                    .append(" partition=").append(snapshot.path("manifest").path("strategy").asText())
                    .append(" alpha=").append(snapshot.path("manifest").path("alpha").asText())
                    .append("\nround=").append(run.result().path("roundId")).append(" outcome=").append(run.result().path("outcome").asText());
            for(String metric:METRICS) out.append("\n  ").append(metric).append("=").append(format(value(run,metric)));
            out.append("\n  scenarioTraceHash=").append(snapshot.path("scenarioTraceHash").asText())
                    .append("\n  initialModelStateHash=").append(snapshot.path("initialModelStateHash").asText())
                    .append("\n  initializationMethod=").append(snapshot.path("initializationMethod").asText())
                    .append(" initializationSeed=").append(snapshot.path("initializationSeed").asText());
            if(c.fuzzySelection()!=null) out.append("\n  fuzzyWeights=").append(c.fuzzySelection().weights)
                    .append(" uncertaintyMode=").append(c.fuzzySelection().uncertaintyMode)
                    .append(" fairnessMode=").append(c.fuzzySelection().fairness.mode)
                    .append(" initialLambda=").append(c.fuzzySelection().fairness.initialLambda);
            if(run.result().has("currentFairnessLambda")) out.append("\n  finalRoundAppliedLambda=").append(run.result().get("currentFairnessLambda"))
                    .append(" nextLambda=").append(run.result().path("nextFairnessLambda"));
            for(double threshold:targets) {
                var timing=targetTime(run,threshold);
                out.append("\n  threshold=").append(threshold).append(" timeToTarget=")
                        .append(timing.reached()?String.format(Locale.ROOT,"firstCrossingRound=%d virtualSeconds=%.6f wallSeconds=%.6f",timing.round(),timing.virtual(),timing.wall()):"NOT_REACHED")
                        .append(" sustainedFromRound=").append(sustainedFromRound(run,threshold)<0?"NOT_SUSTAINED":sustainedFromRound(run,threshold));
                if(timing.reached()) out.append(" virtualWithSelector=").append(timing.round()==0?"0":format(optionalNumber(run.rounds().get(timing.round()-1).path("cumulativeVirtualSecondsWithSelector"))));
            }
            JsonNode target=snapshot.path("timeToTargetSeconds");
            out.append("\n  targetAccuracy=").append(c.targetAccuracy()).append(" timeToTargetSeconds=")
                    .append(target.isNumber()?target.asText():"NOT_REACHED")
                    .append("\n  perClassRecall=").append(run.result().path("evaluation").path("perClassRecall"))
                    .append("\n  perClassPrecision=").append(run.result().path("evaluation").path("perClassPrecision"))
                    .append("\n  confusionMatrix=").append(run.result().path("evaluation").path("confusionMatrix"))
                    .append("\n  checkpoint=").append(snapshot.path("checkpointPath").asText())
                    .append("\n  gitCommit=").append(provenanceKnown?commit:"UNKNOWN")
                    .append(" gitDirty=").append(provenanceKnown?Boolean.toString(snapshot.path("gitDirty").asBoolean()):"UNKNOWN").append("\n");
        }
        if(!runs.isEmpty()) {
            var c=runs.get(0).config();
            out.append("\nShared setup for ").append(side).append(": rounds=").append(c.rounds()).append(" clients=").append(c.totalClients())
                    .append(" K=").append(c.selectedPerRound()).append(" localEpochs=").append(c.localEpochs())
                    .append(" batchSize=").append(c.batchSize()).append(" learningRate=").append(c.learningRate())
                    .append(" simulationEnabled=").append(c.simulationEnabled()).append(" resourceProfile=").append(c.resourceProfile())
                    .append(" availability=").append(c.availability()).append(" dropout=").append(c.dropout()).append(" jitter=").append(c.jitter())
                    .append(" deadlineSeconds=").append(c.deadlineSeconds()).append(" requiredRamMb=").append(c.requiredRamMb())
                    .append(" exploration=").append(c.exploration()).append(" priorSecondsPerSample=").append(c.priorSecondsPerSample()).append("\n");
        }
    }

    static double value(RunResult run,String metric) {
        JsonNode result=run.result();
        return switch(metric) {
            case "accuracy","macroF1","loss","worstClassRecall" -> number(result.path("evaluation").path(metric));
            case "coverage","participationGini" -> number(result.path("fairness").path(metric));
            case "ramFeasibleCoverage","estimatedFeasibleCoverage" -> result.path("fairness").path(metric).isNull()?Double.NaN:number(result.path("fairness").path(metric));
            case "ramFeasiblePopulation","estimatedFeasiblePopulation" -> number(result.path("fairness").path(metric));
            case "virtualSeconds" -> number(result.path("cumulativeVirtualSeconds"));
            case "wallSeconds" -> run.rounds().stream().mapToDouble(r->number(r.path("wallClockSeconds"))).sum();
            case "proxySeconds" -> run.rounds().stream().mapToDouble(r->number(r.path("proxyEvaluationMs"))).sum()/1000;
            case "proxyWallSeconds" -> sum(run,"proxyEvaluationWallMs")/1000;
            case "weightSeconds" -> sum(run,"weightCalculationMs")/1000;
            case "aggregationSeconds" -> sum(run,"aggregationMs")/1000;
            case "serverOverheadSeconds" -> sum(run,"serverAggregationOverheadMs")/1000;
            case "logicalModelBytesDispatched","logicalUpdateBytesAccepted" -> sum(run,metric);
            case "acceptedUpdates" -> run.rounds().stream().mapToInt(r->r.path("acceptedIds").size()).sum();
            case "selectedClients" -> run.rounds().stream().mapToInt(r->r.path("selectedIds").size()).sum();
            case "acceptedSelectedRatio" -> value(run,"selectedClients")==0?Double.NaN:value(run,"acceptedUpdates")/value(run,"selectedClients");
            case "selectorSeconds" -> optionalSum(run,"selectorComputationMs")/1000;
            case "fairnessUpdateSeconds" -> optionalSum(run,"fairnessUpdateMs")/1000;
            case "virtualSecondsWithSelector" -> optionalNumber(result.path("cumulativeVirtualSecondsWithSelector"));
            case "feasibleSelectionCoverage","feasibleCompletionCoverage","selectionGini","completionGini","ramFeasibleCompletionGini",
                    "feasibleOpportunityAdjustedGini","feasibleCompletionOpportunityAdjustedGini","maxFeasibleSelectionStaleness","meanFeasibleSelectionStaleness" -> optionalNumber(result.path("fairness").path(metric));
            default -> throw new IllegalArgumentException("Unknown comparison metric: "+metric);
        };
    }
    private static double recall(RunResult run,int label) {return number(run.result().path("evaluation").path("perClassRecall").path(label));}
    private static double number(JsonNode node) {
        if(!node.isNumber() || !Double.isFinite(node.asDouble())) throw new IllegalStateException("Missing or invalid numeric metric: "+node);
        return node.asDouble();
    }
    static String stats(List<Double> values) {
        var finite=values.stream().filter(Double::isFinite).toList();
        if(finite.isEmpty()) return "N/A";
        double mean=finite.stream().mapToDouble(Double::doubleValue).average().orElseThrow();
        if(finite.size()==1) return String.format(Locale.ROOT,"%.6f +/- N/A (n=1)",mean);
        double variance=finite.stream().mapToDouble(v->(v-mean)*(v-mean)).sum()/(finite.size()-1);
        return String.format(Locale.ROOT,"%.6f +/- %.6f%s",mean,Math.sqrt(variance),finite.size()==values.size()?"":" (n="+finite.size()+")");
    }
    private static String format(double value) {return Double.isFinite(value)?String.format(Locale.ROOT,"%.6f",value):"N/A";}
    private static double sum(RunResult run,String field) {return run.rounds().stream().mapToDouble(r->number(r.path(field))).sum();}
    private static double optionalNumber(JsonNode node) {return node.isMissingNode()||node.isNull()?Double.NaN:number(node);}
    private static double optionalSum(RunResult run,String field) {return run.rounds().stream().mapToDouble(r->optionalNumber(r.path(field))).sum();}
    record TargetTime(boolean reached,double virtual,double wall,int round) {}
    static TargetTime targetTime(RunResult run,double threshold) {
        var initial=run.experiment().path("snapshot").path("initialEvaluation").path("accuracy");
        if(initial.isNumber() && initial.asDouble()>=threshold) return new TargetTime(true,0,0,0);
        double wall=0;
        for(var round:run.rounds()) {
            wall+=number(round.path("wallClockSeconds"));
            if(number(round.path("evaluation").path("accuracy"))>=threshold)
                return new TargetTime(true,number(round.path("cumulativeVirtualSeconds")),wall,round.path("roundId").asInt());
        }
        return new TargetTime(false,Double.NaN,Double.NaN,-1);
    }
    static int sustainedFromRound(RunResult run,double threshold) {
        int lastBelow=-1;
        for(int i=0;i<run.rounds().size();i++) if(number(run.rounds().get(i).path("evaluation").path("accuracy"))<threshold) lastBelow=i;
        if(lastBelow==run.rounds().size()-1) return -1;
        if(lastBelow<0 && run.experiment().path("snapshot").path("initialEvaluation").path("accuracy").asDouble(-1)>=threshold) return 0;
        return run.rounds().get(lastBelow+1).path("roundId").asInt();
    }
    private static void appendTargets(StringBuilder out,List<Double> targets,List<RunResult> left,List<RunResult> right) {
        out.append("\nTIME TO TARGET (censored runs stay NOT_REACHED, never 0)\n");
        for(double threshold:targets) {
            for(var side:List.of(left,right)) {
                var times=side.stream().map(r->targetTime(r,threshold)).toList();
                long reached=times.stream().filter(TargetTime::reached).count();
                out.append(String.format(Locale.ROOT,"threshold=%.2f row=%s reached=%d/%d conditionalVirtual=%s conditionalWall=%s%n",threshold,
                        side.get(0).row(),reached,side.size(),stats(times.stream().map(TargetTime::virtual).toList()),stats(times.stream().map(TargetTime::wall).toList())));
                out.append("  sustainedThroughFinalRound=").append(side.stream().filter(r->sustainedFromRound(r,threshold)>=0).count()).append("/").append(side.size()).append("\n");
            }
        }
        out.append("Conditional means include ONLY reached runs; use reached counts together with these times.\n");
    }
}
