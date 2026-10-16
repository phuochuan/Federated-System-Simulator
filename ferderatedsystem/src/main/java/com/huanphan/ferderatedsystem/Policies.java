package com.huanphan.ferderatedsystem;

import java.util.*;

public final class Policies {
    private Policies() {}

    public interface ClientSelector {
        List<ClientProfile> select(List<ClientProfile> eligible, ExperimentConfig config, Random rng);
    }
    public static class RandomSelector implements ClientSelector {
        public List<ClientProfile> select(List<ClientProfile> eligible, ExperimentConfig c, Random rng) {
            var shuffled=new ArrayList<>(eligible);
            Collections.shuffle(shuffled,rng);
            return new ArrayList<>(shuffled.subList(0,Math.min(c.selectedPerRound(),shuffled.size())));
        }
    }
    public static class ResourceAwareSelector implements ClientSelector {
        public List<ClientProfile> select(List<ClientProfile> eligible, ExperimentConfig c, Random rng) {
            var feasible=new ArrayList<>(eligible.stream().filter(p -> p.ramMb >= c.requiredRamMb())
                    .filter(p -> c.deadlineSeconds()==null || p.estimate(c)<=c.deadlineSeconds()).toList());
            int k=Math.min(c.selectedPerRound(),feasible.size());
            int explore=Math.min(k,(int)Math.ceil(k*c.exploration()));
            Collections.shuffle(feasible,rng);
            var chosen=new ArrayList<>(feasible.subList(0,explore));
            feasible.removeAll(chosen);
            feasible.sort(Comparator.comparingDouble((ClientProfile p) -> p.estimate(c)
                    / ((p.completionCount+1.0)/(p.selectionCount+1.0))).thenComparingInt(p -> p.clientId));
            chosen.addAll(feasible.subList(0,k-explore));
            return chosen;
        }
    }
    public interface AggregationStrategy { List<Double> weights(List<Integer> samples, List<Double> losses); }
    public static class FedAvg implements AggregationStrategy {
        public List<Double> weights(List<Integer> samples,List<Double> losses) {
            if(samples.isEmpty() || samples.stream().anyMatch(n -> n<=0)) throw new IllegalArgumentException("Positive sample counts required");
            double sum=samples.stream().mapToDouble(Integer::doubleValue).sum();
            return samples.stream().map(n -> n/sum).toList();
        }
    }
    public static class FedLBW implements AggregationStrategy {
        public List<Double> weights(List<Integer> samples,List<Double> losses) {
            if(losses.isEmpty() || losses.size()!=samples.size() || losses.stream().anyMatch(l -> !Double.isFinite(l) || l<0))
                throw new IllegalArgumentException("Finite nonnegative proxy losses required");
            // Explicit numerical variant: clamp loss to 1e-12, then scale to avoid reciprocal overflow.
            double minimum=losses.stream().mapToDouble(l -> Math.max(l,1e-12)).min().orElseThrow();
            var inverse=losses.stream().map(l -> minimum/Math.max(l,1e-12)).toList();
            double sum=inverse.stream().mapToDouble(Double::doubleValue).sum();
            return inverse.stream().map(w -> w/sum).toList();
        }
    }
}
