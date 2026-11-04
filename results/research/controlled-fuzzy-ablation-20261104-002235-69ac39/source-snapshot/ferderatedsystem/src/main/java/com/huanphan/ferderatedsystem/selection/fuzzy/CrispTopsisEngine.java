package com.huanphan.ferderatedsystem.selection.fuzzy;

import java.util.*;

/** Conventional vector normalization, weighted Euclidean distance, column extrema ideals.
 * Zero columns are uninformative. Identical alternatives score .5; ties use ascending ID.
 * Uses only the middle observations: this is NOT the existing zero-width fuzzy algorithm.
 */
public final class CrispTopsisEngine {
    public Map<Integer,Double> rank(FuzzyDecisionMatrix matrix,double epsilon) {
        Map<Integer,double[]> weighted=new TreeMap<>();
        matrix.rows().keySet().forEach(id->weighted.put(id,new double[matrix.criteria().size()]));
        double[] plus=new double[matrix.criteria().size()],minus=plus.clone();
        for(int j=0;j<plus.length && !weighted.isEmpty();j++) {
            double norm=0;for(var row:matrix.rows().values()) norm=Math.hypot(norm,row.get(j).middle());
            var criterion=matrix.criteria().get(j);double lo=Double.POSITIVE_INFINITY,hi=Double.NEGATIVE_INFINITY;
            for(var entry:weighted.entrySet()) {
                double value=norm<=epsilon?0:criterion.weight()*matrix.rows().get(entry.getKey()).get(j).middle()/norm;
                entry.getValue()[j]=value;lo=Math.min(lo,value);hi=Math.max(hi,value);
            }
            boolean cost=criterion.type()==FuzzyDecisionMatrix.Type.COST;
            plus[j]=cost?lo:hi;minus[j]=cost?hi:lo;
        }
        Map<Integer,Double> scores=new TreeMap<>();
        for(var entry:weighted.entrySet()) {
            double dp=0,dn=0;for(int j=0;j<plus.length;j++) {
                dp=Math.hypot(dp,entry.getValue()[j]-plus[j]);dn=Math.hypot(dn,entry.getValue()[j]-minus[j]);
            }
            scores.put(entry.getKey(),dp+dn<=epsilon?.5:dn/(dp+dn));
        }
        return scores;
    }
    public static List<Integer> order(Map<Integer,Double> scores) {
        return scores.keySet().stream().sorted(Comparator.<Integer>comparingDouble(scores::get).reversed().thenComparingInt(i->i)).toList();
    }
}
