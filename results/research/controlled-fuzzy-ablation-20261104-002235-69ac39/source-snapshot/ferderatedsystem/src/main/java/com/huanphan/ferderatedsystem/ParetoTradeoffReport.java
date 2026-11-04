package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.nio.file.Path;
import java.util.*;
import static com.huanphan.ferderatedsystem.ControlledExperiments.*;

/** Strict, unweighted Pareto dominance of descriptive estimates, not a significance test. */
final class ParetoTradeoffReport {
    enum Direction {MAXIMIZE,MINIMIZE}
    static final Map<String,Direction> OBJECTIVES;
    static final Map<String,Direction> ACCURACY_GINI=Map.of("accuracy",Direction.MAXIMIZE,"feasibleOpportunityAdjustedGini",Direction.MINIMIZE);
    static {
        var directions=new LinkedHashMap<String,Direction>();
        for(String key:List.of("accuracy","macroF1","feasibleSelectionCoverage","feasibleCompletionCoverage")) directions.put(key,Direction.MAXIMIZE);
        for(String key:List.of("feasibleOpportunityAdjustedGini","accuracyTailSd","virtualSecondsWithSelector")) directions.put(key,Direction.MINIMIZE);
        OBJECTIVES=Collections.unmodifiableMap(directions);
    }
    private ParetoTradeoffReport() {}
    static boolean valid(JsonNode point,Map<String,Direction> objectives) {
        return objectives.keySet().stream().allMatch(k->point.path(k).isNumber()&&Double.isFinite(point.path(k).asDouble()));
    }
    static boolean dominates(JsonNode left,JsonNode right,Map<String,Direction> directions) {
        if(directions.isEmpty()||!valid(left,directions)||!valid(right,directions)) return false;
        boolean strict=false;
        for(var entry:directions.entrySet()) {
            double a=left.path(entry.getKey()).asDouble(),b=right.path(entry.getKey()).asDouble();
            int order=a==b?0:a>b?1:-1;if(entry.getValue()==Direction.MINIMIZE) order=-order;
            if(order<0) return false;if(order>0) strict=true;
        }
        return strict;
    }
    static ObjectNode rank(List<ObjectNode> points,Map<String,Direction> directions,ObjectMapper json) {
        var out=json.createObjectNode();out.set("directions",json.valueToTree(directions));var rows=out.putArray("points");
        var nondominated=out.putArray("nondominatedPolicies");var dominated=out.putArray("dominatedPolicies");var unknown=out.putArray("unassessedPolicies");
        for(var point:points) {
            var row=point.deepCopy();var by=row.putArray("dominatedBy");boolean eligible=valid(point.path("means"),directions)&&point.path("dataComplete").asBoolean();
            if(eligible) for(var other:points) if(other!=point&&other.path("dataComplete").asBoolean()&&dominates(other.path("means"),point.path("means"),directions)) by.add(other.path("policy").asText());
            String status=!eligible?"UNASSESSED":by.isEmpty()?"NONDOMINATED":"DOMINATED";row.put("status",status);
            (eligible?by.isEmpty()?nondominated:dominated:unknown).add(row.path("policy").asText());rows.add(row);
        }
        return out;
    }
    static ObjectNode frontier(JsonNode records,JsonNode protocol,ObjectMapper json) {
        var out=json.createObjectNode().put("analysisType","PARETO_COMPARISON").put("phaseAStatus","NO_MATCH");
        out.put("interpretation","Observed sample-mean dominance only. No significance/equivalence claim or arbitrary weighted winner. Missing objectives are UNASSESSED.");
        var perPartition=out.putArray("perPartition");List<ObjectNode> partitionPoints=new ArrayList<>();
        var partitions=ResearchExperiments.seeds(protocol.path("evaluation").path("partitionSeeds"));
        int expectedSeeds=protocol.path("evaluation").path("seeds").size();
        for(long partition:partitions) {
            List<ObjectNode> points=new ArrayList<>();
            for(var row:ParetoProtocol.ROWS) {
                List<JsonNode> selected=new ArrayList<>();for(var r:records) if(r.path("partitionSeed").asLong()==partition&&r.path("policy").asText().equals(row.name())) selected.add(r);
                var point=json.createObjectNode().put("policy",row.name()).put("partitionSeed",partition);var means=point.putObject("means");var statistics=point.putObject("statistics");boolean complete=selected.size()==expectedSeeds;
                for(String key:FairnessMatchedReport.METRICS) {
                    var stats=FairnessMatchedReport.stats(selected.stream().map(r->r.path(key).asDouble(Double.NaN)).toList(),json);
                    statistics.set(key,stats);means.set(key,stats.path("n").asInt()==expectedSeeds?stats.path("mean"):NullNode.instance);
                }
                point.put("dataComplete",complete);points.add(point);partitionPoints.add(point);
            }
            var part=perPartition.addObject().put("partitionSeed",partition);part.set("multiObjective",rank(points,OBJECTIVES,json));part.set("accuracyGini2D",rank(points,ACCURACY_GINI,json));
        }
        var cells=out.putArray("perSeedCell");for(long partition:partitions) for(long seed:ResearchExperiments.seeds(protocol.path("evaluation").path("seeds"))) {
            List<ObjectNode> points=new ArrayList<>();for(var r:records) if(r.path("partitionSeed").asLong()==partition&&r.path("trainingScenarioSeed").asLong()==seed) {
                var point=json.createObjectNode().put("policy",r.path("policy").asText()).put("dataComplete",true);point.set("means",r);points.add(point);
            }
            var cell=cells.addObject().put("partitionSeed",partition).put("trainingScenarioSeed",seed);cell.set("multiObjective",rank(points,OBJECTIVES,json));
        }
        List<ObjectNode> across=new ArrayList<>();
        for(var row:ParetoProtocol.ROWS) {
            var point=json.createObjectNode().put("policy",row.name());var means=point.putObject("means");var stats=point.putObject("statisticsAcrossPartitionMeans");boolean complete=true;
            var selected=partitionPoints.stream().filter(p->p.path("policy").asText().equals(row.name())).toList();
            complete&=selected.size()==partitions.size()&&selected.stream().allMatch(p->p.path("dataComplete").asBoolean());
            for(String key:FairnessMatchedReport.METRICS) {var s=FairnessMatchedReport.stats(selected.stream().map(p->p.path("means").path(key).asDouble(Double.NaN)).toList(),json);stats.set(key,s);means.set(key,s.path("n").asInt()==partitions.size()?s.path("mean"):NullNode.instance);}
            point.put("dataComplete",complete);across.add(point);
        }
        var aggregate=out.putObject("crossPartition").put("unit","Equal-weight partition means; sample SD across partition means is descriptive partition variation, not pooled independent training seeds");
        aggregate.set("multiObjective",rank(across,OBJECTIVES,json));aggregate.set("accuracyGini2D",rank(across,ACCURACY_GINI,json));
        var consistency=out.putArray("partitionConsistency");
        for(var row:ParetoProtocol.ROWS) {
            var entry=consistency.addObject().put("policy",row.name());var status=entry.putObject("statusByPartition");Set<String> seen=new HashSet<>();
            for(var partition:perPartition) for(var point:partition.path("multiObjective").path("points")) if(point.path("policy").asText().equals(row.name())) {
                status.set(partition.path("partitionSeed").asText(),point.path("status"));seen.add(point.path("status").asText());
            }
            entry.put("inconsistentAcrossPartitions",seen.size()>1);
        }
        var adaptive=out.putArray("adaptiveRelationsByPartition");
        for(var fixed:List.of(Row.P1,Row.P2,Row.P3)) {
            var entry=adaptive.addObject().put("reference","P4").put("fixedPolicy",fixed.name());var relations=entry.putObject("relationByPartition");Set<String> seen=new HashSet<>();
            for(long partition:partitions) {
                var p4=partitionPoints.stream().filter(p->p.path("policy").asText().equals("P4")&&p.path("partitionSeed").asLong()==partition).findFirst().orElseThrow();
                var other=partitionPoints.stream().filter(p->p.path("policy").asText().equals(fixed.name())&&p.path("partitionSeed").asLong()==partition).findFirst().orElseThrow();
                String relation=!p4.path("dataComplete").asBoolean()||!other.path("dataComplete").asBoolean()?"UNASSESSED":
                        dominates(p4.path("means"),other.path("means"),OBJECTIVES)?"P4_DOMINATES":dominates(other.path("means"),p4.path("means"),OBJECTIVES)?"FIXED_DOMINATES":"NEITHER_DOMINATES";
                relations.put(Long.toString(partition),relation);seen.add(relation);
            }
            entry.put("inconsistentAcrossPartitions",seen.size()>1);
        }
        return out;
    }
    static void write(Path output,List<RunResult> runs,JsonNode p,ObjectMapper json,Exception failure) throws Exception {
        Set<String> identities=new HashSet<>(),expectedCells=new HashSet<>();
        for(long partition:ResearchExperiments.seeds(p.path("evaluation").path("partitionSeeds"))) for(long seed:ResearchExperiments.seeds(p.path("evaluation").path("seeds"))) for(var row:ParetoProtocol.ROWS) expectedCells.add(partition+":"+seed+":"+row);
        for(var run:runs) if(!identities.add(FairnessMatchedReport.cell(run)+":"+run.row())) throw new IllegalStateException("Duplicate Pareto run/cell");
        if(failure==null&&!identities.equals(expectedCells)) failure=new IllegalStateException("Incomplete/unexpected Pareto policy-partition-seed cells");
        var data=FairnessMatchedReport.data("pareto",runs,p,json,failure,false);data.remove("accuracyGiniPareto");
        data.put("analysisType","PARETO_COMPARISON").put("phaseAStatus","NO_MATCH").put("pairedReferencePolicy","P4");
        int expected=p.path("evaluation").path("partitionSeeds").size()*p.path("evaluation").path("seeds").size()*4;
        data.put("expectedRuns",expected).put("completedRuns",runs.size());
        boolean complete=failure==null&&runs.size()==expected;data.put("complete",complete);
        data.put("policyLockHash",ResearchProvenance.hash(output.resolve("pareto-tradeoff-config.json")));
        var drops=data.putArray("largeAccuracyDrops");for(var r:data.path("results")) if(r.path("maxAccuracyDropPp").asDouble()>=p.path("largeAccuracyDropPp").asDouble()||
                r.path("finalAccuracyChangePp").asDouble()<=-p.path("largeAccuracyDropPp").asDouble()) {
            var drop=drops.addObject();for(String key:List.of("experimentId","policy","partitionSeed","trainingScenarioSeed","accuracy","maxAccuracyDropPp","finalAccuracyChangePp")) drop.set(key,r.path(key));drop.put("dropMetricSplit","proxy");
        }
        data.put("largeDropThresholdPp",p.path("largeAccuracyDropPp").asDouble());
        var front=frontier(data.path("results"),p,json);front.put("complete",complete);
        if(!complete) {front.put("interpretation","INCOMPLETE: exploratory points only, no final frontier conclusion");data.put("conclusion","INCOMPLETE: completed and low-accuracy runs retained; no final comparison");}
        else data.put("conclusion","Compare partition-specific nondominated sets, paired differences and cross-partition variation. Non-dominance is not proof of superiority; no overall winner is selected.");
        data.set("frontier",front);
        ResearchProvenance.save(output.resolve("pareto-tradeoff-frontier.json"),front,json,false);
        ResearchProvenance.save(output.resolve("pareto-tradeoff-results.json"),data,json,false);
        FairnessMatchedReport.writeCsv(output.resolve("pareto-tradeoff-results.csv"),data.path("results"));
        ResearchProvenance.saveText(output.resolve("pareto-tradeoff-summary.md"),markdown(data));
        writePlotData(output,data);
    }
    private static String fmt(JsonNode v) {return v.isNumber()?String.format(Locale.ROOT,"%.6f",v.asDouble()):"N/A";}
    private static String stats(JsonNode s) {return fmt(s.path("mean"))+" ± "+fmt(s.path("sampleSd"))+" (n="+s.path("n")+")";}
    static String markdown(JsonNode r) {
        var out=new StringBuilder("# Held-out Pareto Trade-off Evaluation\n\nPhase A: **NO_MATCH**. Phase B: **PARETO_COMPARISON**. Complete: ")
                .append(r.path("complete")).append("; runs=").append(r.path("completedRuns")).append("/").append(r.path("expectedRuns")).append("; smoke=").append(r.path("smoke")).append(".\n\n")
                .append(r.path("conclusion").asText()).append("\n\n").append(r.path("units").asText()).append("\n\n").append(r.path("denominators").asText()).append("\n\n")
                .append("P1=fixed .650, P2=fixed .675, P3=fixed .725; P4=Adaptive initial .300. Policies and adaptive parameters were locked from Phase A before held-out evaluation. No held-out tuning or best-checkpoint replacement.\n\n")
                .append("Final Accuracy/F1/Loss/recalls use ONLY the final test checkpoint. Tail mean/SD, consecutive drops, final-round accuracy change and time-to-target use the proxy trajectory. These split-specific statistics must not be conflated.\n\n")
                .append("## Per-partition mean ± sample SD across training/scenario seeds\n\n| Partition:policy | Metric | Mean ± sample SD | Min | Max |\n| --- | --- | --- | ---: | ---: |\n");
        for(var group:r.path("summaryByPartition")) for(String key:FairnessMatchedReport.METRICS) {var s=group.path("metrics").path(key);out.append("| ").append(group.path("group").asText()).append(" | ").append(key).append(" | ").append(stats(s)).append(" | ").append(fmt(s.path("min"))).append(" | ").append(fmt(s.path("max"))).append(" |\n");}
        out.append("\n## Observed partition-specific frontiers\n\n");
        for(var part:r.path("frontier").path("perPartition")) out.append("- Partition ").append(part.path("partitionSeed")).append(": 7-objective nondominated=").append(part.path("multiObjective").path("nondominatedPolicies"))
                .append("; dominated=").append(part.path("multiObjective").path("dominatedPolicies")).append("; unassessed=").append(part.path("multiObjective").path("unassessedPolicies"))
                .append("; Accuracy–Gini frontier=").append(part.path("accuracyGini2D").path("nondominatedPolicies")).append(".\n");
        out.append("\nMaximize Accuracy, Macro-F1, feasible selection/completion coverage; minimize feasible opportunity-adjusted selection Gini, proxy accuracy tail SD and virtual seconds including selector/fairness overhead. Dominance requires no worse on every objective and strictly better on at least one; ties do not dominate. Missing objectives are unassessed.\n\n")
                .append("## Paired differences: P4 minus Fixed\n\n| Partition | Seed | Fixed policy | Accuracy Δ | Macro-F1 Δ | Gini Δ | Tail SD Δ | Virtual+selector Δ |\n| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |\n");
        for(var delta:r.path("pairedDifferences")) {out.append("| ").append(delta.path("partitionSeed")).append(" | ").append(delta.path("trainingScenarioSeed")).append(" | ").append(delta.path("policy").asText());for(String k:List.of("accuracy","macroF1","feasibleOpportunityAdjustedGini","accuracyTailSd","virtualSecondsWithSelector")) out.append(" | ").append(fmt(delta.path(k)));out.append(" |\n");}
        out.append("\nAll paired metrics and their within-partition sample SD are in JSON.\n\n## Cross-partition summary\n\nEqual-weight means of partition means; the SD below describes variation across partitions, not 15 independent training seeds.\n\n| Policy | Metric | Mean of partition means ± SD across partition means |\n| --- | --- | --- |\n");
        for(var point:r.path("frontier").path("crossPartition").path("multiObjective").path("points")) for(String key:OBJECTIVES.keySet()) out.append("| ").append(point.path("policy").asText()).append(" | ").append(key).append(" | ").append(stats(point.path("statisticsAcrossPartitionMeans").path(key))).append(" |\n");
        out.append("\n## Consistency of Adaptive comparisons\n\n");for(var relation:r.path("frontier").path("adaptiveRelationsByPartition")) out.append("- P4 vs ").append(relation.path("fixedPolicy").asText()).append(": ").append(relation.path("relationByPartition")).append("; inconsistent across partitions=").append(relation.path("inconsistentAcrossPartitions")).append(".\n");
        out.append("\n## Large proxy-trajectory accuracy drops\n\nThreshold=").append(r.path("largeDropThresholdPp")).append(" percentage points, predeclared. All flagged and unflagged outcomes are retained.\n\n");
        if(r.path("largeAccuracyDrops").isEmpty()) out.append("No run exceeded the declared threshold.\n");
        for(var drop:r.path("largeAccuracyDrops")) out.append("- ").append(drop.path("experimentId").asText()).append(": max drop=").append(drop.path("maxAccuracyDropPp")).append(" pp; final proxy change=").append(drop.path("finalAccuracyChangePp")).append(" pp; final test accuracy=").append(drop.path("accuracy")).append(".\n");
        return out.append("\n![Accuracy–Gini](accuracy-gini-pareto.png)\n\n![Accuracy–time](accuracy-virtual-time.png)\n\n![Accuracy–tail SD](learning-stability.png)\n\n![Gini through rounds](fairness-evolution.png)\n\n![Lambda and credits](adaptive-behavior.png)\n\n## Evidence limits\n\nThese are descriptive sample-mean frontiers, not statistical equivalence or superiority tests. No weighted score or automatic overall winner is constructed. Non-dominance may vary by partition or by seed; the aggregate frontier does not override inconsistent partition results. Test pools remain the fixed Covertype split used by this project, not a globally untouched dataset. Deterministic simulated durations are uncalibrated assumptions; server/selector overhead and wall time remain measured. See the immutable config and E0 evidence for the exact runtime scope.\n").toString();
    }
    private static void writePlotData(Path output,JsonNode data) throws Exception {
        var text=new StringBuilder("partitionSeed,trainingScenarioSeed,policy,accuracy,selectionGini,virtualSecondsWithSelector,accuracyTailSd\n");
        for(var r:data.path("results")) {List<String> fields=new ArrayList<>();for(String k:List.of("partitionSeed","trainingScenarioSeed","policy","accuracy","feasibleOpportunityAdjustedGini","virtualSecondsWithSelector","accuracyTailSd")) fields.add(r.path(k).asText());text.append(String.join(",",fields)).append("\n");}
        ResearchProvenance.saveText(output.resolve("pareto-tradeoff-plot-data.csv"),text.toString());
        var rounds=new StringBuilder("experimentId,policy,cell,round,proxyAccuracy,selectionGini,appliedLambda,smoothedGini\n");
        for(var trace:data.path("trajectories")) for(var r:trace.path("rounds")) rounds.append(String.join(",",trace.path("experimentId").asText(),trace.path("policy").asText(),trace.path("cell").asText(),r.path("roundId").asText(),r.path("trajectoryEvaluation").path("accuracy").asText(),r.path("fairness").path("feasibleOpportunityAdjustedGini").asText(),r.path("currentFairnessLambda").asText(),r.path("smoothedFeasibleSelectionGini").asText())).append("\n");
        ResearchProvenance.saveText(output.resolve("pareto-tradeoff-trajectory-data.csv"),rounds.toString());
    }
}
