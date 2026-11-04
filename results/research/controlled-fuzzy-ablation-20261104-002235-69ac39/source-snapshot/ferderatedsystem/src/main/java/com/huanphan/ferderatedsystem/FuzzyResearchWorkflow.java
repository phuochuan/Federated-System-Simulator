package com.huanphan.ferderatedsystem;

import org.springframework.stereotype.Component;
import org.springframework.core.env.Environment;
import java.nio.file.*;

/** The batch controller uses the existing HTTP admission/resume API and disk-backed evidence. */
@Component
public class FuzzyResearchWorkflow {
    private final Environment env;
    public FuzzyResearchWorkflow(Environment env) {this.env=env;}
    public int run() throws Exception {
        Path root=Path.of(env.getProperty("minifls.launch.workspace","")).toAbsolutePath();
        String python=root.resolve(".venv/Scripts/python.exe").toString();
        String script="controlled-fuzzy-ablation".equals(env.getProperty("minifls.launch.method"))
            ?"controlled_fuzzy_ablation.py":"fuzzy_uncertainty_workflow.py";
        var process=new ProcessBuilder(python,"-u",root.resolve("scripts/"+script).toString())
                .directory(root.toFile()).inheritIO().start();
        return process.waitFor();
    }
}
