package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.huanphan.ferderatedsystem.selection.fuzzy.*;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ControlledAblationTests {
    final ObjectMapper json=new ObjectMapper();
    ObjectNode request() throws Exception {
        var c=new FuzzySelectionTests().config("fuzzy_topsis");
        var clients=new ArrayList<ClientProfile>();
        double[][] x={{2,.9,.2},{4,.7,.8},{3,.8,.5}};
        for(int i=0;i<3;i++) {
            var p=new ClientProfile(i+1,100,100,"homogeneous");p.estimatedSeconds=x[i][0];
            // Beta(1,1): (completion+1)/(selection+2) = .9/.7/.8.
            p.selectionCount=8;p.completionCount=(int)Math.round(x[i][1]*10)-1;
            p.recentTrainingLoss=x[i][2]/(1-x[i][2]);
            p.timeResiduals=new ArrayList<>(List.of(.01,.02,.03,.04,.9));
            p.reliabilityResiduals=new ArrayList<>(List.of(.02,.04,.06,.08,.9));
            clients.add(p);
        }
        var request=json.createObjectNode();request.set("config",json.valueToTree(c));request.put("round",9);
        request.set("selectorInput",json.valueToTree(Map.of("eligibleClients",clients,"history",new SelectionHistory())));
        return request;
    }
    @Test void sameCriteriaFeasibilityAndScoringEngineOnlyWidthsVary() throws Exception {
        var request=request();var original=request.deepCopy();
        var result=new ControlledAblationController(json).replay(request);
        assertEquals(original,request);
        for(int i=0;i<5;i++) {
            var r=result.path("A"+i);
            assertEquals(result.path("A1").path("observations"),r.path("observations"));
            assertEquals(i==0?"CrispTopsisEngine":"FuzzyTopsisEngine",r.path("engine").asText());
            var matrix=json.treeToValue(r.path("matrix"),FuzzyDecisionMatrix.class);
            if(i>0) assertEquals(json.valueToTree(new FuzzyTopsisEngine().rank(matrix,1e-9).scores()),r.path("scores"));
            for(var row:matrix.rows().values()) for(var cell:row) if(i==1) {
                assertEquals(cell.lower(),cell.middle());assertEquals(cell.middle(),cell.upper());
            }
        }
        assertEquals(.1,result.path("A2").path("widths").path("1").path("estimatedTime").asDouble());
        assertEquals(.1/3,result.path("A3").path("widths").path("1").path("estimatedTime").asDouble(),1e-12);
        assertEquals(.04,result.path("A4").path("widths").path("1").path("estimatedTime").asDouble());
        assertEquals(.08,result.path("A4").path("widths").path("1").path("reliability").asDouble());
        var twice=new ControlledAblationController(json).replay(request);
        for(int i=0;i<5;i++) assertEquals(result.path("A"+i).path("ranking"),twice.path("A"+i).path("ranking"));
    }
    @Test void manuallyVerifiedZeroWidthMatrix() throws Exception {
        var r=new ControlledAblationController(json).replay(request()).path("A1");
        // Normalized rows: (1,1,.25), (.5,7/9,1), (2/3,8/9,.625).
        // D-1=.2+.35*2/9=5/18; D+1=.25*.75=3/16.
        assertEquals((5./18)/(5./18+3./16),r.path("scores").path("1").asDouble(),1e-12);
        assertEquals((3./16)/(5./18+3./16),r.path("scores").path("2").asDouble(),1e-12);
        assertEquals(List.of(1,3,2),json.convertValue(r.path("ranking"),new com.fasterxml.jackson.core.type.TypeReference<List<Integer>>(){}));
    }
    @Test void futureFieldsCannotReachReplayAndInvalidRoundFails() throws Exception {
        var request=request();request.put("futureDropout",true);request.put("futureDuration",999999);
        var controller=new ControlledAblationController(json);var first=controller.replay(request);
        request.put("futureDuration",0);request.put("futureDropout",false);
        var second=controller.replay(request);
        assertEquals(first.path("A4").path("scores"),second.path("A4").path("scores"));
        request.put("round",0);assertThrows(IllegalArgumentException.class,()->controller.replay(request));
    }
}
