package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.nio.file.Path;
import java.util.*;
import static com.huanphan.ferderatedsystem.ControlledExperiments.*;

/** Reporting and fairness-only matching. Learning outcomes never enter policy selection. */
final class FairnessMatchedReport {
    static final List<String> TOLERANCES=List.of("selectionCoverageAbs","completionCoverageAbs","selectionGiniMeanAbs","completionGiniMeanAbs","maxStalenessMeanAbs","meanStalenessMeanAbs");
    static final List<String> MATCH_METRICS=List.of("feasibleSelectionCoverage","feasibleCompletionCoverage","feasibleOpportunityAdjustedGini",
            "feasibleCompletionOpportunityAdjustedGini","maxFeasibleSelectionStaleness","meanFeasibleSelectionStaleness");
    static final List<String> METRICS=List.of("accuracy","macroF1","loss","worstClassRecall","recall0","recall1","recall2","recall3","recall4","recall5","recall6",
            "accuracyTailMean","accuracyTailSd","macroF1TailSd","maxAccuracyDropPp","finalAccuracyChangePp","populationSelectionCoverage","populationCompletionCoverage",
            "feasibleSelectionCoverage","feasibleCompletionCoverage","feasibleOpportunityAdjustedGini","feasibleCompletionOpportunityAdjustedGini",
            "selectionGini","completionGini","ramFeasibleCompletionGini","maxFeasibleSelectionStaleness","meanFeasibleSelectionStaleness",
            "populationNeverSelected","feasibleNeverSelected","acceptedSelectedRatio","virtualSeconds","virtualSecondsWithSelector","wallSeconds",
            "selectorSeconds","fairnessUpdateSeconds","slotsChangedVsTopsis","slotsChangedVsTopsisRatio","meanAppliedLambda");
    private FairnessMatchedReport() {}
    static String cell(RunResult run) {
        var manifest=run.experiment().path("snapshot").path("manifest");
        return manifest.path("partitionSeed").asLong(manifest.path("seed").asLong()+2)+":"+run.config().seed();
    }
    static ObjectNode match(List<RunResult> runs,JsonNode tolerance,ObjectMapper json) {
        Map<String,RunResult> adaptive=new TreeMap<>();Map<Row,Map<String,RunResult>> fixed=new TreeMap<>();
        for(var run:runs) {
            Map<String,RunResult> target=run.row()==Row.M7?adaptive:fixed.computeIfAbsent(run.row(),ignored->new TreeMap<>());
            if(target.put(cell(run),run)!=null) throw new IllegalStateException("Duplicate matching cell");
        }
        if(adaptive.isEmpty()||fixed.isEmpty()) throw new IllegalStateException("Incomplete fixed/adaptive matching matrix");
        var result=json.createObjectNode().put("learningMetricsUsed",false);var candidates=result.putArray("candidates");
        List<ObjectNode> eligible=new ArrayList<>();List<ObjectNode> all=new ArrayList<>();
        for(var entry:fixed.entrySet()) {
            if(!entry.getValue().keySet().equals(adaptive.keySet())) throw new IllegalStateException("Incomplete paired partition/seed cells");
            var candidate=json.createObjectNode().put("policy",entry.getKey().name());
            candidate.put("lambda",entry.getValue().values().iterator().next().config().fuzzySelection().fairness.initialLambda);
            var gaps=candidate.putObject("gaps");boolean sameDenominators=true,finite=true;
            Map<String,List<Double>> differences=new LinkedHashMap<>();MATCH_METRICS.forEach(k->differences.put(k,new ArrayList<>()));
            for(var pair:entry.getValue().entrySet()) {
                var a=pair.getValue();var b=adaptive.get(pair.getKey());
                // Count alone is insufficient: opportunity populations must contain the same clients.
                var left=a.experiment().path("snapshot").path("selectionHistory").path("clients");
                var right=b.experiment().path("snapshot").path("selectionHistory").path("clients");
                Set<String> l=new HashSet<>(),r=new HashSet<>();left.fieldNames().forEachRemaining(l::add);right.fieldNames().forEachRemaining(r::add);
                sameDenominators&=l.equals(r)&&!l.isEmpty();
                for(String key:MATCH_METRICS) {
                    double x=fair(a,key),y=fair(b,key);finite&=Double.isFinite(x)&&Double.isFinite(y);
                    differences.get(key).add(Math.abs(x-y));
                }
            }
            boolean qualified=finite&&sameDenominators;int index=0;
            for(String key:MATCH_METRICS) {
                var values=differences.get(key);
                double gap=index<2?values.stream().mapToDouble(Double::doubleValue).max().orElse(Double.NaN):values.stream().mapToDouble(Double::doubleValue).average().orElse(Double.NaN);
                put(gaps,key,gap);qualified&=Double.isFinite(gap)&&gap<=tolerance.path(TOLERANCES.get(index++)).asDouble();
            }
            candidate.put("sameObservedFeasiblePopulation",sameDenominators).put("withinAllTolerances",qualified);
            put(candidate,"coverageGap",Math.max(gaps.path(MATCH_METRICS.get(0)).asDouble(Double.POSITIVE_INFINITY),gaps.path(MATCH_METRICS.get(1)).asDouble(Double.POSITIVE_INFINITY)));
            candidates.add(candidate);all.add(candidate);if(qualified) eligible.add(candidate);
        }
        Comparator<ObjectNode> giniOrder=Comparator.<ObjectNode>comparingDouble(c->c.path("gaps").path("feasibleOpportunityAdjustedGini").asDouble(Double.POSITIVE_INFINITY)).thenComparingDouble(c->c.path("lambda").asDouble());
        var nearest=all.stream().min(Comparator.<ObjectNode>comparingDouble(c->c.path("coverageGap").asDouble(Double.POSITIVE_INFINITY)).thenComparing(giniOrder)).orElseThrow();
        result.set("nearestCandidate",nearest);
        if(eligible.isEmpty()) {result.put("status","NO_MATCH");result.putNull("selectedPolicy");result.putNull("selectedLambda");}
        else {
            var selected=eligible.stream().min(giniOrder).orElseThrow();
            result.put("status","MATCHED");result.set("selectedPolicy",selected.path("policy"));result.set("selectedLambda",selected.path("lambda"));
        }
        result.set("tolerances",tolerance);
        result.put("definition","Coverage uses maximum absolute paired gap; selection/completion Gini and staleness use mean absolute paired gaps. Coverage and all other tolerances must pass; among qualified policies minimize selection-Gini gap, tie smaller lambda. Completion Gini here is feasible completion/opportunity Gini. This is an operational match, not statistical equivalence.");
        return result;
    }
    private static double fair(RunResult run,String key) {
        var value=run.result().path("fairness").path(key);return value.isNumber()?value.asDouble():Double.NaN;
    }
    private static RunResult trajectoryRun(RunResult run,ObjectMapper json) {
        List<JsonNode> rounds=new ArrayList<>();
        for(var row:run.rounds()) {
            var copy=(ObjectNode)row.deepCopy();if(row.has("trajectoryEvaluation")) copy.set("evaluation",row.path("trajectoryEvaluation"));rounds.add(copy);
        }
        return new RunResult(run.row(),run.config(),run.experiment(),rounds.get(rounds.size()-1),rounds);
    }
    static double metric(RunResult run,String key,int window,ObjectMapper json) {
        var clients=run.experiment().path("snapshot").path("clients");
        if(key.startsWith("recall")) return run.result().path("evaluation").path("perClassRecall").path(Integer.parseInt(key.substring(6))).asDouble(Double.NaN);
        return switch(key) {
            case "accuracyTailMean","accuracyTailSd","macroF1TailSd","maxAccuracyDropPp","finalAccuracyChangePp" -> LambdaAblationReport.value(trajectoryRun(run,json),key,window);
            case "populationSelectionCoverage" -> clients.isEmpty()?Double.NaN:count(clients,"selectionCount",true)/(double)clients.size();
            case "populationCompletionCoverage" -> clients.isEmpty()?Double.NaN:count(clients,"completionCount",true)/(double)clients.size();
            case "populationNeverSelected" -> count(clients,"selectionCount",false);
            case "feasibleNeverSelected" -> count(run.experiment().path("snapshot").path("selectionHistory").path("clients"),"selections",false);
            default -> LambdaAblationReport.value(run,key,window);
        };
    }
    private static long count(JsonNode values,String key,boolean positive) {
        long count=0;for(var v:values) if((v.path(key).asInt()>0)==positive) count++;return count;
    }
    private static void put(ObjectNode node,String key,double value) {if(Double.isFinite(value)) node.put(key,value);else node.putNull(key);}
    static ObjectNode stats(List<Double> values,ObjectMapper json) {
        var finite=values.stream().filter(Double::isFinite).toList();var out=json.createObjectNode().put("n",finite.size()).put("total",values.size());
        if(finite.isEmpty()) {out.putNull("mean");out.putNull("sampleSd");return out;}
        double mean=finite.stream().mapToDouble(Double::doubleValue).average().orElseThrow();out.put("mean",mean);
        if(finite.size()<2) out.putNull("sampleSd");else out.put("sampleSd",Math.sqrt(finite.stream().mapToDouble(v->(v-mean)*(v-mean)).sum()/(finite.size()-1)));
        out.put("min",Collections.min(finite)).put("max",Collections.max(finite));return out;
    }
    static ObjectNode outcome(RunResult run,String phase,JsonNode p,ObjectMapper json) throws Exception {
        var manifest=run.experiment().path("snapshot").path("manifest");
        var out=json.createObjectNode().put("phase",phase).put("experimentId",run.config().experimentId()).put("policy",run.row().name())
                .put("partitionSeed",manifest.path("partitionSeed").asLong(manifest.path("seed").asLong()+2)).put("splitSeed",manifest.path("seed").asLong())
                .put("trainingScenarioSeed",run.config().seed()).put("configuredLambda",run.config().fuzzySelection().fairness.initialLambda)
                .put("finalEvaluationSplit",run.result().path("evaluationSplit").asText(run.config().effectiveEvaluationSplit()))
                .put("stabilityAndTargetSplit",run.config().effectiveEvaluationSplit());
        for(String key:METRICS) put(out,key,metric(run,key,p.path("stabilityWindow").asInt(10),json));
        out.put("populationDenominator",run.config().totalClients());
        out.set("ramFeasibleDenominator",run.result().path("fairness").path("ramFeasiblePopulation"));
        out.set("observedFeasibleOpportunityDenominator",run.result().path("fairness").path("feasibleOpportunityPopulation"));
        out.put("partitionManifestHash",ResearchProvenance.hash(manifest));
        out.set("initialModelHash",run.experiment().path("snapshot").path("initialModelStateHash"));
        out.set("scenarioTraceHash",run.experiment().path("snapshot").path("scenarioTraceHash"));
        out.set("provenance",run.config().provenance()==null?NullNode.instance:run.config().provenance());
        var targets=out.putObject("targets");var trajectory=trajectoryRun(run,json);
        for(var value:p.path("accuracyTargets")) {
            double target=value.asDouble();var time=ComparisonReport.targetTime(trajectory,target);int sustained=ComparisonReport.sustainedFromRound(trajectory,target);
            var entry=targets.putObject(value.asText());entry.put("split",run.config().effectiveEvaluationSplit()).put("reached",time.reached());
            if(time.reached()) {
                entry.put("firstRound",time.round()).put("virtualSeconds",time.virtual()).put("wallSeconds",time.wall());
                entry.put("virtualSecondsWithSelector",time.round()==0?0:run.rounds().get(time.round()-1).path("cumulativeVirtualSecondsWithSelector").asDouble());
            } else {entry.putNull("firstRound");entry.putNull("virtualSeconds");entry.putNull("wallSeconds");entry.putNull("virtualSecondsWithSelector");}
            if(sustained>=0) entry.put("sustainedFromRound",sustained);else entry.putNull("sustainedFromRound");
            entry.put("firstCrossingSustainedThroughFinal",time.reached()&&sustained==time.round());
        }
        return out;
    }
    static ObjectNode data(String phase,List<RunResult> runs,JsonNode p,ObjectMapper json,Exception failure,boolean matching) throws Exception {
        var report=json.createObjectNode().put("phase",phase).put("smoke",p.path("smoke").asBoolean()).put("complete",failure==null);
        if(failure!=null) report.put("error",failure.toString());
        report.put("units","Ratios except maximum accuracy drop in percentage points and times in seconds. Tail SD is within-run; summary sample SD is between training/scenario seeds inside each partition. Partitions are not treated as extra independent training seeds.");
        report.put("denominators","Population selection/completion coverage: all 100 logical clients. RAM denominator: static feasible RAM population (normally 60). Feasible coverage/Gini/staleness: clients with >=1 valid estimated-feasible opportunity, whose count and membership are policy-specific and exported. Completion Ginis are explicitly separated into population, RAM-feasible and feasible completion/opportunity versions.");
        var records=report.putArray("results");for(var run:runs) records.add(outcome(run,phase,p,json));
        if(matching&&failure==null&&!runs.isEmpty()) report.set("fairnessMatching",match(runs,p.path("matching"),json));
        var summaries=report.putArray("summaryByPartition");Map<String,List<JsonNode>> groups=new TreeMap<>();
        records.forEach(r->groups.computeIfAbsent(r.path("partitionSeed").asText()+":"+r.path("policy").asText(),ignored->new ArrayList<>()).add(r));
        for(var entry:groups.entrySet()) {
            var summary=summaries.addObject().put("group",entry.getKey());var metrics=summary.putObject("metrics");
            for(String key:METRICS) metrics.set(key,stats(entry.getValue().stream().map(r->r.path(key).asDouble(Double.NaN)).toList(),json));
        }
        var paired=report.putArray("pairedDifferences");
        if(failure==null) {
            String adaptivePolicy=matching?"M7":"P4";
            Map<String,JsonNode> adaptive=new HashMap<>();records.forEach(r->{if(r.path("policy").asText().equals(adaptivePolicy)) adaptive.put(r.path("partitionSeed").asText()+":"+r.path("trainingScenarioSeed").asText(),r);});
            for(var r:records) if(!r.path("policy").asText().equals(adaptivePolicy)) {
                var other=adaptive.get(r.path("partitionSeed").asText()+":"+r.path("trainingScenarioSeed").asText());
                if(other==null) throw new IllegalStateException("Missing adaptive pair in report");
                var delta=paired.addObject().put("direction","adaptive_minus_fixed");
                for(String k:List.of("partitionSeed","trainingScenarioSeed","policy")) delta.set(k,r.path(k));
                for(String k:METRICS) put(delta,k,other.path(k).asDouble(Double.NaN)-r.path(k).asDouble(Double.NaN));
            }
        }
        var pairedStats=report.putArray("pairedDifferenceSummaryByPartition");Map<String,List<JsonNode>> deltaGroups=new TreeMap<>();
        paired.forEach(r->deltaGroups.computeIfAbsent(r.path("partitionSeed").asText()+":"+r.path("policy").asText(),ignored->new ArrayList<>()).add(r));
        for(var entry:deltaGroups.entrySet()) {var row=pairedStats.addObject().put("group",entry.getKey());var metrics=row.putObject("metrics");for(String k:METRICS) metrics.set(k,stats(entry.getValue().stream().map(r->r.path(k).asDouble(Double.NaN)).toList(),json));}
        var trajectories=report.putArray("trajectories");
        for(var run:runs) {
            var trajectory=trajectories.addObject().put("experimentId",run.config().experimentId()).put("policy",run.row().name()).put("cell",cell(run));var rounds=trajectory.putArray("rounds");
            Set<Integer> selected=new HashSet<>();
            for(var r:run.rounds()) {
                for(var id:r.path("selectedIds")) selected.add(id.asInt());var row=rounds.addObject().put("populationNeverSelected",run.config().totalClients()-selected.size());
                for(String k:List.of("roundId","currentFairnessLambda","nextFairnessLambda","smoothedFeasibleSelectionGini","fairnessCredits","fairnessCreditsAfterRound","fairness",
                        "slotsChangedVsTopsis","slotsChangedVsTopsisRatio","topsisTopKClientIds","selectedIds","acceptedIds","selectionDecisions","trajectoryEvaluation","evaluation","modelStateHash","selectorComputationMs","fairnessUpdateMs")) row.set(k,r.path(k));
            }
        }
        var pareto=report.putArray("accuracyGiniPareto");Map<Row,List<RunResult>> policies=new TreeMap<>();runs.forEach(r->policies.computeIfAbsent(r.row(),ignored->new ArrayList<>()).add(r));
        for(var entry:policies.entrySet()) {
            var point=pareto.addObject().put("policy",entry.getKey().name());
            point.put("meanAccuracy",entry.getValue().stream().mapToDouble(r->r.result().path("evaluation").path("accuracy").asDouble()).average().orElseThrow());
            put(point,"meanSelectionGini",entry.getValue().stream().mapToDouble(r->fair(r,"feasibleOpportunityAdjustedGini")).average().orElse(Double.NaN));
        }
        for(var a:pareto) {
            boolean dominated=false;for(var b:pareto) if(a.path("meanSelectionGini").isNumber()&&b.path("meanSelectionGini").isNumber()&&b!=a&&b.path("meanAccuracy").asDouble()>=a.path("meanAccuracy").asDouble()&&b.path("meanSelectionGini").asDouble()<=a.path("meanSelectionGini").asDouble()&&
                    (b.path("meanAccuracy").asDouble()>a.path("meanAccuracy").asDouble()||b.path("meanSelectionGini").asDouble()<a.path("meanSelectionGini").asDouble())) dominated=true;
            ((ObjectNode)a).put("onObservedMeanFrontier",a.path("meanSelectionGini").isNumber()&&!dominated);
        }
        return report;
    }
    static void write(Path output,String phase,List<RunResult> runs,JsonNode p,ObjectMapper json,Exception failure) throws Exception {
        var report=data(phase,runs,p,json,failure,true);
        ResearchProvenance.save(output.resolve("fairness-matched-results.json"),report,json,false);
        writeCsv(output.resolve("fairness-matched-results.csv"),report.path("results"));
        ResearchProvenance.saveText(output.resolve("fairness-matched-summary.md"),markdown(report));
    }
    static void writeCsv(Path path,JsonNode records) throws Exception {
        List<String> columns=new ArrayList<>();if(!records.isEmpty()) records.get(0).fieldNames().forEachRemaining(columns::add);
        var csv=new StringBuilder(String.join(",",columns)).append("\n");for(var record:records) {List<String> fields=new ArrayList<>();for(String key:columns) {var v=record.path(key);fields.add(quote(v.isTextual()?v.asText():v.toString()));}csv.append(String.join(",",fields)).append("\n");}
        ResearchProvenance.saveText(path,csv.toString());
    }
    private static String quote(String text) {return "\""+text.replace("\"","\"\"")+"\"";}
    private static String fmt(JsonNode value) {return value.isNumber()?String.format(Locale.ROOT,"%.6f",value.asDouble()):"N/A";}
    static String markdown(JsonNode r) {
        var out=new StringBuilder("# Fairness-matched lambda experiments — ").append(r.path("phase").asText()).append("\n\nComplete: ").append(r.path("complete")).append("; smoke: ").append(r.path("smoke")).append(".\n\n");
        if(r.has("error")) out.append("INCOMPLETE: ").append(r.path("error").asText()).append(". Completed runs are retained; no final comparison or policy lock is justified.\n\n");
        String status=r.path("fairnessMatching").path("status").asText("INCOMPLETE");
        out.append("Fairness status: **").append(status).append("**. ").append(status.equals("MATCHED")?"Operational tolerances passed; this is not statistical equivalence.":"Do not label this comparison fairness-matched. Inspect every coverage/Gini/staleness gap in JSON; held-out policy must not be retuned.").append("\n\n")
                .append(r.path("units").asText()).append("\n\n").append(r.path("denominators").asText()).append("\n\n")
                .append("Phase A reports proxy validation outcomes. Phase B reports test ONLY at the final checkpoint; tail stability, drift/drop and time-to-target use the independently held-out proxy trajectory, as labelled in every record. Final accuracy always uses the final checkpoint, including low accuracy/drift runs.\n\n")
                .append("## Per-partition mean ± sample SD across training/scenario seeds\n\n| Partition:policy | Metric | Mean | Sample SD | n | Min / worst case | Max |\n| --- | --- | ---: | ---: | ---: | ---: | ---: |\n");
        for(var group:r.path("summaryByPartition")) for(String key:METRICS) {var s=group.path("metrics").path(key);out.append("| ").append(group.path("group").asText()).append(" | ").append(key).append(" | ").append(fmt(s.path("mean"))).append(" | ").append(fmt(s.path("sampleSd"))).append(" | ").append(s.path("n")).append(" | ").append(fmt(s.path("min"))).append(" | ").append(fmt(s.path("max"))).append(" |\n");}
        out.append("\n## Candidate fairness gaps\n\n").append(r.path("fairnessMatching").path("definition").asText()).append("\n\n| Policy | Lambda | Selection coverage max gap | Completion coverage max gap | Selection Gini mean gap | Completion Gini mean gap | Max staleness mean gap | Mean staleness mean gap | All tolerances pass |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |\n");
        for(var candidate:r.path("fairnessMatching").path("candidates")) {
            out.append("| ").append(candidate.path("policy").asText()).append(" | ").append(fmt(candidate.path("lambda")));
            for(String k:MATCH_METRICS) out.append(" | ").append(fmt(candidate.path("gaps").path(k)));
            out.append(" | ").append(candidate.path("withinAllTolerances")).append(" |\n");
        }
        out.append("\nConfigured tolerances: `").append(r.path("fairnessMatching").path("tolerances")).append("`. Selected policy: ")
                .append(r.path("fairnessMatching").path("selectedPolicy")).append("; lambda: ").append(r.path("fairnessMatching").path("selectedLambda")).append(".\n");
        out.append("\n## Paired differences: Adaptive minus Fixed\n\n| Partition | Seed | Fixed policy | Accuracy difference | Tail SD difference | Selection Gini difference |\n| --- | --- | --- | ---: | ---: | ---: |\n");
        for(var d:r.path("pairedDifferences")) out.append("| ").append(d.path("partitionSeed")).append(" | ").append(d.path("trainingScenarioSeed")).append(" | ").append(d.path("policy").asText()).append(" | ").append(fmt(d.path("accuracy"))).append(" | ").append(fmt(d.path("accuracyTailSd"))).append(" | ").append(fmt(d.path("feasibleOpportunityAdjustedGini"))).append(" |\n");
        out.append("\nAll paired metric differences and their sample SD within each partition are in JSON. Accuracy–Gini points below are descriptive means across balanced partition/seed cells, not a significance or superiority test.\n\n## Observed Accuracy–Gini Pareto analysis\n\n| Policy | Mean accuracy | Mean selection Gini | On observed mean frontier |\n| --- | ---: | ---: | --- |\n");
        for(var point:r.path("accuracyGiniPareto")) out.append("| ").append(point.path("policy").asText()).append(" | ").append(fmt(point.path("meanAccuracy"))).append(" | ").append(fmt(point.path("meanSelectionGini"))).append(" | ").append(point.path("onObservedMeanFrontier")).append(" |\n");
        if(r.path("complete").asBoolean()) out.append("\n![Accuracy–Gini trade-off](accuracy-gini-pareto.png)\n\n![Learning stability](learning-stability.png)\n\n![Fairness evolution](fairness-evolution.png)\n\n![Adaptive behavior](adaptive-behavior.png)\n");
        return out.append("\n## Fairness and adaptive trajectories\n\nPer-round Gini/staleness, population never-selected count, applied/next lambda, smoothed Gini, full credit distributions and slots changed vs raw TOPSIS on the same pre-round history are retained under `trajectories` in JSON. Matching tolerances and each candidate's exact gaps are under `fairnessMatching`.\n\nVirtual time includes measured server overhead; virtual time with selector additionally includes measured selector/fairness overhead. Deterministic simulated duration does not make those measured overheads deterministic. No best-test-checkpoint selection, statistical equivalence, or adaptive-superiority claim is made.\n").toString();
    }
}
