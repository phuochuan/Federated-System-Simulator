package com.huanphan.ferderatedsystem.selection.fuzzy;

import com.huanphan.ferderatedsystem.ClientProfile;
import com.huanphan.ferderatedsystem.ExperimentConfig;
import java.util.*;

public final class ClientCriteriaExtractor {
    private static final List<String> ORDER=List.of("estimatedTime","reliability","learningUtility","fairnessDeficit","selectionStaleness");
    public record Extracted(FuzzyDecisionMatrix matrix,Map<Integer,Map<String,Double>> observations) {}
    public Extracted extract(List<ClientProfile> feasible,ExperimentConfig c,int round,SelectionHistory history,FairnessCreditState state) {
        var settings=c.fuzzySelection();settings.check(c.selection());
        var criteria=ORDER.stream().filter(key->settings.weights.getOrDefault(key,0.)>0)
                .map(key->new FuzzyDecisionMatrix.Criterion(key,key.equals("estimatedTime")?FuzzyDecisionMatrix.Type.COST:FuzzyDecisionMatrix.Type.BENEFIT,settings.weights.get(key))).toList();
        Map<Integer,List<TriangularFuzzyNumber>> rows=new TreeMap<>();Map<Integer,Map<String,Double>> observations=new TreeMap<>();
        double maxDeficit=feasible.stream().mapToDouble(p->deficit(p.clientId,c,history,state)).max().orElse(0);
        for(var p:feasible) {
            if(p.selectionCount<0 || p.completionCount<0 || p.completionCount>p.selectionCount) throw new IllegalArgumentException("Invalid client history: "+p.clientId);
            double time=p.estimate(c);FuzzySelectionConfig.nonnegative(time);time=Math.max(settings.epsilon,time);
            double alpha=p.completionCount+settings.reliabilityAlpha,beta=p.selectionCount-p.completionCount+settings.reliabilityBeta;
            double reliability=alpha/(alpha+beta);
            if(settings.observationNoise!=null) {
                time=settings.observationNoise.observe(time,c.seed(),round,p.clientId,"time");
                reliability=settings.observationNoise.observe(reliability,c.seed(),round,p.clientId,"reliability");
            }
            double utility=settings.learningUtilityPrior;
            if(p.recentTrainingLoss!=null) {FuzzySelectionConfig.nonnegative(p.recentTrainingLoss);utility=1-1/(1+p.recentTrainingLoss);}
            double fairness=maxDeficit==0?0:deficit(p.clientId,c,history,state)/maxDeficit;
            double stale=p.selectionCount==0?1:Math.min(1,Math.max(0,round-p.lastSelectedRound)/(double)Math.max(1,round));
            Map<String,Double> crisp=new LinkedHashMap<>();crisp.put("estimatedTime",time);crisp.put("reliability",reliability);
            crisp.put("learningUtility",utility);crisp.put("fairnessDeficit",fairness);crisp.put("selectionStaleness",stale);
            List<TriangularFuzzyNumber> row=new ArrayList<>();
            for(var criterion:criteria) {
                String key=criterion.name();double x=crisp.get(key),u=settings.uncertaintyFallback;
                if(settings.uncertaintyMode.equals("crisp")) u=0;
                else if(settings.uncertaintyMode.equals("history_based")) {
                    u=switch(key) {
                        case "reliability" -> Math.min(settings.uncertaintyMax,settings.uncertaintyScale*Math.sqrt(reliability*(1-reliability)/(alpha+beta+1)));
                        case "fairnessDeficit","selectionStaleness" -> 0;
                        default -> settings.uncertaintyFallback/Math.sqrt(p.selectionCount+1.0);
                    };
                }
                if(settings.uncertaintyMode.equals("error_calibrated")) {
                    u=switch(key) {
                        case "estimatedTime" -> settings.calibratedWidth(p.timeResiduals);
                        case "reliability" -> settings.calibratedWidth(p.reliabilityResiduals);
                        default -> settings.uncertaintyFallback;
                    };
                }
                u=(key.equals("fairnessDeficit")||key.equals("selectionStaleness"))?0:Math.min(settings.uncertaintyMax,u);
                row.add(key.equals("estimatedTime")?new TriangularFuzzyNumber(Math.max(settings.epsilon,x*(1-u)),Math.max(settings.epsilon,x),Math.max(settings.epsilon,x*(1+u)))
                        :new TriangularFuzzyNumber(Math.max(0,x-u),x,Math.min(1,x+u)));
            }
            if(rows.put(p.clientId,row)!=null) throw new IllegalArgumentException("Duplicate client ID");
            observations.put(p.clientId,Collections.unmodifiableMap(crisp));
        }
        return new Extracted(new FuzzyDecisionMatrix(criteria,rows),Collections.unmodifiableMap(observations));
    }
    private double deficit(int id,ExperimentConfig c,SelectionHistory history,FairnessCreditState state) {
        var prior=history.prior(id);
        return FuzzySelectionConfig.usesCredit(c.selection())?state.deficits.getOrDefault(id,0.):Math.max(0,prior.entitlement-prior.selections);
    }
}
