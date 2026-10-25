package com.huanphan.ferderatedsystem;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class FerderatedsystemApplication {

	public static void main(String[] args) {
		SpringApplication.run(FerderatedsystemApplication.class, args);
	}

	@Bean
	ApplicationRunner paperExperiment(PaperExperiments experiments) {
		return args -> {
			// Chọn bằng MINIFLS_METHOD=fedavg hoặc fedlbw.
			experiments.runConfigured();
			// Để test trực tiếp trong IDE, thay dòng trên bằng MỘT hàm:
//			 experiments.runFedAvg();
			 experiments.runFedLBW();
			// experiments.runFedProx(); // khung mở rộng, chưa có thuật toán
		};
	}

}
