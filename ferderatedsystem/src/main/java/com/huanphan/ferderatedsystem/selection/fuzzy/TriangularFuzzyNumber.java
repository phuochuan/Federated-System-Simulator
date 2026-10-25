package com.huanphan.ferderatedsystem.selection.fuzzy;

public record TriangularFuzzyNumber(double lower,double middle,double upper) {
    public TriangularFuzzyNumber {
        if(!Double.isFinite(lower)||!Double.isFinite(middle)||!Double.isFinite(upper)||lower<0||lower>middle||middle>upper)
            throw new IllegalArgumentException("TFN requires finite 0 <= lower <= middle <= upper");
    }
    public TriangularFuzzyNumber add(TriangularFuzzyNumber b) {return new TriangularFuzzyNumber(lower+b.lower,middle+b.middle,upper+b.upper);}
    public TriangularFuzzyNumber multiply(double value) {
        FuzzySelectionConfig.nonnegative(value);return new TriangularFuzzyNumber(lower*value,middle*value,upper*value);
    }
    public TriangularFuzzyNumber divide(double value) {FuzzySelectionConfig.positive(value);return new TriangularFuzzyNumber(lower/value,middle/value,upper/value);}
    public double vertexDistance(TriangularFuzzyNumber b) {
        return Math.hypot(Math.hypot(lower-b.lower,middle-b.middle),upper-b.upper)/Math.sqrt(3);
    }
}
