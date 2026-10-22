package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Validation;
import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;
import org.mockito.ArgumentCaptor;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class PaperExperimentsTests {
    @Test void disabledStartupDoesNotCallWorkerOrCoordinator() throws Exception {
        try(var factory=Validation.buildDefaultValidatorFactory()) {
            var coordinator=mock(RoundCoordinator.class);
            var worker=mock(PythonMLClient.class);
            new PaperExperiments(coordinator,worker,new ObjectMapper(),new MockEnvironment(),factory.getValidator()).runConfigured();
            verifyNoInteractions(coordinator,worker);
        }
    }

    @Test void launchSelectsMethodAndAppliesEnvironmentOverrides() throws Exception {
        try(var factory=Validation.buildDefaultValidatorFactory()) {
            var coordinator=mock(RoundCoordinator.class);
            var worker=mock(PythonMLClient.class);
            var json=new ObjectMapper();
            when(worker.get("/methods")).thenReturn(json.readTree("{\"methods\":[\"fedavg\",\"fedlbw\"]}"));
            var env=new MockEnvironment().withProperty("minifls.launch.method","fedlbw")
                    .withProperty("minifls.launch.config","configurations/smoke.json")
                    .withProperty("minifls.launch.experiment-id","manual-test")
                    .withProperty("minifls.launch.rounds","2").withProperty("minifls.launch.seed","7")
                    .withProperty("minifls.launch.selection","resource_aware");
            var launcher=new PaperExperiments(coordinator,worker,json,env,factory.getValidator());
            launcher.runConfigured();
            var captured=ArgumentCaptor.forClass(ExperimentConfig.class);
            verify(coordinator).start(captured.capture());
            var config=captured.getValue();
            assertEquals("fedlbw",config.aggregation());
            assertEquals("manual-test",config.experimentId());
            assertEquals("resource_aware",config.selection());
            assertEquals(2,config.rounds());
            assertEquals(7,config.seed());
            assertEquals("artifacts/partitions/synthetic-iid-42",config.manifestPath());
            env.setProperty("minifls.launch.rounds","0");
            assertThrows(IllegalArgumentException.class,() -> launcher.loadConfig("fedlbw"));
        }
    }

    @Test void plannedAndUnknownMethodsNeverStartFallbackExperiments() throws Exception {
        try(var factory=Validation.buildDefaultValidatorFactory()) {
            var coordinator=mock(RoundCoordinator.class);
            var worker=mock(PythonMLClient.class);
            var json=new ObjectMapper();
            when(worker.get("/methods")).thenReturn(json.readTree("{\"methods\":[\"fedavg\",\"fedlbw\"]}"));
            var env=new MockEnvironment().withProperty("minifls.launch.method","oort");
            var launcher=new PaperExperiments(coordinator,worker,json,env,factory.getValidator());
            assertThrows(IllegalArgumentException.class,launcher::runConfigured);
            env.setProperty("minifls.launch.method","typo");
            assertThrows(IllegalArgumentException.class,launcher::runConfigured);
            verifyNoInteractions(coordinator);
        }
    }
}
