package com.huanphan.ferderatedsystem;

import com.huanphan.ferderatedsystem.selection.fuzzy.*;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class FuzzyUncertaintyTests {
    private FuzzyDecisionMatrix matrix() {
        return new FuzzyDecisionMatrix(List.of(
            new FuzzyDecisionMatrix.Criterion("estimatedTime",FuzzyDecisionMatrix.Type.COST,.4),
            new FuzzyDecisionMatrix.Criterion("reliability",FuzzyDecisionMatrix.Type.BENEFIT,.35),
            new FuzzyDecisionMatrix.Criterion("learningUtility",FuzzyDecisionMatrix.Type.BENEFIT,.25)),
            new TreeMap<>(Map.of(1,List.of(t(2),t(.9),t(.2)),2,List.of(t(4),t(.7),t(.8)),3,List.of(t(3),t(.8),t(.5)))));
    }
    private TriangularFuzzyNumber t(double x) {return new TriangularFuzzyNumber(x,x,x);}
    @Test void conventionalCrispIndependentScalarReference() {
        var matrix=matrix();var actual=new CrispTopsisEngine().rank(matrix,1e-9);
        double[][] x={{2,.9,.2},{4,.7,.8},{3,.8,.5}};
        double[] weights={.4,.35,.25};
        // Deliberately separate array implementation using squared sums.
        for(int j=0;j<3;j++) {
            double norm=Math.sqrt(x[0][j]*x[0][j]+x[1][j]*x[1][j]+x[2][j]*x[2][j]);
            for(int i=0;i<3;i++) x[i][j]=x[i][j]/norm*weights[j];
        }
        for(int i=0;i<3;i++) {
            double plus=0,minus=0;
            for(int j=0;j<3;j++) {
                double lo=Math.min(x[0][j],Math.min(x[1][j],x[2][j])), hi=Math.max(x[0][j],Math.max(x[1][j],x[2][j]));
                plus+=Math.pow(x[i][j]-(j==0?lo:hi),2);minus+=Math.pow(x[i][j]-(j==0?hi:lo),2);
            }
            double dp=Math.sqrt(plus),dn=Math.sqrt(minus);
            assertEquals(dn/(dp+dn),actual.get(i+1),1e-12);
        }
    }
    @Test void zeroWidthFuzzyDoesNotMasqueradeAsCrisp() {
        var crisp=new CrispTopsisEngine().rank(matrix(),1e-9);
        var fuzzy=new FuzzyTopsisEngine().rank(matrix(),1e-9).scores();
        assertTrue(crisp.keySet().stream().anyMatch(i->Math.abs(crisp.get(i)-fuzzy.get(i))>1e-4));
        assertEquals(List.of(2,7),CrispTopsisEngine.order(Map.of(7,.5,2,.5)));
    }
    @Test void noiseIsPairedDeterministicAndLeavesProfilesUntouched() {
        var noise=new ObservationUncertainty();noise.scenario="U2";
        var client=new ClientProfile(1,100,100,"heterogeneous");client.estimatedSeconds=2.;
        for(int round=1;round<100;round++) {
            double observed=noise.observe(2,42,round,client.clientId,"time");
            assertEquals(observed,noise.observe(2,42,round,client.clientId,"time"));
            assertTrue(observed>=1.4 && observed<=2.6);
        }
        assertEquals(2.,client.estimatedSeconds);assertEquals(0,client.selectionCount);
        noise.timing=false;assertEquals(2,noise.observe(2,42,1,1,"time"));
        noise.scenario="U3";noise.timing=true;noise.biasedFraction=1;
        assertEquals(noise.observe(2,42,1,1,"time"),noise.observe(2,42,70,1,"time"));
    }
    @Test void residualCalibrationIsBoundedSparseAndRobust() {
        var settings=new FuzzySelectionConfig();
        assertEquals(.1,settings.calibratedWidth(List.of(.01,.03)));
        assertEquals(.04,settings.calibratedWidth(List.of(.01,.02,.03,.04,99.)));
        assertEquals(.45,settings.calibratedWidth(List.of(9.,9.,9.,9.,9.)));
        var observations=new ArrayList<>(List.of(.1,.2,.3,.4,.5));
        var frozen=new ArrayList<>(observations);settings.calibratedWidth(observations);assertEquals(frozen,observations);
    }
}
