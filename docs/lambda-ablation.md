# Fixed Lambda Ablation — nhóm L0–L5

Mục tiêu là kiểm tra **adaptive feedback có tạo trade-off tốt hơn fixed lambda đủ lớn hay không**. Thí nghiệm không được thiết kế để mặc định chứng minh fixed lambda không thể tăng coverage. Cả kết quả ủng hộ và bác bỏ lợi thế adaptive đều có giá trị.

## Thiết kế kiểm soát

| Experiment / hàm | Selection | Lambda |
| --- | --- | --- |
| L0 / `runL0(seed)` | `fuzzy_topsis` | 0, pure Fuzzy TOPSIS |
| L1 / `runL1(seed)` | `fuzzy_topsis_fair` | fixed .3 |
| L2 / `runL2(seed)` | `fuzzy_topsis_fair` | fixed .5 |
| L3 / `runL3(seed)` | `fuzzy_topsis_fair` | fixed .7 |
| L4 / `runL4(seed)` | `fuzzy_topsis_fair` | fixed .9 |
| L5 / `runL5(seed)` | `adaptive_fuzzy_topsis_fair` | controller hiện tại, khởi đầu .3 |

`ControlledExperiments.compareFixedLambdaAblation()` chạy một lần mỗi dòng/seed, theo thứ tự seed rồi L0→L5. Tất cả giữ nguyên Fuzzy TOPSIS engine, weights .40/.35/.25, uncertainty, feasibility predicate, deterministic tie-breaking, FedAvg aggregation, MLP 54–256–128–7, local epoch1, batch32, LR=.01, K=5 và các tham số controller. L1–L5 dùng cùng recurrence `Q(next)=max(0,Q+min(K,F)/F-selected)` và max-normalization; chỉ L5 cập nhật lambda. L0 là pure baseline không có credit state tác động tới lựa chọn; không đưa fairness/staleness criteria vào matrix. Không dùng quota trong ablation này.

Config validator yêu cầu fixed lambdas tăng nghiêm ngặt, hữu hạn, bắt đầu bằng0 và nằm trong bounds hợp lệ; weights/mode/training được validate trước khi train run đầu. Kiểm tra pair chỉ cho phép khác `experimentId`, selection method và `fuzzySelection.fairness.lambda`; các thay đổi khác bị từ chối. Actual initialized tensor hash, manifest đầy đủ, trace hash và từng event của cả population phải khớp theo seed.

`configurations/lambda-ablation.json` giữ protocol F trước đó: **100 clients, 70 rounds, 5 seeds `[42,43,44,45,46]`, Non-IID alpha=.5, partition seed42**. Scenario heterogeneous: availability=.9, dropout=.05, deadline10s, requiredRAM600MB, jitter=.1. Tổng **30 experiments / 2,100 rounds**. Không tái sử dụng kết quả F3/F4/F5 từ batch cũ để tránh trộn batch/điều kiện timing. Có thể xem L0/L1/L5 là bản chạy đối chứng mới của F3/F4/F5.

## Chạy

Chuẩn bị manifests theo README và bật một Python worker. Trong terminal Java, từ repo root:

```powershell
$env:MINIFLS_WORKSPACE = (Get-Location).Path
$env:MINIFLS_METHOD = 'lambda_ablation'
$env:MINIFLS_LAMBDA_MATRIX_CONFIG = 'configurations/lambda-ablation.json'
Remove-Item Env:MINIFLS_MATRIX_ROUNDS -ErrorAction SilentlyContinue
Set-Location ferderatedsystem
.\gradlew.bat bootRun --no-daemon
```

Nhánh này chỉ gọi nhóm L, không cần đổi các lời gọi A/B/C/F người dùng đang bật. `MINIFLS_MATRIX_ROUNDS=2` hoặc `3` là smoke override cho tất cả dòng; nó không giảm số seeds. Các single-run override như `MINIFLS_SELECTION`, `MINIFLS_ROUNDS`, `MINIFLS_SEED` không áp dụng cho batch. File config mới là batch schema, không phải body POST `/experiments`.

Sau khi build JAR, chạy smoke tự động với synthetic, 2 seeds và 3 rounds:

```powershell
.\.venv\Scripts\python.exe scripts/verify_fuzzy.py --lambda-ablation
```

Script dùng ports/database riêng, kiểm tra12 experiments, initial weights/traces, fixed lambdas không đổi, pure TOPSIS zero replacements, credit/controller replay, scores và slots-changed; sau đó chạy riêng một live restart/resume check. Đây là kiểm chứng implementation, không phải số liệu nghiên cứu.

Kết quả kiểm tra đã chạy: [validation ngày 25/10/2026](validation/lambda-ablation-2026-10-25.md).

## Kết quả

File TXT chỉ xuất khi **toàn bộ 30 experiments hoàn tất**, hoặc khi bắt được lỗi:

```text
artifacts/comparisons/<batch-id>/L-fixed-lambda-ablation.txt
artifacts/comparisons/<batch-id>/runs/matrix-<batch-id>-Lx-s<seed>/
  experiment.json
  rounds.json
  result.json
```

Trong lúc chạy, theo dõi `/experiments`, `/experiments/{id}/rounds` và log `matrix.run_started` / `round.committed`. Chưa có TXT khi đang train run cuối là bình thường. `matrix.report_saved comparison=L-lambda` ghi đường dẫn report. Trạng thái cuối là `COMPLETED` hoặc `INCOMPLETE` cùng lỗi; không đưa summary/paired conclusion cho batch thiếu run. Resume từng experiment vẫn dùng SQLite/API hiện tại; orchestration không tự ghép lại report của batch đã bị ngắt.

Report tổng hợp cả6 methods và9 contrasts: L0–L5, L1–L5, L2–L5, L3–L5, L4–L5 và L0–L1/L2/L3/L4. Mỗi outcome có mean ± sample SD qua seeds và paired differences right-minus-left cho từng seed. Cùng với final accuracy/Macro-F1 có per-class recall, first time-to-target và sustained-through-final-round status. Không đạt target là `NOT_REACHED`, không gán0.

### Outcomes và định nghĩa

* **Learning:** `accuracy`, `macroF1` lấy đúng round cuối, không lấy best checkpoint. Across-seed sample SD trong summary thể hiện biến thiên giữa runs.
* **Stability trong run:** `lambdaAblation.stabilityWindow=10` định trước; dùng last `min(10, số round)` observations. `accuracyTailMean` là diagnostic, `accuracyTailSd` / `macroF1TailSd` dùng sample SD (n−1); ít hơn2 observations trả N/A. Đây là stability của reported evaluation trajectory, không phải signal cho controller hay criterion chọn checkpoint. Không thay final accuracy bằng tail mean khi báo kết quả chính.
* **Drops:** `maxAccuracyDropPp` là cú giảm dương lớn nhất giữa hai round liên tiếp, bỏ initial evaluation; `finalAccuracyChangePp` là accuracy cuối trừ accuracy round trước, đơn vị điểm phần trăm. Một-round run không có hai đại lượng này.
* **Fairness:** population completion coverage, RAM-feasible coverage, feasible selection/completion coverage, opportunity-adjusted selection Gini, RAM-feasible completion Gini, max/mean valid-opportunity staleness. Mẫu số toàn population khác mẫu số60 RAM-feasible clients; selection coverage100% không tự có nghĩa completion coverage100%.
* **System:** accepted/selected ratio, wall time, virtual time có/không có selector và fairness-bookkeeping overhead. Wan/communication cost vẫn chưa mô hình hóa.
* **Selection impact:** per-round `topsisTopKClientIds` là Top-K theo raw CC **trên chính pre-round history của run đó**; ties theo clientId. `slotsChangedVsTopsis = |S_selected \ S_rawCC|`, mỗi replacement tính một lần, không lấy symmetric difference. `slotsChangedVsTopsisRatio` trong report = tổng replacements / tổng selected slots; dùng K thực tế khi pool nhỏ. Empty pool: count0, ratio per-round null; cả run không chọn ai thì report ratio N/A. L0 phải luôn có zero replacements.

Các trường selection impact được lưu trong JSON metrics SQLite/API của mọi fuzzy run mới, gồm cả nhóm F. Không cần schema migration; kết quả cũ không có các trường này vẫn đọc được, nhưng không đưa vào L report như thể đã đo. Stability tính từ committed evaluation trajectory khi xuất report; không thay đổi selection hay aggregation.

## Cách diễn giải và thí nghiệm nhiều partitions

Đối chiếu accuracy/Macro-F1/coverage theo chiều tăng; Gini/staleness/instability/time theo chiều giảm. Nếu fixed .7 hay .9 có coverage/Gini tương tự L5 và learning outcomes không kém một cách có bằng chứng, batch này chưa xác lập đóng góp riêng của adaptive feedback. Gần nhau về point estimates không phải một kiểm định equivalence/noninferiority; nếu cần kết luận này phải định nghĩa margin và phân tích thống kê trước khi chạy confirmatory study. Không chọn một fixed lambda bằng test scores rồi gọi đó là kết quả xác nhận độc lập.

Default config chỉ dùng **một partition seed42**. Để kiểm tra nhiều partitions, chuẩn bị thêm cặp IID/Non-IID cùng data seed (ví dụ43,44), tạo bản sao protocol JSON cho mỗi partition, đổi hai manifest paths, giữ các settings khác và chạy một batch riêng cho từng bản qua `MINIFLS_LAMBDA_MATRIX_CONFIG`. Báo cáo riêng per-partition và giữ paired seeds bên trong mỗi partition; không gộp chúng thành các seeds độc lập của một partition. Xác nhận tham số đã chọn trên partitions/seeds chưa dùng khi thăm dò.

Physical training durations là số đo và run order cố định có thể chịu biến động workload/JVM warmup; shared traces không làm timing histories hay candidate sets tự giống hệt. Report ghi số round khác candidate pool. Fixed lambda tăng không có bảo đảm global coverage tăng đơn điệu do lịch sử và model thay đổi theo lựa chọn. Fuzzy uncertainty, local-loss utility và cold-start timing prior vẫn là heuristics; xem [giả định engine/controller](fuzzy-mcdm-client-selection.md).
