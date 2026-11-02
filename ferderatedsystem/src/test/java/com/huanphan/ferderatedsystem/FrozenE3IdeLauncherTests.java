package com.huanphan.ferderatedsystem;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class FrozenE3IdeLauncherTests {
    @TempDir Path temp;
    @Test void workspaceIsFoundFromModuleWorkingDirectory() throws Exception {
        Files.createDirectories(temp.resolve("configurations"));
        Files.writeString(temp.resolve("configurations/fuzzy-uncertainty.json"),"{}");
        Path module=Files.createDirectories(temp.resolve("ferderatedsystem/subfolder"));
        assertEquals(temp,FrozenE3IdeLauncher.workspace(module));
    }
    @Test void ambiguousArgumentsFailClosed() {
        assertThrows(IllegalArgumentException.class,()->FrozenE3IdeLauncher.arguments(new String[]{"--unknown=yes"}));
        assertThrows(IllegalArgumentException.class,()->FrozenE3IdeLauncher.arguments(new String[]{"--batch=a","--batch=b"}));
        assertEquals("12",FrozenE3IdeLauncher.arguments(new String[]{"--run-budget=12"}).get("run-budget"));
    }
    @Test void originalSourceAndJarAreRequiredWithoutRewritingIdentities() throws Exception {
        var json=new ObjectMapper();Path batch=Files.createDirectories(temp.resolve("artifacts/batch"));
        Path source=temp.resolve("scientific.java");Files.writeString(source,"original");
        Path jar=batch.resolve("coordinator.jar");Files.writeString(jar,"frozen-jar");
        json.writeValue(batch.resolve("source-identity.json").toFile(),Map.of("scientific.java",FrozenE3IdeLauncher.hash(source)));
        json.writeValue(batch.resolve("build-identity.json").toFile(),Map.of("jarSHA256",FrozenE3IdeLauncher.hash(jar)));
        FrozenE3IdeLauncher.verifySources(temp,batch);
        Files.writeString(source,"changed");
        assertThrows(IllegalStateException.class,()->FrozenE3IdeLauncher.verifySources(temp,batch));
        Files.writeString(source,"original");Files.writeString(jar,"changed-jar");
        assertThrows(IllegalStateException.class,()->FrozenE3IdeLauncher.verifySources(temp,batch));
    }
}
