package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Exogenous events for EVERY client/round; no dependence on selection, RAM outcomes or job order. */
final class ScenarioTrace {
    private ScenarioTrace() {}
    record Loaded(JsonNode document,String hash) {
        JsonNode round(int round) {return document.path("rounds").get(round-1);}
        JsonNode event(int round,int client) {return round(round).path("clients").get(client);}
    }
    static ObjectNode generate(ExperimentConfig c,ObjectMapper json) {
        var trace=json.createObjectNode();trace.put("version",1);trace.put("generator","sha256-independent-channels-v1");
        trace.set("scenario",scenario(c,json));
        var rounds=trace.putArray("rounds");
        for(int round=1;round<=c.rounds();round++) {
            var entry=rounds.addObject();entry.put("roundId",round);var clients=entry.putArray("clients");
            for(int id=0;id<c.totalClients();id++) clients.addObject().put("clientId",id)
                    .put("available",draw(c.seed(),round,id,"availability")<c.availability())
                    .put("dropoutEvent",draw(c.seed(),round,id,"dropout")<c.dropout())
                    .put("jitterMultiplier",1+c.jitter()*(2*draw(c.seed(),round,id,"jitter")-1));
        }
        return trace;
    }
    private static ObjectNode scenario(ExperimentConfig c,ObjectMapper json) {
        var node=json.createObjectNode();node.put("seed",(int)c.seed()).put("rounds",c.rounds()).put("totalClients",c.totalClients())
                .put("resourceProfile",c.resourceProfile()).put("availability",c.availability()).put("dropout",c.dropout())
                .put("jitter",c.jitter()).put("requiredRamMb",c.requiredRamMb());
        if(c.deadlineSeconds()==null) node.putNull("deadlineSeconds");else node.put("deadlineSeconds",c.deadlineSeconds());
        return node;
    }
    static Loaded load(ExperimentConfig c,ObjectMapper json,Path root) throws Exception {
        Path path=root.resolve(c.scenarioTracePath()).normalize().toRealPath();
        if(!path.startsWith(root.toRealPath())) throw new IllegalArgumentException("Trace must stay within workspace");
        byte[] bytes=Files.readAllBytes(path);var document=json.readTree(bytes);
        // Full comparison also validates IDs/order/ranges and detects edits to counterfactual client events.
        if(!document.equals(generate(c,json))) throw new IllegalArgumentException("Scenario trace content/config mismatch: "+path);
        return new Loaded(document,HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)));
    }
    private static double draw(long seed,int round,int client,String channel) {
        try {
            byte[] hash=MessageDigest.getInstance("SHA-256").digest(("minifls-trace-v1|"+seed+"|"+round+"|"+client+"|"+channel).getBytes(StandardCharsets.UTF_8));
            long bits=java.nio.ByteBuffer.wrap(hash).getLong();return (bits>>>11)*0x1.0p-53;
        } catch(Exception e) {throw new IllegalStateException(e);}
    }
}
