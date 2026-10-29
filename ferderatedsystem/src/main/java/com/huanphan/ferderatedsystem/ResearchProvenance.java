package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import org.springframework.boot.system.ApplicationHome;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.security.DigestOutputStream;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import com.fasterxml.jackson.core.JsonGenerator;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Content identities, not timestamps or checkpoint filenames, control research reuse. */
final class ResearchProvenance {
    private ResearchProvenance() {}
    static String hash(Path path) throws Exception {
        var digest=MessageDigest.getInstance("SHA-256");
        try(var in=Files.newInputStream(path)) {byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))>=0) digest.update(buffer,0,n);}
        return HexFormat.of().formatHex(digest.digest());
    }
    static String hash(JsonNode node) throws Exception {
        var digest=MessageDigest.getInstance("SHA-256");
        try(var out=new DigestOutputStream(OutputStream.nullOutputStream(),digest);
            var generator=new ObjectMapper().getFactory().createGenerator(new OutputStreamWriter(out,StandardCharsets.UTF_8))) {
            canonical(node,generator);
        }
        return HexFormat.of().formatHex(digest.digest());
    }
    private static void canonical(JsonNode node,JsonGenerator generator) throws Exception {
        if(node.isObject()) {
            generator.writeStartObject();var names=new TreeSet<String>();node.fieldNames().forEachRemaining(names::add);
            for(String name:names) {generator.writeFieldName(name);canonical(node.get(name),generator);}
            generator.writeEndObject();
        } else if(node.isArray()) {
            generator.writeStartArray();for(var value:node) canonical(value,generator);generator.writeEndArray();
        } else {
            generator.writeTree(node);
        }
    }
    static String javaBuildHash(ObjectMapper json) throws Exception {
        var entries=new TreeMap<String,String>();
        var source=new ApplicationHome(ResearchProvenance.class).getSource();
        if(source!=null) addFiles(source.toPath(),"application",entries);
        int index=0;
        for(String entry:System.getProperty("java.class.path").split(java.io.File.pathSeparator)) {
            var path=Path.of(entry);if(Files.exists(path)) addFiles(path,"classpath/"+(index++),entries);
        }
        if(entries.isEmpty()) throw new IllegalStateException("Cannot identify executing Java build");
        return hash(json.valueToTree(entries));
    }
    private static void addFiles(Path path,String label,Map<String,String> entries) throws Exception {
        if(Files.isRegularFile(path)) entries.put(label+"/"+path.getFileName(),hash(path));
        else if(Files.isDirectory(path)) try(var files=Files.walk(path)) {
            for(Path file:files.filter(Files::isRegularFile).sorted().toList())
                entries.put(label+"/"+path.relativize(file).toString().replace('\\','/'),hash(file));
        }
    }
    static ObjectNode runtime(PythonMLClient worker,ObjectMapper json) throws Exception {
        var out=json.createObjectNode().put("javaBuildHash",javaBuildHash(json))
                .put("javaVersion",System.getProperty("java.version")).put("osArch",System.getProperty("os.arch"));
        var python=worker.get("/runtime");
        if(!python.has("sourceHashes") || !python.has("packages") || !python.has("executionDevice") || !python.path("sourceFilesUnchanged").asBoolean())
            throw new IllegalStateException("Worker runtime provenance is unavailable; upgrade worker before research runs");
        out.set("worker",python);out.set("workerTransport",json.readTree(json.writeValueAsString(worker.retryPolicy())));return out;
    }
    static void verify(JsonNode provenance,PythonMLClient worker,ObjectMapper json) throws Exception {
        if(!provenance.path("runtimeIdentity").equals(runtime(worker,json)))
            throw new IllegalStateException("Java/Python runtime changed; refusing run/resume with different provenance");
    }
    static ObjectNode capture(Path root,PythonMLClient worker,ObjectMapper json) throws Exception {
        var out=json.createObjectNode();out.set("runtimeIdentity",runtime(worker,json));
        out.put("gitCommit",git(root,"rev-parse","HEAD").trim());
        String status=git(root,"status","--porcelain");out.put("gitDirty",!status.isBlank());out.put("gitStatus",status);
        out.put("dirtyDiffHash",hash(TextNode.valueOf(git(root,"diff","--binary","HEAD"))));
        return out;
    }
    private static String git(Path root,String... args) throws Exception {
        var command=new ArrayList<>(List.of("git"));command.addAll(List.of(args));
        var process=new ProcessBuilder(command).directory(root.toFile()).redirectError(ProcessBuilder.Redirect.DISCARD).start();
        String value=new String(process.getInputStream().readAllBytes(),StandardCharsets.UTF_8);
        if(!process.waitFor(10,TimeUnit.SECONDS)) {process.destroyForcibly();throw new IllegalStateException("Git metadata timed out");}
        if(process.exitValue()!=0) throw new IllegalStateException("Git provenance unavailable");return value;
    }
    static void save(Path path,JsonNode value,ObjectMapper json,boolean immutable) throws Exception {
        Files.createDirectories(path.getParent());
        if(immutable && Files.exists(path)) {
            try(var in=Files.newInputStream(path)) {
                if(!hash(json.readTree(in)).equals(hash(value))) throw new IllegalStateException("Immutable research metadata differs: "+path);
            }
            return;
        }
        saveJson(path,value,json);
    }
    /** Stream JSON into a temporary file so a failed export never leaves a partial target. */
    static void saveJson(Path path,Object value,ObjectMapper json) throws Exception {
        Files.createDirectories(path.getParent());Path temporary=Files.createTempFile(path.getParent(),"report-",".tmp");
        try {
            try(var out=Files.newOutputStream(temporary)) {json.writerWithDefaultPrettyPrinter().writeValue(out,value);}
            Files.writeString(temporary,"\n",StandardCharsets.UTF_8,StandardOpenOption.APPEND);
            try {Files.move(temporary,path,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}
            catch(AtomicMoveNotSupportedException e) {Files.move(temporary,path,StandardCopyOption.REPLACE_EXISTING);}
        } finally {Files.deleteIfExists(temporary);}
    }
    static void saveText(Path path,String text) throws Exception {
        Files.createDirectories(path.getParent());Path temporary=Files.createTempFile(path.getParent(),"report-",".tmp");
        try {
            Files.writeString(temporary,text,StandardCharsets.UTF_8);
            try {Files.move(temporary,path,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}
            catch(AtomicMoveNotSupportedException e) {Files.move(temporary,path,StandardCopyOption.REPLACE_EXISTING);}
        } finally {Files.deleteIfExists(temporary);}
    }
}
