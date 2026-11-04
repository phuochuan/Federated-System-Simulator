package com.huanphan.ferderatedsystem.selection.fuzzy;

import java.util.*;

public final class CriterionNormalizer {
    public List<TriangularFuzzyNumber> normalize(List<TriangularFuzzyNumber> column,FuzzyDecisionMatrix.Type type,double epsilon) {
        FuzzySelectionConfig.positive(epsilon);
        if(column.isEmpty()) return List.of();
        double maximum=column.stream().mapToDouble(TriangularFuzzyNumber::upper).max().orElseThrow();
        if(maximum<=epsilon) return column.stream().map(v->new TriangularFuzzyNumber(1,1,1)).toList();
        if(type==FuzzyDecisionMatrix.Type.BENEFIT) return column.stream().map(v->v.divide(maximum)).toList();
        double minimum=column.stream().mapToDouble(v->Math.max(epsilon,v.lower())).min().orElseThrow();
        return column.stream().map(v->new TriangularFuzzyNumber(minimum/Math.max(epsilon,v.upper()),
                minimum/Math.max(epsilon,v.middle()),minimum/Math.max(epsilon,v.lower()))).toList();
    }
}
