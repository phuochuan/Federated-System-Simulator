package com.huanphan.ferderatedsystem.selection.fuzzy;

import java.util.*;

public record FuzzyDecisionMatrix(List<Criterion> criteria,Map<Integer,List<TriangularFuzzyNumber>> rows) {
    public enum Type {BENEFIT,COST}
    public record Criterion(String name,Type type,double weight) {
        public Criterion {Objects.requireNonNull(name);Objects.requireNonNull(type);FuzzySelectionConfig.positive(weight);}
    }
    public FuzzyDecisionMatrix {
        criteria=List.copyOf(criteria);
        if(criteria.isEmpty() || Math.abs(criteria.stream().mapToDouble(Criterion::weight).sum()-1)>1e-9
                || criteria.stream().map(Criterion::name).distinct().count()!=criteria.size()) throw new IllegalArgumentException("Invalid criterion weights/names");
        var copy=new TreeMap<Integer,List<TriangularFuzzyNumber>>();
        for(var row:rows.entrySet()) {
            if(row.getKey()<0 || row.getValue().size()!=criteria.size()) throw new IllegalArgumentException("Invalid decision matrix row");
            copy.put(row.getKey(),List.copyOf(row.getValue()));
        }
        rows=Collections.unmodifiableMap(copy);
    }
}
