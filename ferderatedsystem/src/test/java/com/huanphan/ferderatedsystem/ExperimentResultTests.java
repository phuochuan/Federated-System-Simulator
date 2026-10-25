package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import static org.mockito.Mockito.mock;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class ExperimentResultTests {
    private SingleConnectionDataSource source;
    private JdbcTemplate db;
    private MockMvc mvc;

    @BeforeEach void setup() {
        source=new SingleConnectionDataSource("jdbc:sqlite::memory:",true);
        db=new JdbcTemplate(source);
        var json=new ObjectMapper();
        var repository=new ExperimentRepository(db,json,new DataSourceTransactionManager(source));
        repository.initialize();
        mvc=MockMvcBuilders.standaloneSetup(new ExperimentController(mock(RoundCoordinator.class),
                repository,mock(PythonMLClient.class),json)).build();
    }

    @AfterEach void close() {source.destroy();}

    private void experiment(String id,String status,int finalRound) {
        db.update("INSERT INTO experiments(id,status,config) VALUES (?,?,?)",id,status,"{\"rounds\":"+finalRound+"}");
    }

    private void round(String id,int round) {
        db.update("INSERT INTO rounds VALUES (?,?,?,?,?)",id,round,round,"COMMITTED",
                "{\"roundId\":"+round+",\"modelVersion\":"+round+",\"evaluation\":{\"accuracy\":0.75,\"macroF1\":0.6}}");
    }

    @Test void returnsOnlyRound20WithItsEvaluation() throws Exception {
        experiment("finished","COMPLETED",20);
        round("finished",1);round("finished",19);round("finished",20);
        mvc.perform(get("/experiments/finished/result")).andExpect(status().isOk())
                .andExpect(jsonPath("$").isMap()).andExpect(jsonPath("$.roundId").value(20))
                .andExpect(jsonPath("$.evaluation.accuracy").value(.75))
                .andExpect(jsonPath("$.evaluation.macroF1").value(.6));
    }

    @Test void followsConfiguredFinalRoundForOtherRuns() throws Exception {
        experiment("short","COMPLETED",2);round("short",2);
        mvc.perform(get("/experiments/short/result")).andExpect(status().isOk())
                .andExpect(jsonPath("$.roundId").value(2));
    }

    @Test void unfinishedRunsDoNotExposePartialRoundsAsFinalResults() throws Exception {
        for(String state:new String[]{"RUNNING","FAILED","INTERRUPTED"}) {
            experiment(state,state,20);round(state,19);
            mvc.perform(get("/experiments/"+state+"/result")).andExpect(status().isConflict())
                    .andExpect(jsonPath("$.error").value("Final result is not ready; experiment status: "+state));
        }
    }

    @Test void reportsUnknownExperimentAndMissingFinalRound() throws Exception {
        mvc.perform(get("/experiments/unknown/result")).andExpect(status().isNotFound());
        experiment("incomplete","COMPLETED",20);round("incomplete",19);
        mvc.perform(get("/experiments/incomplete/result")).andExpect(status().isConflict());
    }
}
