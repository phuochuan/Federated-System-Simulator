package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.huanphan.ferderatedsystem.selection.fuzzy.*;
import java.util.*;
import static com.huanphan.ferderatedsystem.ControlledExperiments.*;

final class ReproducibilityAuditReport {
    private ReproducibilityAuditReport() {}
    static ObjectNode create(Map<String,List<RunResult>> groups,JsonNode protocol,ObjectMapper json,Exception failure) throws Exception {
        var report=json.createObjectNode();report.put("smoke",protocol.path("smoke").asBoolean(false));
        int expected=protocol.path("seeds").size()*2*2*protocol.path("audit").path("repetitions").asInt();
        int count=groups.values().stream().mapToInt(List::size).sum();
        boolean complete=failure==null&&count==expected,deterministic=true,conditional=true,savedState=true;
        Set<JsonNode> initialModels=new HashSet<>();
        report.put("complete",complete).put("completedRuns",count).put("expectedRuns",expected);
        if(failure!=null) report.put("error",failure.toString());
        var runs=report.putArray("runs");var pairs=report.putArray("comparisons");var summaries=report.putArray("repeatSummaryByGroup");
        for(var group:groups.entrySet()) {
            var summary=summaries.addObject().put("group",group.getKey());var metrics=summary.putObject("metrics");
            for(String key:List.of("accuracy","macroF1","loss","feasibleSelectionCoverage","feasibleCompletionCoverage","feasibleOpportunityAdjustedGini","virtualSeconds","virtualSecondsWithSelector","wallSeconds"))
                metrics.set(key,FairnessMatchedReport.stats(group.getValue().stream().map(r->ComparisonReport.value(r,key)).toList(),json));
            metrics.set("meanActualTrainingMs",FairnessMatchedReport.stats(group.getValue().stream().map(r->r.rounds().stream().flatMap(x->{List<Double> values=new ArrayList<>();for(var participant:x.path("participants")) values.add(participant.path("training").path("actualTrainingMs").asDouble());return values.stream();}).mapToDouble(Double::doubleValue).average().orElse(Double.NaN)).toList(),json));
            for(var run:group.getValue()) {
                var entry=runs.addObject().put("group",group.getKey()).put("experimentId",run.config().experimentId());
                entry.set("config",json.valueToTree(run.config()));var snap=run.experiment().path("snapshot");
                for(String key:List.of("manifest","initialModelStateHash","scenarioTraceHash","gitCommit","gitDirty","executionProvenance")) entry.set(key,snap.path(key));
                entry.put("partitionManifestHash",ResearchProvenance.hash(snap.path("manifest")));
                entry.put("partitionSeed",snap.path("manifest").path("partitionSeed").asLong(snap.path("manifest").path("seed").asLong()+2));
                entry.put("splitSeed",snap.path("manifest").path("seed").asLong());
                entry.put("savedStateAndTimingReplayPassed",stateReplay(run,json));
                savedState&=entry.path("savedStateAndTimingReplayPassed").asBoolean();initialModels.add(snap.path("initialModelStateHash"));
                var rounds=entry.putArray("rounds");
                for(var round:run.rounds()) {
                    var evidence=rounds.addObject();
                    for(String key:List.of("roundId","selectedIds","acceptedIds","estimatedFeasibleIds","selectionDecisions","modelStateHash",
                            "evaluation","fairness","currentFairnessLambda","nextFairnessLambda","fairnessCredits","fairnessCreditsAfterRound",
                            "smoothedFeasibleSelectionGini","simulatedTrainingRoundSeconds")) evidence.set(key,round.path(key));
                    var training=evidence.putArray("training");for(var participant:round.path("participants")) {
                        var local=training.addObject();local.set("clientId",participant.path("clientId"));
                        local.set("durationInputMs",participant.path("durationInputMs"));
                        for(String key:List.of("actualTrainingMs","trainingLoss","modelStateHash")) local.set(key,participant.path("training").path(key));
                    }
                }
                if(report.path("runtimeIdentity").isMissingNode()) report.set("runtimeIdentity",run.config().provenance().path("runtimeIdentity"));
                if(group.getKey().startsWith("deterministic")&&!entry.path("savedStateAndTimingReplayPassed").asBoolean()) deterministic=false;
            }
            var values=group.getValue();
            for(int a=0;a<values.size();a++) for(int b=a+1;b<values.size();b++) {
                var comparison=compare(values.get(a),values.get(b),json);comparison.put("group",group.getKey());pairs.add(comparison);
                if(group.getKey().startsWith("deterministic")&&!comparison.path("exactDecisionModelMetricReplay").asBoolean()) deterministic=false;
                if(comparison.path("conditionalTrainingDifferences").asInt()>0) conditional=false;
            }
        }
        report.put("sameInitialModelsAcrossPoliciesAndModes",initialModels.size()==1);
        report.put("savedStateReplayPassed",savedState);
        report.put("deterministicReplayPassed",complete&&deterministic&&conditional&&savedState&&initialModels.size()==1);
        report.put("conditionalTrainingPassed",conditional);
        report.put("conclusion",!complete?"INCOMPLETE: retained evidence cannot establish reproducibility":
                !conditional?"TRAINING_NONDETERMINISM: equal model/client/round inputs produced different local tensors":
                !deterministic||!savedState||initialModels.size()!=1?"DETERMINISTIC_REPLAY_FAILED: inspect initialization, model, selection and saved-state divergence before E1":
                "Deterministic decision/model/learning replay passed. Measured-duration differences are reported separately; this does not establish cross-platform reproducibility.");
        report.put("timingScope","Pure simulated training duration is deterministic in deterministic mode. Server, selector, fairness, evaluation and physical wall-time overhead remain measured and need not be equal.");
        return report;
    }
    static ObjectNode compare(RunResult a,RunResult b,ObjectMapper json) {
        var out=json.createObjectNode().put("left",a.config().experimentId()).put("right",b.config().experimentId());
        boolean initial=validHash(a.experiment().path("snapshot").path("initialModelStateHash"))&&validHash(b.experiment().path("snapshot").path("initialModelStateHash"))&&
                a.experiment().path("snapshot").path("initialModelStateHash").equals(b.experiment().path("snapshot").path("initialModelStateHash"));
        out.put("sameInitialModel",initial);
        boolean inputs=a.experiment().path("snapshot").path("manifest").equals(b.experiment().path("snapshot").path("manifest"))&&
                a.experiment().path("snapshot").path("scenarioTraceHash").equals(b.experiment().path("snapshot").path("scenarioTraceHash"));
        var configA=(ObjectNode)json.valueToTree(a.config());var configB=(ObjectNode)json.valueToTree(b.config());
        configA.remove(List.of("experimentId","provenance"));configB.remove(List.of("experimentId","provenance"));inputs&=configA.equals(configB);
        boolean exact=initial&&inputs;int conditionalChecked=0,conditionalDifferences=0,missingHashes=0;String priorA=a.experiment().path("snapshot").path("initialModelStateHash").asText(),priorB=b.experiment().path("snapshot").path("initialModelStateHash").asText();
        for(String name:List.of("Selection","SelectionSet","GlobalModel","LearningMetrics","FairnessMetrics","LambdaCredits","TimingEstimates","DurationInput","SavedState")) out.putNull("first"+name+"Difference");
        if(a.rounds().size()!=b.rounds().size()) exact=false;
        for(int i=0;i<Math.min(a.rounds().size(),b.rounds().size());i++) {
            var x=a.rounds().get(i);var y=b.rounds().get(i);int round=i+1;
            boolean selection=x.path("selectedIds").equals(y.path("selectedIds"));
            boolean set=new HashSet<>(ids(x.path("selectedIds"))).equals(new HashSet<>(ids(y.path("selectedIds"))));
            boolean model=validHash(x.path("modelStateHash"))&&x.path("modelStateHash").equals(y.path("modelStateHash"));
            if(!validHash(x.path("modelStateHash"))||!validHash(y.path("modelStateHash"))) missingHashes++;
            inputs&=x.path("scenarioTrace").equals(y.path("scenarioTrace"));
            boolean learning=evaluation(x,json).equals(evaluation(y,json));
            boolean fairness=x.path("fairness").equals(y.path("fairness"));
            boolean credits=List.of("currentFairnessLambda","nextFairnessLambda","fairnessCredits","fairnessCreditsAfterRound").stream().allMatch(k->x.path(k).equals(y.path(k)));
            boolean timing=x.path("criteriaObservations").equals(y.path("criteriaObservations"));
            boolean duration=durations(x,json).equals(durations(y,json));
            boolean state=x.path("selectorInput").path("history").equals(y.path("selectorInput").path("history"));
            boolean[] equal={selection,set,model,learning,fairness,credits,timing,duration,state};int index=0;
            for(String name:List.of("Selection","SelectionSet","GlobalModel","LearningMetrics","FairnessMetrics","LambdaCredits","TimingEstimates","DurationInput","SavedState")) {
                if(!equal[index++]&&out.path("first"+name+"Difference").isNull()) out.put("first"+name+"Difference",round);
            }
            exact&=selection&&model&&learning&&fairness&&credits&&timing&&state&&x.path("acceptedIds").equals(y.path("acceptedIds"))&&x.path("simulatedTrainingRoundSeconds").equals(y.path("simulatedTrainingRoundSeconds"));
            if(inputs&&priorA.equals(priorB)&&!priorA.isBlank()) {
                Map<Integer,JsonNode> left=new HashMap<>();for(var p:x.path("participants")) left.put(p.path("clientId").asInt(),p.path("training"));
                for(var p:y.path("participants")) {
                    var q=left.get(p.path("clientId").asInt());if(q==null) continue;conditionalChecked++;
                    if(!validHash(q.path("modelStateHash"))||!validHash(p.path("training").path("modelStateHash"))) {missingHashes++;continue;}
                    if(!q.path("modelStateHash").equals(p.path("training").path("modelStateHash"))||
                            !q.path("trainingLoss").equals(p.path("training").path("trainingLoss"))) conditionalDifferences++;
                }
            }
            priorA=x.path("modelStateHash").asText();priorB=y.path("modelStateHash").asText();
        }
        exact&=inputs&&missingHashes==0;
        out.put("controlledConfigPartitionAndScenarioMatch",inputs).put("missingHashEvidence",missingHashes);
        out.put("equalInputTrainingJobsChecked",conditionalChecked).put("conditionalTrainingDifferences",conditionalDifferences).put("exactDecisionModelMetricReplay",exact);
        out.put("classification",!inputs?"UNCONTROLLED_INPUT_DIFFERENCE":missingHashes>0?"INSUFFICIENT_MODEL_HASH_EVIDENCE":conditionalDifferences>0?"TRAINING_RANDOMNESS_OR_NUMERIC_NONDETERMINISM":
                !initial?"INITIALIZATION_DIFFERENCE":exact?"EXACT_DECISION_MODEL_METRIC_REPLAY":
                a.config().durationMode().equals("measured")&&!out.path("firstDurationInputDifference").isNull()?"TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY":
                "STATE_OR_EXECUTION_DIVERGENCE_REQUIRES_INVESTIGATION");
        return out;
    }
    private static boolean validHash(JsonNode node) {return node.isTextual()&&node.asText().matches("[0-9a-f]{64}");}
    private static List<Integer> ids(JsonNode values) {List<Integer> out=new ArrayList<>();values.forEach(v->out.add(v.asInt()));return out;}
    private static JsonNode evaluation(JsonNode round,ObjectMapper json) {
        var node=round.path("evaluation").deepCopy();if(node instanceof ObjectNode object) object.remove("evaluationMs");return node;
    }
    private static JsonNode durations(JsonNode row,ObjectMapper json) {
        var out=json.createObjectNode();for(var p:row.path("participants")) out.set(p.path("clientId").asText(),p.path("durationInputMs"));return out;
    }
    static boolean stateReplay(RunResult run,ObjectMapper json) {
        try {
            var history=new SelectionHistory();var state=FairnessCreditState.initial(run.config().selection(),run.config().fuzzySelection());
            Map<Integer,Double> estimates=new HashMap<>();
            for(var row:run.rounds()) {
                if(!json.valueToTree(history).equals(row.path("selectorInput").path("history"))||!json.valueToTree(state).equals(row.path("selectorInput").path("state"))) return false;
                for(var p:row.path("selectorInput").path("eligibleClients")) {
                    int id=p.path("clientId").asInt();Double expected=estimates.get(id);
                    if(expected==null?!p.path("estimatedSeconds").isNull():Double.compare(expected,p.path("estimatedSeconds").asDouble())!=0) return false;
                    double prediction=expected==null?p.path("numSamples").asInt()*run.config().localEpochs()*run.config().priorSecondsPerSample()/p.path("cpu").asDouble():expected;
                    var observation=row.path("criteriaObservations").path(Integer.toString(id));
                    if(!observation.isMissingNode()&&Math.abs(observation.path("estimatedTime").asDouble()-Math.max(run.config().fuzzySelection().epsilon,prediction))>1e-12) return false;
                }
                var feasible=ids(row.path("estimatedFeasibleIds"));var selected=new HashSet<>(ids(row.path("selectedIds")));var accepted=new HashSet<>(ids(row.path("acceptedIds")));
                history.observe(feasible,selected,accepted,run.config().selectedPerRound());
                new CreditFairnessScheduler().afterRound(state,run.config().fuzzySelection(),history,feasible,selected,run.config().selectedPerRound(),row.path("roundId").asInt());
                if(Double.compare(state.currentLambda,row.path("nextFairnessLambda").asDouble())!=0||!json.valueToTree(state.deficits).equals(row.path("fairnessCreditsAfterRound"))) return false;
                for(var p:row.path("participants")) {
                    int id=p.path("clientId").asInt();
                    var profile=run.experiment().path("snapshot").path("clients");
                    double cpu=0;for(var client:profile) if(client.path("clientId").asInt()==id) cpu=client.path("cpu").asDouble();
                    if(cpu<=0) return false;estimates.put(id,p.path("durationInputMs").asDouble()/1000/cpu);
                }
            }
            return json.valueToTree(history).equals(run.experiment().path("snapshot").path("selectionHistory"))&&json.valueToTree(state).equals(run.experiment().path("snapshot").path("fuzzySelectionState"));
        } catch(Exception e) {return false;}
    }
    static String markdown(JsonNode report) {
        var out=new StringBuilder("# Reproducibility audit\n\n").append(report.path("conclusion").asText()).append("\n\n")
                .append("Completed runs: ").append(report.path("completedRuns")).append("/").append(report.path("expectedRuns")).append(". Smoke: ").append(report.path("smoke")).append(".\n\n")
                .append("| Group | First selection/order difference | First selected-set difference | First global model difference | First learning difference | Classification |\n| --- | ---: | ---: | ---: | ---: | --- |\n");
        for(var pair:report.path("comparisons")) out.append("| ").append(pair.path("group").asText()).append(" | ").append(pair.path("firstSelectionDifference")).append(" | ")
                .append(pair.path("firstSelectionSetDifference")).append(" | ").append(pair.path("firstGlobalModelDifference")).append(" | ")
                .append(pair.path("firstLearningMetricsDifference")).append(" | ").append(pair.path("classification").asText()).append(" |\n");
        out.append("\n## Conditional run-to-run variability\n\nThese sample SDs are across repetitions of one seed inside each policy/duration group, not across training seeds and not within-run tail SD. All groups retain their observed n even when incomplete.\n\n| Group | Metric | Mean | Sample SD | n | Min | Max |\n| --- | --- | ---: | ---: | ---: | ---: | ---: |\n");
        for(var group:report.path("repeatSummaryByGroup")) {
            var fields=group.path("metrics").fields();while(fields.hasNext()) {
                var field=fields.next();var s=field.getValue();out.append("| ").append(group.path("group").asText()).append(" | ").append(field.getKey()).append(" | ")
                        .append(s.path("mean")).append(" | ").append(s.path("sampleSd")).append(" | ").append(s.path("n")).append(" | ").append(s.path("min")).append(" | ").append(s.path("max")).append(" |\n");
            }
        }
        return out.append("\nNull means no observed divergence or unavailable summary statistic. Each of three repeats is compared with every other repeat within its policy/seed/duration group.\n\n")
                .append(report.path("timingScope").asText()).append("\n\nEqual-input local update checks separate training nondeterminism from selection changes caused by measured durations. Saved-state replay checks credit/controller/history consistency; passing it does not prove absence of all simulator bugs. All metadata and round evidence are in reproducibility-audit.json and the run exports.\n").toString();
    }
}
