package com.huanphan.ferderatedsystem;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** IntelliJ entry point. Python supervises a pinned scientific Java JAR, never the manual worker. */
public final class ControlledAblationIdeLauncher {
    private static volatile Process supervisor;
    static Map<String,String> arguments(String[] args) {
        Map<String,String> result=new HashMap<>();
        for(String arg:args) {
            if(!arg.startsWith("--")||!arg.contains("=")) throw new IllegalArgumentException("Use --name=value");
            int split=arg.indexOf('=');String key=arg.substring(2,split),value=arg.substring(split+1);
            if(!Set.of("workspace","stage","mode","run-budget","round-budget","server-port","worker-url","output-root","config").contains(key)
                ||result.put(key,value)!=null) throw new IllegalArgumentException("Unknown/duplicate launcher option: "+key);
        }
        String stage=result.getOrDefault("stage","full"),mode=result.getOrDefault("mode","run");
        if(!Set.of("full","pilot").contains(stage)||!Set.of("run","preflight","report-only").contains(mode))
            throw new IllegalArgumentException("Use stage full/pilot and mode run/preflight/report-only");
        for(String key:List.of("run-budget","round-budget"))
            if(Long.parseLong(result.getOrDefault(key,"0"))<0) throw new IllegalArgumentException("Budget cannot be negative");
        int port=Integer.parseInt(result.getOrDefault("server-port","8080"));
        if(port<1||port>65535) throw new IllegalArgumentException("Invalid coordinator port");
        return result;
    }
    private static synchronized void cleanup() {
        if(supervisor==null) return;
        var descendants=supervisor.descendants().toList();
        for(int i=descendants.size()-1;i>=0;i--) descendants.get(i).destroy();
        supervisor.destroy();
        try {if(!supervisor.waitFor(5,TimeUnit.SECONDS)) supervisor.destroyForcibly();}
        catch(InterruptedException error) {Thread.currentThread().interrupt();supervisor.destroyForcibly();}
        descendants.stream().filter(ProcessHandle::isAlive).forEach(ProcessHandle::destroyForcibly);
    }
    public static void main(String[] args) throws Exception {
        var options=arguments(args);
        Path root=FrozenE3IdeLauncher.workspace(Path.of(options.getOrDefault("workspace",System.getProperty("user.dir")))).toRealPath();
        Path python=root.resolve(".venv/Scripts/python.exe");
        if(!Files.isRegularFile(python)) throw new IllegalStateException("Missing repository .venv/Scripts/python.exe");
        String stage=options.getOrDefault("stage","full"),mode=options.getOrDefault("mode","run");
        var builder=new ProcessBuilder(python.toString(),"-u",root.resolve("scripts/controlled_ablation_ide.py").toString(),"java");
        var env=builder.environment();
        env.put("MINIFLS_STUDY","controlled-fuzzy-ablation");
        env.put("MINIFLS_FUZZY_CONFIG",options.getOrDefault("config","configurations/controlled-fuzzy-ablation-"+stage+".json"));
        env.put("MINIFLS_FUZZY_OUTPUT",options.getOrDefault("output-root","artifacts/research/controlled-fuzzy-ablation/"+stage));
        env.put("MINIFLS_FUZZY_MODE",mode.equals("run")?(stage.equals("pilot")?"pilot":"full"):mode);
        env.put("MINIFLS_FUZZY_RUN_BUDGET",options.getOrDefault("run-budget","0"));
        env.put("MINIFLS_FUZZY_ROUND_BUDGET",options.getOrDefault("round-budget","0"));
        env.put("MINIFLS_SERVER_PORT",options.getOrDefault("server-port","8080"));
        env.put("MINIFLS_WORKER_URL",options.getOrDefault("worker-url","http://127.0.0.1:8000"));
        env.put("MINIFLS_IDE_OWNER_PID",Long.toString(ProcessHandle.current().pid()));
        env.put("MINIFLS_IDE_OWNER_STARTED_MS",Long.toString(ProcessHandle.current().info().startInstant().orElseThrow().toEpochMilli()));
        env.put("PYTHONUTF8","1");
        // All coordinator restarts use the exact JDK selected in IntelliJ.
        env.put("JAVA_HOME",System.getProperty("java.home"));
        env.put("MINIFLS_JAVA_EXECUTABLE",Path.of(System.getProperty("java.home"),"bin","java.exe").toString());
        Runtime.getRuntime().addShutdownHook(new Thread(ControlledAblationIdeLauncher::cleanup,"controlled-ablation-cleanup"));
        System.out.println("[IDE] Controlled ablation stage="+stage+"; run budget="+env.get("MINIFLS_FUZZY_RUN_BUDGET")+"; round budget="+env.get("MINIFLS_FUZZY_ROUND_BUDGET"));
        System.out.println("[IDE] Full default: 225 x 70 research rounds, plus two 2-round reproducibility audits. No separate Covertype pilot.");
        System.out.println("[IDE] Start Uvicorn manually. The IDE does not launch or terminate your worker. Disk/provenance guards remain active.");
        supervisor=builder.directory(root.toFile()).inheritIO().start();
        int code;
        try {code=supervisor.waitFor();} finally {cleanup();}
        if(code!=0) throw new IllegalStateException("Study stopped with exit "+code+"; inspect this console and batch status; retain checkpoints");
    }
}
