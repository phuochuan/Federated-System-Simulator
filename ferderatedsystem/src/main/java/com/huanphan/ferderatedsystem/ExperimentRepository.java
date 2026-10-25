package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import jakarta.annotation.PostConstruct;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.transaction.support.TransactionTemplate;
import java.util.*;

/** Lưu cấu hình, kết quả round và snapshot phục hồi bằng SQLite. */
@Repository
public class ExperimentRepository {
    private static final Logger log=LoggerFactory.getLogger(ExperimentRepository.class);
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
        // Run đang chạy trước khi Java dừng phải được đánh dấu gián đoạn để có thể resume.
        int interrupted=db.update("UPDATE experiments SET status='INTERRUPTED' WHERE status='RUNNING'");
        log.info("repository.ready restoredInterruptedExperiments={}",interrupted);
    }
    public void create(ExperimentConfig config) {
        db.update("INSERT INTO experiments(id,status,config) VALUES (?,'RUNNING',?)",config.experimentId(),encode(config));
    }
    public String encode(Object value) {
        try{return json.writeValueAsString(value);}catch(Exception e){throw new IllegalStateException(e);}
    }
    public void commit(String id,int round,int version,String outcome,Object metrics,Object snapshot) {
        // Ghi metrics và snapshot trong cùng transaction để không phục hồi từ round ghi dở.
        tx.executeWithoutResult(s -> {
            db.update("INSERT INTO rounds VALUES (?,?,?,?,?)",id,round,version,outcome,encode(metrics));
            db.update("UPDATE experiments SET snapshot=? WHERE id=?",encode(snapshot),id);
        });
        log.debug("repository.round_saved experiment={} round={} modelVersion={} outcome={}",id,round,version,outcome);
    }
    public void snapshot(String id,Object snapshot) {db.update("UPDATE experiments SET snapshot=? WHERE id=?",encode(snapshot),id);}
    public void status(String id,String status,String error) {
        db.update("UPDATE experiments SET status=?,error=? WHERE id=?",status,error,id);
        log.info("repository.status_saved experiment={} status={}",id,status);
    }
    public Map<String,Object> find(String id) {
        var rows=db.queryForList("SELECT * FROM experiments WHERE id=?",id);
        if(rows.isEmpty()) throw new NoSuchElementException("Unknown experiment");
        return rows.get(0);
    }
    public List<Map<String,Object>> list() {return db.queryForList("SELECT id,status,error,created_at FROM experiments ORDER BY created_at DESC");}
    public JsonNode result(String id) {
        var experiment=find(id);
        // Chỉ trả round cuối đã hoàn tất theo config, không trả nhầm round đang chạy dở.
        if(!"COMPLETED".equals(experiment.get("status")))
            throw new IllegalStateException("Final result is not ready; experiment status: "+experiment.get("status"));
        int finalRound;
        try {finalRound=json.readTree((String)experiment.get("config")).path("rounds").asInt();}
        catch(Exception e) {throw new IllegalStateException("Cannot read experiment configuration",e);}
        var rows=db.query("SELECT metrics FROM rounds WHERE experiment_id=? AND round_id=?",(rs,n)-> {
            try{return json.readTree(rs.getString(1));}catch(Exception e){throw new IllegalStateException(e);}
        },id,finalRound);
        if(rows.isEmpty()) throw new IllegalStateException("Final round result is not available");
        log.info("result.loaded experiment={} round={}",id,finalRound);
        return rows.get(0);
    }
    public List<JsonNode> rounds(String id) {
        find(id);
        return db.query("SELECT metrics FROM rounds WHERE experiment_id=? ORDER BY round_id",(rs,n)-> {
            try{return json.readTree(rs.getString(1));}catch(Exception e){throw new IllegalStateException(e);}
        },id);
    }
}
