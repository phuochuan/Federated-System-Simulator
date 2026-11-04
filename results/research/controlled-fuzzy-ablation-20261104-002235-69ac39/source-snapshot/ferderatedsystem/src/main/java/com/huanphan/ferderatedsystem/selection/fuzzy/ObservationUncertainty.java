package com.huanphan.ferderatedsystem.selection.fuzzy;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.nio.ByteBuffer;

/** Stateless exogenous observation channels; never reads or mutates future events. */
public final class ObservationUncertainty {
    public String scenario="U0";
    public boolean timing=true,reliability=true;
    public double bias=.2,biasedFraction=.3;
    public void check() {
        if(!java.util.Set.of("U0","U1","U2","U3").contains(scenario)) throw new IllegalArgumentException("Unknown observation scenario");
        FuzzySelectionConfig.unit(bias);FuzzySelectionConfig.unit(biasedFraction);
    }
    private static double draw(long seed,int round,int id,String channel) {
        try {
            byte[] hash=MessageDigest.getInstance("SHA-256").digest(("observation-v1|"+seed+"|"+round+"|"+id+"|"+channel).getBytes(StandardCharsets.UTF_8));
            return (ByteBuffer.wrap(hash).getLong()>>>11)*0x1.0p-53;
        } catch(Exception e) {throw new IllegalStateException(e);}
    }
    public double observe(double x,long seed,int round,int id,String channel) {
        if((channel.equals("time")&&!timing)||(channel.equals("reliability")&&!reliability)) return x;
        double delta=switch(scenario) {
            case "U1" -> .1*(2*draw(seed,round,id,channel)-1);
            case "U2" -> .3*(2*draw(seed,round,id,channel)-1);
            case "U3" -> draw(seed,0,id,"subset")<biasedFraction?(draw(seed,0,id,"sign")<.5?-bias:bias):0;
            default -> 0;
        };
        return channel.equals("time")?Math.max(1e-9,x*(1+delta)):Math.max(0,Math.min(1,x*(1+delta)));
    }
}
