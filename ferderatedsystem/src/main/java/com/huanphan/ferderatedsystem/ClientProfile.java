package com.huanphan.ferderatedsystem;

public class ClientProfile {
    public int clientId;
    public int numSamples;
    public String tier;
    public double cpu;
    public double ramMb;
    public int selectionCount;
    public int completionCount;
    public int opportunityCount;
    public int lastSelectedRound;
    public int lastCompletedRound;
    public Double estimatedSeconds;
    public Double recentTrainingLoss;
    public String lastStatus = "REGISTERED";

    public ClientProfile() {}
    public ClientProfile(int id, int samples, int population, String profile) {
        clientId=id; numSamples=samples;
        tier=id < population * .4 ? "LOW" : id < population * .8 ? "MEDIUM" : "HIGH";
        cpu=profile.equals("ram") || profile.equals("homogeneous") ? 1 : switch(tier) {case "LOW" -> .5; case "HIGH" -> 2; default -> 1;};
        ramMb=profile.equals("cpu") || profile.equals("homogeneous") ? 1024 : switch(tier) {case "LOW" -> 512; case "HIGH" -> 2048; default -> 1024;};
    }
    public double estimate(ExperimentConfig c) {
        return estimatedSeconds != null ? estimatedSeconds : numSamples * c.localEpochs() * c.priorSecondsPerSample() / cpu;
    }
}
