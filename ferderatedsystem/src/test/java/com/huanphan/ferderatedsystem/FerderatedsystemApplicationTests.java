package com.huanphan.ferderatedsystem;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(properties={"spring.datasource.url=jdbc:sqlite::memory:","minifls.launch.method=none"})
class FerderatedsystemApplicationTests {

	@Test
	void contextLoads() {
	}

}
