package com.huanphan.ferderatedsystem;

import java.util.*;

/** Các chiến lược lựa chọn client; thuật toán aggregation ở Python minifls.methods. */
public final class Policies {
    private Policies() {}

    public interface ClientSelector {
        List<ClientProfile> select(List<ClientProfile> eligible, ExperimentConfig config, Random rng);
    }
    /** Same observable RAM/deadline predicate for feasible-random and resource-aware. */
    public static boolean isFeasible(ClientProfile client,ExperimentConfig c) {
        return isFeasible(client,c,0);
    }
    public static boolean isFeasible(ClientProfile client,ExperimentConfig c,int round) {
        double estimate=client.estimate(c);
        if(c.fuzzySelection()!=null && c.fuzzySelection().observationNoise!=null)
            estimate=c.fuzzySelection().observationNoise.observe(estimate,c.seed(),round,client.clientId,"time");
        return client.ramMb>=c.requiredRamMb() && (c.deadlineSeconds()==null || estimate<=c.deadlineSeconds());
    }
    public static List<ClientProfile> feasibleClients(List<ClientProfile> eligible,ExperimentConfig c) {
        return new ArrayList<>(eligible.stream().filter(p->isFeasible(p,c)).toList());
    }
    public static List<ClientProfile> feasibleClients(List<ClientProfile> eligible,ExperimentConfig c,int round) {
        return new ArrayList<>(eligible.stream().filter(p->isFeasible(p,c,round)).toList());
    }
    public static class RandomSelector implements ClientSelector {
        public List<ClientProfile> select(List<ClientProfile> eligible, ExperimentConfig c, Random rng) {
            // Xáo trộn có seed rồi lấy K phần tử để chọn đều, không lặp trong cùng round.
            var shuffled=new ArrayList<>(eligible);
            Collections.shuffle(shuffled,rng);
            return new ArrayList<>(shuffled.subList(0,Math.min(c.selectedPerRound(),shuffled.size())));
        }
    }
    public static class ResourceAwareSelector implements ClientSelector {
        public List<ClientProfile> select(List<ClientProfile> eligible, ExperimentConfig c, Random rng) {
            // Chỉ dùng profile và lịch sử đã biết trước round, không đọc kết quả tương lai.
            var feasible=feasibleClients(eligible,c);
            int k=Math.min(c.selectedPerRound(),feasible.size());
            // Dành một phần lượt chọn cho exploration để client chưa được thử có cơ hội tham gia.
            int explore=Math.min(k,(int)Math.ceil(k*c.exploration()));
            Collections.shuffle(feasible,rng);
            var chosen=new ArrayList<>(feasible.subList(0,explore));
            feasible.removeAll(chosen);
            // Ưu tiên thời gian ước lượng thấp, có điều chỉnh theo tỷ lệ hoàn thành trong lịch sử.
            feasible.sort(Comparator.comparingDouble((ClientProfile p) -> p.estimate(c)
                    / ((p.completionCount+1.0)/(p.selectionCount+1.0))).thenComparingInt(p -> p.clientId));
            chosen.addAll(feasible.subList(0,k-explore));
            return chosen;
        }
    }
    public static class FeasibleRandomSelector implements ClientSelector {
        public List<ClientProfile> select(List<ClientProfile> eligible,ExperimentConfig c,Random rng) {
            // Uniform sampling without replacement; no completion-time ranking or future traces.
            return new RandomSelector().select(feasibleClients(eligible,c),c,rng);
        }
    }
}
