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
			// MINIFLS_METHOD=matrix: ba câu hỏi, chạy tuần tự và xuất ba file TXT.
			if ("matrix".equals(env.getProperty("minifls.launch.method", "none"))) {
				matrix.compareModelSizes();       // A1 vs A2
				matrix.compareAggregations();     // B1 vs B2
				matrix.compareClientSelection();  // C1/C2/C3/C4: 2x2 factorial
				return;
			}
			// Chọn bằng MINIFLS_METHOD=fedavg hoặc fedlbw.
			experiments.runConfigured();
			// Để test trực tiếp trong IDE, thay dòng trên bằng MỘT hàm:
//			 experiments.runFedAvg();
//			 experiments.runFedLBW();
			// experiments.runFedProx(); // khung mở rộng, chưa có thuật toán
		};
	}

}
