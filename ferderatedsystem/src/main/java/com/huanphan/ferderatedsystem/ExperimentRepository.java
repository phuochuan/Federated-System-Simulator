package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import jakarta.annotation.PostConstruct;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.support.TransactionTemplate;
import java.util.*;

@Repository
public class ExperimentRepository {
    private final JdbcTemplate db;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    public ExperimentRepository(JdbcTemplate db,ObjectMapper json,org.springframework.transaction.PlatformTransactionManager manager) {
        this.db=db;this.json=json;this.tx=new TransactionTemplate(manager);
    }
    @PostConstruct void initialize() {
        db.execute("PRAGMA journal_mode=WAL");
        db.execute("PRAGMA busy_timeout=5000");
        db.execute("CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, status TEXT NOT NULL, config TEXT NOT NULL, snapshot TEXT, error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)");
        db.execute("CREATE TABLE IF NOT EXISTS rounds (experiment_id TEXT, round_id INTEGER, model_version INTEGER, outcome TEXT, metrics TEXT NOT NULL, PRIMARY KEY(experiment_id,round_id))");
        // A terminated process never reports an in-flight experiment as still running.
        db.update("UPDATE experiments SET status='INTERRUPTED' WHERE status='RUNNING'");
    }
    public void create(ExperimentConfig config) {
        db.update("INSERT INTO experiments(id,status,config) VALUES (?,'RUNNING',?)",config.experimentId(),encode(config));
    }
    public String encode(Object value) {
        try{return json.writeValueAsString(value);}catch(Exception e){throw new IllegalStateException(e);}
    }
    public void commit(String id,int round,int version,String outcome,Object metrics,Object snapshot) {
        tx.executeWithoutResult(s -> {
            db.update("INSERT INTO rounds VALUES (?,?,?,?,?)",id,round,version,outcome,encode(metrics));
            db.update("UPDATE experiments SET snapshot=? WHERE id=?",encode(snapshot),id);
        });
    }
    public void snapshot(String id,Object snapshot) {db.update("UPDATE experiments SET snapshot=? WHERE id=?",encode(snapshot),id);}
    public void status(String id,String status,String error) {db.update("UPDATE experiments SET status=?,error=? WHERE id=?",status,error,id);}
    public Map<String,Object> find(String id) {
        var rows=db.queryForList("SELECT * FROM experiments WHERE id=?",id);
        if(rows.isEmpty()) throw new NoSuchElementException("Unknown experiment");
        return rows.get(0);
    }
    public List<Map<String,Object>> list() {return db.queryForList("SELECT id,status,error,created_at FROM experiments ORDER BY created_at DESC");}
    public List<JsonNode> rounds(String id) {
        find(id);
        return db.query("SELECT metrics FROM rounds WHERE experiment_id=? ORDER BY round_id",(rs,n)-> {
            try{return json.readTree(rs.getString(1));}catch(Exception e){throw new IllegalStateException(e);}
        },id);
    }
}
