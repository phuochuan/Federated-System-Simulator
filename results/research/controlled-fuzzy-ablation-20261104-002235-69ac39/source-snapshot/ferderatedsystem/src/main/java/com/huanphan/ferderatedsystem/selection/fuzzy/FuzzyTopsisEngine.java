package com.huanphan.ferderatedsystem.selection.fuzzy;

import java.util.*;

/** Linear fuzzy benefit/cost normalization, data-derived componentwise fuzzy ideals, vertex distances. */
public final class FuzzyTopsisEngine {
    public record Distance(double positive,double negative) {}
    public record Result(Map<Integer,Double> scores,Map<Integer,Distance> distances,FuzzyDecisionMatrix normalized,
                         FuzzyDecisionMatrix weighted,List<TriangularFuzzyNumber> positiveIdeal,List<TriangularFuzzyNumber> negativeIdeal) {}
    public Result rank(FuzzyDecisionMatrix matrix,double epsilon) {
        FuzzySelectionConfig.positive(epsilon);
        var normalized=new TreeMap<Integer,List<TriangularFuzzyNumber>>();
        var weighted=new TreeMap<Integer,List<TriangularFuzzyNumber>>();
        matrix.rows().keySet().forEach(id->{normalized.put(id,new ArrayList<>());weighted.put(id,new ArrayList<>());});
        List<TriangularFuzzyNumber> plus=new ArrayList<>(),minus=new ArrayList<>();
        for(int j=0;j<matrix.criteria().size() && !matrix.rows().isEmpty();j++) {
            final int column=j;var criterion=matrix.criteria().get(j);
            var values=new CriterionNormalizer().normalize(matrix.rows().values().stream().map(row->row.get(column)).toList(),criterion.type(),epsilon);
            int i=0;
            for(int id:matrix.rows().keySet()) {normalized.get(id).add(values.get(i));weighted.get(id).add(values.get(i++).multiply(criterion.weight()));}
            var cells=weighted.values().stream().map(row->row.get(column)).toList();
            plus.add(new TriangularFuzzyNumber(cells.stream().mapToDouble(TriangularFuzzyNumber::lower).max().orElseThrow(),
                    cells.stream().mapToDouble(TriangularFuzzyNumber::middle).max().orElseThrow(),cells.stream().mapToDouble(TriangularFuzzyNumber::upper).max().orElseThrow()));
            minus.add(new TriangularFuzzyNumber(cells.stream().mapToDouble(TriangularFuzzyNumber::lower).min().orElseThrow(),
                    cells.stream().mapToDouble(TriangularFuzzyNumber::middle).min().orElseThrow(),cells.stream().mapToDouble(TriangularFuzzyNumber::upper).min().orElseThrow()));
        }
        Map<Integer,Double> scores=new TreeMap<>();Map<Integer,Distance> distances=new TreeMap<>();
        for(var row:weighted.entrySet()) {
            double dp=0,dn=0;
            for(int j=0;j<plus.size();j++) {dp+=row.getValue().get(j).vertexDistance(plus.get(j));dn+=row.getValue().get(j).vertexDistance(minus.get(j));}
            double cc=dp+dn<=epsilon?.5:dn/(dp+dn);
            if(!Double.isFinite(cc)||cc<0||cc>1) throw new IllegalStateException("Nonfinite/out-of-range TOPSIS score");
            scores.put(row.getKey(),cc);distances.put(row.getKey(),new Distance(dp,dn));
        }
        return new Result(Collections.unmodifiableMap(scores),Collections.unmodifiableMap(distances),new FuzzyDecisionMatrix(matrix.criteria(),normalized),
                new FuzzyDecisionMatrix(matrix.criteria(),weighted),List.copyOf(plus),List.copyOf(minus));
    }
}
