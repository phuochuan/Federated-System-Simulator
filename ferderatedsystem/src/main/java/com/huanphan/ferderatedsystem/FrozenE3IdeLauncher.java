package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** IntelliJ entry point: retain the frozen scientific runtime, replace launch plumbing only. */
public final class FrozenE3IdeLauncher {
    private static final ObjectMapper JSON=new ObjectMapper();
    private static volatile Process server,controller;

    static Path workspace(Path start) {
        Path candidate=start.toAbsolutePath().normalize();
        while(candidate!=null) {
            if(Files.isRegularFile(candidate.resolve("configurations/fuzzy-uncertainty.json"))) return candidate;
            candidate=candidate.getParent();
        }
        throw new IllegalArgumentException("Open the repository or ferderatedsystem module as the working directory");
    }
    static String hash(Path file) throws Exception {
        try(var stream=Files.newInputStream(file)) {
            var digest=MessageDigest.getInstance("SHA-256");byte[] buffer=new byte[65536];int n;
            while((n=stream.read(buffer))!=-1) digest.update(buffer,0,n);
            return HexFormat.of().formatHex(digest.digest());
        }
    }
    static Map<String,String> arguments(String[] args) {
        Map<String,String> result=new HashMap<>();
        for(String arg:args) {
            if(!arg.startsWith("--")||!arg.contains("=")) throw new IllegalArgumentException("Use --name=value arguments");
            int split=arg.indexOf('=');String key=arg.substring(2,split);
            if(!Set.of("workspace","batch","server-port","worker-url","run-budget","round-budget","lock-directory","java").contains(key))
                throw new IllegalArgumentException("Unknown launcher argument: "+key);
            if(result.put(key,arg.substring(split+1))!=null) throw new IllegalArgumentException("Duplicate launcher argument: "+key);
        }
        return result;
    }
    static void verifySources(Path root,Path batch) throws Exception {
        var source=JSON.readTree(batch.resolve("source-identity.json").toFile());
        var fields=source.fields();
        while(fields.hasNext()) {
            var item=fields.next();Path path=root.resolve(item.getKey()).normalize();
            if(!path.startsWith(root)||!Files.isRegularFile(path)||!hash(path).equals(item.getValue().asText()))
                throw new IllegalStateException("Frozen source differs: "+item.getKey()+"; do not disable provenance checks");
        }
        var identity=JSON.readTree(batch.resolve("build-identity.json").toFile());
        if(!hash(batch.resolve("coordinator.jar")).equals(identity.path("jarSHA256").asText()))
            throw new IllegalStateException("Frozen coordinator JAR checksum mismatch");
    }
    private static void stop(Process process) {
        if(process==null) return;
        var descendants=process.descendants().toList();
        for(int i=descendants.size()-1;i>=0;i--) descendants.get(i).destroy();
        process.destroy();
        try {if(!process.waitFor(5,TimeUnit.SECONDS)) process.destroyForcibly();}
        catch(InterruptedException error) {Thread.currentThread().interrupt();process.destroyForcibly();}
        descendants.stream().filter(ProcessHandle::isAlive).forEach(ProcessHandle::destroyForcibly);
    }
    private static synchronized void cleanup() {stop(controller);stop(server);}

    public static void main(String[] args) throws Exception {
        var options=arguments(args);
        Path root=workspace(Path.of(options.getOrDefault("workspace",System.getProperty("user.dir")))).toRealPath();
        Path batch;
        if(options.containsKey("batch")) batch=root.resolve(options.get("batch")).normalize().toRealPath();
        else batch=Path.of(JSON.readTree(root.resolve("artifacts/research/fuzzy-uncertainty/active-batch.json").toFile()).path("folder").asText()).toRealPath();
        if(!batch.startsWith(root.resolve("artifacts"))) throw new IllegalArgumentException("Batch must stay inside repository artifacts");
        Path locks=root.resolve(options.getOrDefault("lock-directory","artifacts/research/locks")).normalize();
        if(!locks.startsWith(root.resolve("artifacts"))) throw new IllegalArgumentException("Lock directory must stay in artifacts");
        Files.createDirectories(locks);
        try(var channel=FileChannel.open(locks.resolve("java.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE)) {
            var lock=channel.tryLock(0,1,false);
            if(lock==null) throw new IllegalStateException("Another coordinator/watchdog is active. Stop the old Java terminal before running IntelliJ.");
            try(lock) {
                verifySources(root,batch);
                int port=Integer.parseInt(options.getOrDefault("server-port","8080"));
                if(port<1||port>65535) throw new IllegalArgumentException("Invalid server port");
                boolean occupied=false;
                try(var socket=new Socket()) {socket.connect(new InetSocketAddress("127.0.0.1",port),500);occupied=true;}
                catch(java.io.IOException ignored) { /* no existing listener */ }
                if(occupied) throw new IllegalStateException("Port "+port+" is in use; refusing a second coordinator");
                Path python=root.resolve(".venv/Scripts/python.exe");
                if(!Files.isRegularFile(python)) throw new IllegalStateException("Missing repository .venv/Scripts/python.exe");
                var runtime=JSON.readTree(batch.resolve("runtime-identity.json").toFile());
                JsonNode transport=runtime.path("workerTransport");
                Map<String,String> environment=new HashMap<>(System.getenv());
                environment.put("MINIFLS_WORKSPACE",root.toString());
                environment.put("MINIFLS_DATABASE",batch.resolve("experiments.db").toString());
                environment.put("MINIFLS_SERVER_PORT",Integer.toString(port));
                environment.put("MINIFLS_WORKER_URL",options.getOrDefault("worker-url","http://127.0.0.1:8000"));
                environment.put("MINIFLS_LAUNCH_ENABLED","false");
                environment.put("MINIFLS_METHOD","none");
                environment.put("MINIFLS_FUZZY_BATCH",batch.toString());
                environment.put("MINIFLS_FUZZY_MODE","full");
                environment.put("MINIFLS_FUZZY_RUN_BUDGET",options.getOrDefault("run-budget","0"));
                environment.put("MINIFLS_FUZZY_ROUND_BUDGET",options.getOrDefault("round-budget","0"));
                environment.put("MINIFLS_WORKER_MAX_ATTEMPTS",transport.path("maxAttempts").asText());
                environment.put("MINIFLS_WORKER_RETRY_DELAY_MS",transport.path("retryDelayMs").asText());
                environment.put("MINIFLS_WORKER_RETRY_MAX_DELAY_MS",transport.path("retryMaxDelayMs").asText());
                environment.put("MINIFLS_WORKER_REQUEST_TIMEOUT_SECONDS",Long.toString(transport.path("requestTimeoutMs").asLong()/1000));
                environment.put("MINIFLS_WORKER_RECOVERY_BUDGET_SECONDS",transport.path("recoveryBudgetSeconds").asText());
                environment.put("MINIFLS_WORKER_RETRY_JITTER",transport.path("retryJitter").asText("0"));
                environment.put("MINIFLS_IDE_OWNER_PID",Long.toString(ProcessHandle.current().pid()));
                environment.put("MINIFLS_IDE_OWNER_STARTED_MS",Long.toString(ProcessHandle.current().info().startInstant().orElseThrow().toEpochMilli()));
                try(var bytes=FrozenE3IdeLauncher.class.getResourceAsStream("FrozenE3IdeLauncher.class")) {
                    environment.put("MINIFLS_IDE_LAUNCHER_CLASS_SHA256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Objects.requireNonNull(bytes).readAllBytes())));
                }
                environment.put("PYTHONUTF8","1");
                Runtime.getRuntime().addShutdownHook(new Thread(FrozenE3IdeLauncher::cleanup,"frozen-e3-cleanup"));
                System.out.println("[IDE] Full E3 resume, batch="+batch);
                System.out.println("[IDE] Frozen JAR/source hashes verified. Start Uvicorn manually; progress appears here.");
                String java=options.getOrDefault("java",Path.of(System.getProperty("java.home"),"bin","java.exe").toString());
                var serverBuilder=new ProcessBuilder(java,"-Xms128m","-Xmx512m","-XX:ActiveProcessorCount=2","-jar",batch.resolve("coordinator.jar").toString());
                serverBuilder.environment().clear();serverBuilder.environment().putAll(environment);
                server=serverBuilder.directory(root.toFile()).inheritIO().start();
                environment.put("MINIFLS_IDE_SERVER_PID",Long.toString(server.pid()));
                var controlBuilder=new ProcessBuilder(python.toString(),"-u",root.resolve("scripts/resume_frozen_e3.py").toString());
                controlBuilder.environment().clear();controlBuilder.environment().putAll(environment);
                controller=controlBuilder.directory(root.toFile()).inheritIO().start();
                try {
                    while(controller.isAlive()) {
                        if(!server.isAlive()) throw new IllegalStateException("Frozen Java server exited ("+server.exitValue()+"); restart this IntelliJ configuration to resume safely");
                        Thread.sleep(250);
                    }
                    int code=controller.exitValue();
                    if(code!=0) throw new IllegalStateException("E3 controller stopped with code "+code+"; inspect status.json and this console");
                    System.out.println("[IDE] E3 controller completed or reached its configured budget.");
                } finally {cleanup();}
            }
        }
    }
}
