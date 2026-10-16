package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import jakarta.validation.Valid;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import java.util.*;

/** API nhận thí nghiệm, đọc tiến độ và xuất metrics từ trạng thái đã lưu. */
@RestController
public class ExperimentController {
    private final RoundCoordinator coordinator;
    private final ExperimentRepository repository;
    private final PythonMLClient worker;
    private final ObjectMapper json;
    public ExperimentController(RoundCoordinator c,ExperimentRepository r,PythonMLClient w,ObjectMapper j) {
        coordinator=c;repository=r;worker=w;json=j;
    }
    @GetMapping("/health") public Object health() {return Map.of("status","ok","worker",worker.get("/health"));}
    @PostMapping("/experiments") @ResponseStatus(HttpStatus.ACCEPTED)
    public Object start(@Valid @RequestBody ExperimentConfig config) {
        // Trả 202 sau khi nhận tác vụ; quá trình huấn luyện tiếp tục trên executor riêng.
        coordinator.start(config);return Map.of("experimentId",config.experimentId(),"status","RUNNING");
    }
    @GetMapping("/experiments") public Object list() {return repository.list();}
    @GetMapping("/experiments/{id}") public Object get(@PathVariable String id) throws Exception {
        var row=repository.find(id);
        var response=new LinkedHashMap<String,Object>(row);
        for(var key:List.of("config","snapshot")) if(row.get(key)!=null) response.put(key,json.readTree((String)row.get(key)));
        return response;
    }
    @GetMapping("/experiments/{id}/rounds") public Object rounds(@PathVariable String id) {return repository.rounds(id);}
    @PostMapping("/experiments/{id}/resume") @ResponseStatus(HttpStatus.ACCEPTED)
    public Object resume(@PathVariable String id) {coordinator.resume(id);return Map.of("status","RUNNING");}
    @GetMapping(value="/experiments/{id}/metrics.csv",produces="text/csv") public String csv(@PathVariable String id) {
        // CSV là bản rút gọn; endpoint rounds giữ đầy đủ metrics từng client và sự kiện mô phỏng.
        var out=new StringBuilder("round,model_version,outcome,accuracy,loss,macro_f1,accepted,selected,virtual_seconds,cumulative_virtual_seconds,wall_seconds,coverage,gini\n");
        for(var r:repository.rounds(id)) out.append(String.join(",",r.path("roundId").asText(),r.path("modelVersion").asText(),r.path("outcome").asText(),
                r.path("evaluation").path("accuracy").asText(),r.path("evaluation").path("loss").asText(),r.path("evaluation").path("macroF1").asText(),
                ""+r.path("acceptedIds").size(),""+r.path("selectedIds").size(),r.path("virtualRoundSeconds").asText(),r.path("cumulativeVirtualSeconds").asText(),
                r.path("wallClockSeconds").asText(),r.path("fairness").path("coverage").asText(),r.path("fairness").path("participationGini").asText())).append('\n');
        return out.toString();
    }
    @ExceptionHandler(NoSuchElementException.class) @ResponseStatus(HttpStatus.NOT_FOUND)
    public Object missing(Exception e) {return Map.of("error",e.getMessage());}
    @ExceptionHandler({IllegalStateException.class,DuplicateKeyException.class}) @ResponseStatus(HttpStatus.CONFLICT)
    public Object conflict(Exception e) {return Map.of("error",e instanceof DuplicateKeyException?"Experiment ID already exists":e.getMessage());}
    @ExceptionHandler(IllegalArgumentException.class) @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Object invalid(Exception e) {return Map.of("error",e.getMessage());}
}
