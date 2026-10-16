package com.huanphan.ferderatedsystem;

import jakarta.validation.constraints.*;

public record ExperimentConfig(
        @NotBlank @Pattern(regexp="[A-Za-z0-9_-]{1,60}") String experimentId,
        @NotBlank String manifestPath,
        @Min(1) @Max(10000) int totalClients,
        @Min(1) int selectedPerRound,
        @Min(1) @Max(100000) int rounds,
        @Min(0) @Max(1000000000) long seed,
        @NotNull @Pattern(regexp="random|resource_aware") String selection,
        @NotNull @Pattern(regexp="fedavg|fedlbw") String aggregation,
        @Min(1) @Max(100) int localEpochs,
        @Min(1) @Max(65536) int batchSize,
        @DecimalMin(value="0", inclusive=false) @DecimalMax("10") double learningRate,
        boolean simulationEnabled,
        @NotNull @Pattern(regexp="homogeneous|cpu|ram|heterogeneous") String resourceProfile,
        @DecimalMin("0") @DecimalMax("1") double availability,
        @DecimalMin("0") @DecimalMax("1") double dropout,
        @DecimalMin("0") @DecimalMax(value="1",inclusive=false) double jitter,
        @DecimalMin("0") @DecimalMax("1") double exploration,
        @Positive Double deadlineSeconds,
        @Positive double requiredRamMb,
        @Positive double priorSecondsPerSample,
        @DecimalMin("0") @DecimalMax("1") double targetAccuracy) {
    public void check() {
        if (selectedPerRound > totalClients) throw new IllegalArgumentException("K cannot exceed totalClients");
        double[] values={learningRate, availability, dropout, jitter, exploration, requiredRamMb, priorSecondsPerSample, targetAccuracy};
        for(double v:values) if(!Double.isFinite(v)) throw new IllegalArgumentException("Config must be finite");
        if(deadlineSeconds!=null && !Double.isFinite(deadlineSeconds)) throw new IllegalArgumentException("Deadline must be finite");
    }
}
