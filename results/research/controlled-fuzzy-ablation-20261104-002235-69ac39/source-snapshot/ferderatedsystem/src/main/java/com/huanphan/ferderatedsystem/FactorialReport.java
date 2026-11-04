package com.huanphan.ferderatedsystem;

import java.util.*;
import static com.huanphan.ferderatedsystem.ControlledExperiments.RunResult;

final class FactorialReport {
    private FactorialReport() {}
    static String render(String source,List<Long> seeds,List<Double> targets,List<RunResult> c1,List<RunResult> c2,
                         List<RunResult> c3,List<RunResult> c4,List<RunResult> c5,Exception failure) {
        boolean complete=failure==null && List.of(c1,c2,c3,c4,c5).stream().allMatch(r->r.size()==seeds.size());
        StringBuilder out=new StringBuilder("C: 2x2 FACTORIAL AGGREGATION x SELECTION\nStatus: "+(complete?"COMPLETED":"INCOMPLETE")+"\n");
        out.append("C1=FedAvg/Random, C2=FedAvg/Resource-aware, C3=FedLBW/Random, C4=FedLBW/Resource-aware\n");
        out.append("C5=FedAvg/Feasible Random; additional pair C2-C5 reuses the existing C2 result.\n");
        out.append("All five use the same heterogeneous scenario, Non-IID alpha=0.5, initial weights and full population traces per seed.\n");
        if(complete) {
            out.append("\nINTERACTION = (C4-C3) - (C2-C1), computed per seed, raw metric units.\n");
            for(String metric:ComparisonReport.METRICS) {
                List<Double> interactions=new ArrayList<>();
                for(int i=0;i<seeds.size();i++) interactions.add(interaction(c1.get(i),c2.get(i),c3.get(i),c4.get(i),metric));
                out.append(metric).append(" interaction mean +/- sample SD: ").append(ComparisonReport.stats(interactions)).append("\n");
            }
            out.append("Interaction is a descriptive difference-in-differences, not a significance test or proof of a hybrid improvement.\n");
        }
        out.append("\n--- SELECTION EFFECT UNDER FEDAVG ---\n").append(ComparisonReport.render("C2 vs C1","selection",source,seeds,targets,c1,c2,failure));
        out.append("\n--- SELECTION EFFECT UNDER FEDLBW ---\n").append(ComparisonReport.render("C4 vs C3","selection",source,seeds,targets,c3,c4,failure));
        out.append("\n--- AGGREGATION EFFECT UNDER RANDOM ---\n").append(ComparisonReport.render("C3 vs C1","aggregation",source,seeds,targets,c1,c3,failure));
        out.append("\n--- AGGREGATION EFFECT UNDER RESOURCE-AWARE ---\n").append(ComparisonReport.render("C4 vs C2","aggregation",source,seeds,targets,c2,c4,failure));
        out.append("\n--- FEASIBLE RANDOM VS RESOURCE-AWARE UNDER FEDAVG ---\n")
                .append("Both use the same pre-round RAM/deadline feasibility rule; candidate sets can diverge with policy-specific timing histories. Neither reads future dropout/jitter.\n")
                .append(ComparisonReport.render("Does resource-aware ranking improve over feasibility filtering plus random sampling? C2 vs C5",
                        "selection",source,seeds,targets,c5,c2,failure));
        return out.toString();
    }
    static double interaction(RunResult c1,RunResult c2,RunResult c3,RunResult c4,String metric) {
        return (ComparisonReport.value(c4,metric)-ComparisonReport.value(c3,metric))
                -(ComparisonReport.value(c2,metric)-ComparisonReport.value(c1,metric));
    }
}
