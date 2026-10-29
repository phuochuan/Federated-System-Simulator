package com.huanphan.ferderatedsystem;

/** Duration assumptions are protocol inputs; measured worker time is always retained. */
public record SimulationTimingConfig(String mode, double secondsPerSample) {
    public void check() {
        if(!"measured".equals(mode) && !"deterministic".equals(mode))
            throw new IllegalArgumentException("timing.mode must be measured or deterministic");
        if(!Double.isFinite(secondsPerSample) || secondsPerSample<=0)
            throw new IllegalArgumentException("timing.secondsPerSample must be finite and positive");
    }
    public boolean deterministic() {return "deterministic".equals(mode);}
    public double durationMs(ClientProfile client, ExperimentConfig config, double measuredMs) {
        return deterministic()?client.numSamples*config.localEpochs()*secondsPerSample*1000:measuredMs;
    }
}
