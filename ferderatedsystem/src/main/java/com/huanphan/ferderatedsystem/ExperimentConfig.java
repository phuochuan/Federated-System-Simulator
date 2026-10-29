package com.huanphan.ferderatedsystem;

import jakarta.validation.constraints.*;
import com.huanphan.ferderatedsystem.selection.fuzzy.FuzzySelectionConfig;

/** Cấu hình bất biến của thí nghiệm; Bean Validation kiểm tra giới hạn từng trường. */
public record ExperimentConfig(
        @NotBlank @Pattern(regexp="[A-Za-z0-9_-]{1,60}") String experimentId,
        @NotBlank String manifestPath,
        @Min(1) @Max(10000) int totalClients,
        @Min(1) int selectedPerRound,
        @Min(1) @Max(100000) int rounds,
        @Min(0) @Max(1000000000) long seed,
        @NotNull @Pattern(regexp="random|feasible_random|resource_aware|fuzzy_topsis|fuzzy_topsis_fair|adaptive_fuzzy_topsis_fair") String selection,
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
        @DecimalMin("0") @DecimalMax("1") double targetAccuracy,
        @Pattern(regexp="mlp_54_128_64_7|mlp_54_256_128_7") String architecture,
        String scenarioTracePath,
        FuzzySelectionConfig fuzzySelection,
        SimulationTimingConfig timing,
        @Pattern(regexp="proxy|test") String evaluationSplit,
        com.fasterxml.jackson.databind.JsonNode provenance,
        @Pattern(regexp="proxy|test") String finalEvaluationSplit) {
    public String effectiveEvaluationSplit() {return evaluationSplit==null?"test":evaluationSplit;}
    public boolean hasProvenance() {return provenance!=null&&!provenance.isNull();}
    public String durationMode() {return timing==null?"measured":timing.mode();}
    public double durationInputMs(ClientProfile client,double measuredMs) {
        return timing==null?measuredMs:timing.durationMs(client,this,measuredMs);
    }
    public void check() {
        // Kiểm tra thêm quan hệ giữa các trường và tính hữu hạn của các số thực.
        if (selectedPerRound > totalClients) throw new IllegalArgumentException("K cannot exceed totalClients");
        double[] values={learningRate, availability, dropout, jitter, exploration, requiredRamMb, priorSecondsPerSample, targetAccuracy};
        for(double v:values) if(!Double.isFinite(v)) throw new IllegalArgumentException("Config must be finite");
        if(deadlineSeconds!=null && !Double.isFinite(deadlineSeconds)) throw new IllegalArgumentException("Deadline must be finite");
        if(FuzzySelectionConfig.isFuzzy(selection)&&fuzzySelection==null) throw new IllegalArgumentException("fuzzySelection config is required for "+selection);
        if(fuzzySelection!=null) fuzzySelection.check(selection);
        if(timing!=null) timing.check();
        if(evaluationSplit!=null && !evaluationSplit.equals("proxy") && !evaluationSplit.equals("test"))
            throw new IllegalArgumentException("evaluationSplit must be proxy or test");
        if(finalEvaluationSplit!=null && !java.util.Set.of("proxy","test").contains(finalEvaluationSplit))
            throw new IllegalArgumentException("finalEvaluationSplit must be proxy or test");
    }
}
