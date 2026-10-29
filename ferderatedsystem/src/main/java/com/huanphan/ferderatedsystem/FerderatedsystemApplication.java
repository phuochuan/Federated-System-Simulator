package com.huanphan.ferderatedsystem;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.core.env.Environment;

@SpringBootApplication
public class FerderatedsystemApplication {

	public static void main(String[] args) {
		SpringApplication.run(FerderatedsystemApplication.class, args);
	}

	@Bean
	ApplicationRunner paperExperiment(PaperExperiments experiments,ControlledExperiments matrix,Environment env) {
		return args -> {
			if(!env.getProperty("minifls.launch.enabled",Boolean.class,true)) return;
			// Explicit CLI modes bypass the user's manual IDE sequence below.
			switch(env.getProperty("minifls.launch.method","none")) {
				case "pareto_workflow" -> {matrix.runParetoWorkflow();return;}
				case "heldout_pareto" -> {matrix.runHeldoutParetoEvaluation();return;}
				case "pareto_preflight" -> {matrix.preflightHeldoutParetoEvaluation();return;}
				case "reproducibility_audit" -> {matrix.runReproducibilityAudit();return;}
				case "fairness_matched_validation" -> {matrix.runFairnessMatchedValidation();return;}
				case "fairness_matched_evaluation" -> {matrix.runFairnessMatchedEvaluation();return;}
				case "fuzzy_matrix" -> {matrix.compareFuzzyClientSelection();return;}
				case "lambda_ablation" -> {matrix.compareFixedLambdaAblation();return;}
			}
			matrix.runReproducibilityAudit();
			matrix.runFairnessMatchedValidation();
			matrix.runFairnessMatchedEvaluation();
//
//			switch(env.getProperty("minifls.launch.method","none")) {
//				case "reproducibility_audit" -> {matrix.runReproducibilityAudit();return;}
//				case "fairness_matched_validation" -> {matrix.runFairnessMatchedValidation();return;}
//				case "fairness_matched_evaluation" -> {matrix.runFairnessMatchedEvaluation();return;}
//			}
//			if ("lambda_ablation".equals(env.getProperty("minifls.launch.method", "none"))) {
//				matrix.compareFixedLambdaAblation(); // L0-L5; lambda policy is the only experimental factor
//				return;
//			}
//			if ("fuzzy_matrix".equals(env.getProperty("minifls.launch.method", "none"))) {
//				matrix.compareFuzzyClientSelection(); // F1-F5, six paired comparisons
//				return;
//			}
//			// MINIFLS_METHOD=matrix: ba câu hỏi, chạy tuần tự và xuất ba file TXT.
//			if ("matrix".equals(env.getProperty("minifls.launch.method", "none"))) {
////				matrix.compareModelSizes();       // A1 vs A2
////				matrix.compareAggregations();     // B1 vs B2
//				matrix.compareClientSelection();  // C1/C2/C3/C4: 2x2 factorial
////				matrix.compareClientSelectionC5C6();  // C5/C6
//				return;
//			}
//			// Chọn bằng MINIFLS_METHOD=fedavg hoặc fedlbw.
//			experiments.runConfigured();
			// Để test trực tiếp trong IDE, thay dòng trên bằng MỘT hàm:
//			 experiments.runFedAvg();
//			 experiments.runFedLBW();
			// experiments.runFedProx(); // khung mở rộng, chưa có thuật toán
		};
	}

}
