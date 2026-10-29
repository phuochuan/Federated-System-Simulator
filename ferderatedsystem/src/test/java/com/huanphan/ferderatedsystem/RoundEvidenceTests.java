package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class RoundEvidenceTests {
    @TempDir Path root;
    private final ObjectMapper json=new ObjectMapper();

    @Test void indexedEvidenceReadsLargeUnicodeRoundsInAnyOrder() throws Exception {
        Path file=root.resolve("rounds.json");
        String payload="Tiếng Việt 🧪".repeat(2000);
        try(var out=json.getFactory().createGenerator(file.toFile(),com.fasterxml.jackson.core.JsonEncoding.UTF8)) {
            out.useDefaultPrettyPrinter();out.writeStartArray();
            for(int i=0;i<700;i++) {
                out.writeStartObject();out.writeNumberField("roundId",i+1);out.writeStringField("payload",payload);out.writeEndObject();
            }
            out.writeEndArray();
        }
        var rounds=new IndexedRoundEvidence(file,json);
        assertEquals(700,rounds.size());
        for(int i:List.of(699,0,300,1)) {
            assertEquals(i+1,rounds.get(i).path("roundId").asInt());
            assertEquals(payload,rounds.get(i).path("payload").asText());
        }
        assertThrows(IndexOutOfBoundsException.class,()->rounds.get(700));
        assertThrows(UnsupportedOperationException.class,()->rounds.clear());
        // Reads close their file handles, including on Windows.
        Files.move(file,root.resolve("moved.json"));
    }

    @Test void streamingHashPreservesCanonicalIdentity() throws Exception {
        var value=json.readTree("""
                {"z":[{"z":null,"a":"Tiếng Việt 🧪\\n\\\""},1.0,true],"a":-0.5}
                """);
        var canonical=json.readTree("""
                {"a":-0.5,"z":[{"a":"Tiếng Việt 🧪\\n\\\"","z":null},1.0,true]}
                """);
        String expected=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(canonical.toString().getBytes(StandardCharsets.UTF_8)));
        assertEquals(expected,ResearchProvenance.hash(value));
    }

    @Test void streamedExportsRemainImmutableAndFailedWritesPreserveTarget() throws Exception {
        Path file=root.resolve("nested/evidence.json");var value=json.readTree("{\"a\":1,\"b\":[2,3]}");
        ResearchProvenance.save(file,value,json,true);
        ResearchProvenance.save(file,json.readTree("{\"b\":[2,3],\"a\":1}"),json,true);
        assertThrows(IllegalStateException.class,()->ResearchProvenance.save(file,json.readTree("{}"),json,true));
        assertThrows(Exception.class,()->ResearchProvenance.saveJson(file,new Object(),json));
        assertEquals(value,json.readTree(file.toFile()));
        try(var files=Files.list(file.getParent())) {assertEquals(1,files.count());}
        Path rounds=root.resolve("rounds.json");ResearchProvenance.saveJson(rounds,List.of(value,value),json);
        assertEquals(List.of(value,value),new IndexedRoundEvidence(rounds,json));
    }

    @Test void rejectsMalformedRoundExports() throws Exception {
        Path file=root.resolve("rounds.json");
        for(String invalid:List.of("{}","[1]","[{\"roundId\":1}","[] {}")) {
            Files.writeString(file,invalid);
            assertThrows(java.io.IOException.class,()->new IndexedRoundEvidence(file,json));
        }
    }
}
