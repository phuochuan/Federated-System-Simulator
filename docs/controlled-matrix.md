# Chạy controlled experiment matrix bằng các hàm Java

Controlled Experiment Matrix có các nhóm A/B/C hiện có và nhóm **F — Fuzzy Multi-Criteria Decision Making (FMCDM)** bổ sung cho client selection. Hai chế độ khởi chạy tách biệt:

| Chế độ | File cấu hình | Hàm trong application class |
| --- | --- | --- |
| `MINIFLS_METHOD=matrix` | `configurations/controlled-matrix.json` | Các lời gọi A/B/C được bật thủ công |
| `MINIFLS_METHOD=fuzzy_matrix` | `configurations/fuzzy-matrix.json` | `matrix.compareFuzzyClientSelection()` đã được bật |
| `MINIFLS_METHOD=lambda_ablation` | `configurations/lambda-ablation.json` | `matrix.compareFixedLambdaAblation()` đã được bật |

Nhánh `matrix` chỉ chạy các lời gọi được bật trong application class; hiện `compareClientSelection()` đang bật, các lời gọi A/B và cặp riêng C5/C6 đang comment. Để chạy đầy đủ A/B/C, bật ba dòng sau trong `FerderatedsystemApplication.paperExperiment()`:

```java
matrix.compareModelSizes();       // A1 và A2
matrix.compareAggregations();     // B1 và B2
matrix.compareClientSelection();  // C1–C4 factorial + C5 feasible-random baseline
```

Các hàm nằm trong `ControlledExperiments`. A/B gọi hai hàm tương ứng cho từng seed;
C gọi bốn hàm của thiết kế 2x2 và `runC5(seed)` để thêm cặp Feasible Random ↔ Resource-aware.
Mỗi experiment phải hoàn thành trước khi chạy tiếp. Có thể comment A/B trong application
class để chỉ chạy nhóm C.
Không cần restart Python khi đổi MLP; Java truyền kiến trúc rõ ràng lúc initialize.

| Hàm chạy | Kiến trúc | Aggregation | Selection | Partition |
| --- | --- | --- | --- | --- |
| `runA1(seed)` | 54 → 128 → 64 → 7 | FedAvg | Random | IID |
| `runA2(seed)` | 54 → 256 → 128 → 7 | FedAvg | Random | IID |
| `runB1(seed)` | MLP lớn | FedAvg | Random | Non-IID |
| `runB2(seed)` | MLP lớn | FedLBW | Random | Non-IID |
| `runC1(seed)` | MLP lớn | FedAvg | Random | Non-IID |
| `runC2(seed)` | MLP lớn | FedAvg | Resource-aware | Non-IID |
| `runC3(seed)` | MLP lớn | FedLBW | Random | Non-IID |
| `runC4(seed)` | MLP lớn | FedLBW | Resource-aware | Non-IID |
| `runC5(seed)` | MLP lớn | FedAvg | Feasible Random | Non-IID |
| `runC6(seed)` | MLP lớn | FedAvg | Resource-aware | Non-IID |

`compareClientSelection()` chạy C1–C5 và tái sử dụng C2 để so sánh với C5. Hàm riêng `compareClientSelectionC5C6()` chạy cặp C5/C6, trong đó C6 có cùng policy/cấu hình với C2 nhưng experiment ID riêng. Chỉ bật hàm riêng này nếu muốn chạy cặp Feasible Random ↔ Resource-aware độc lập; nó không thuộc số lượng 9 dòng A/B/C nêu dưới đây.

Tất cả các dòng bật simulator. Nhóm C dùng Non-IID alpha=0.5 và cùng scenario heterogeneous;
A/B dùng scenario CPU-only trong `baseConfig` để tách ảnh hưởng architecture/aggregation.

## Cách chạy

1. Chuẩn bị hai manifest Covertype theo README: `covertype-iid-42` và
   `covertype-dirichlet-42`. Hai manifest phải dùng cùng seed dữ liệu, preprocessing,
   train/proxy/test pools; chỉ partition khác nhau. Không ghi đè các manifest đã có.
2. Khởi động Python worker từ source hiện tại, đúng một uvicorn worker.
3. Trong Run Configuration của Java, đặt:

```text
MINIFLS_METHOD=matrix
MINIFLS_MATRIX_CONFIG=configurations/controlled-matrix.json
MINIFLS_WORKSPACE=D:/research/federated-system
MINIFLS_DATABASE=D:/research/federated-system/artifacts/minifls.db
```

4. Run application. Chỉ gọi nhánh matrix; không gọi thêm `runFedAvg()`/`runFedLBW()`
   bên ngoài nhánh này. Theo dõi `matrix.run_started`, `round.committed`, `matrix.report_saved`.

Chạy toàn bộ là **9 dòng × 5 seeds (42–46) = 45 experiment**; chỉ nhóm C là 25 experiment.
Số round lấy từ `baseConfig.rounds` trong file JSON hoặc `MINIFLS_MATRIX_ROUNDS` nếu có.
Các seed này thay đổi model initialization, local training và selection/simulation RNG.
Data split và hai partition vẫn cố định theo manifest seed 42. Kết luận chỉ áp dụng
cho các partition đó, không tự suy rộng thành kết quả trên nhiều partition độc lập.

Muốn kiểm tra pipeline nhanh trước, đặt `MINIFLS_MATRIX_ROUNDS=2`. Đây chỉ là smoke test.
Muốn thay seeds, số client, training hoặc resource scenario, sửa file matrix JSON;
đổi số client đòi hỏi chuẩn bị lại manifest tương ứng. `MINIFLS_ROUNDS`, `MINIFLS_SEED`,
`MINIFLS_SELECTION`, `MINIFLS_CONFIG`, `MINIFLS_EXPERIMENT_ID` của single-run launcher
không ghi đè matrix. Mỗi lần khởi động matrix sinh batch ID và experiment IDs mới.

Scenario mặc định: CPU heterogeneity, RAM 1024 MB cho mọi client, availability=1,
dropout=0, jitter=0, không deadline, requiredRamMb=600. Vì vậy cả hai model có cùng
cơ hội hoàn thành; thời gian CPU mô phỏng vẫn khác nhau theo tier và workload.
`requiredRamMb` là giả định mô phỏng, chưa phải RAM thiết bị được đo/calibrate.
Có thể sửa scenario trong `baseConfig`, nhưng giữ nó giống nhau trong từng cặp.

Riêng C1–C6 cùng lấy `heterogeneousScenario`: resourceProfile=heterogeneous,
availability=0.9, dropout=0.05, deadline=10 giây, requiredRamMb=600, jitter=0.1.
LOW/MEDIUM/HIGH có CPU 0.5/1/2 và RAM 512/1024/2048 MB. LOW không đủ RAM trong
scenario này; báo cáo luôn hiển thị denominator của coverage có điều kiện.

## Kiểm chứng các điều kiện kiểm soát

Java tạo file trace cố định cho **mọi client ở mọi round**, với các channel độc lập
availability/dropout/jitter, lưu ở `traces/<group>-s<seed>.json`. Selection không tham
gia tạo traces; OOM, thứ tự job và việc một client không được chọn không làm thay đổi
event của các client khác. C1–C4 replay cùng file và hash. Toàn bộ event population
được lưu trong round JSON, kể cả các client không được chọn. Selector chỉ dùng availability
hiện tại, profile và lịch sử; không đọc dropout/jitter tương lai để chọn client.

Traces được index theo **round/client**, không theo absolute virtual time. Actual
training duration vẫn là phép đo; model hoặc selection khác có thể tạo duration và
deadline outcome khác dù exogenous traces giống nhau. Đây không phải trace có sẵn
về kết quả thành công/thất bại để ép các phương pháp có cùng kết quả.

Python tính `modelStateHash` từ schema và giá trị tensor. Snapshot lưu hash của
global model khởi tạo, seed và `pytorch-default-linear-v1`. B1/B2 và các cặp của C
phải có cùng actual initial weights; A1/A2 chỉ yêu cầu cùng initialization method/seed
vì tensor shapes khác nhau. Java kiểm tra manifest đầy đủ, shared trace hash và
trace từng round trước khi tạo kết luận. Resume từ snapshot từ chối trace bị sửa.

## Kết quả

Khi mỗi cặp hoàn tất, Java ghi UTF-8 TXT vào:

```text
artifacts/comparisons/<batch-id>/
  A-model-size.txt
  B-aggregation.txt
  C-client-selection.txt
  C5-C6-feasible-selection.txt       # nếu gọi riêng compareClientSelectionC5C6()
  F-fuzzy-client-selection.txt       # nếu chạy fuzzy_matrix
  traces/<group>-s<seed>.json
  runs/<experiment-id>/
    experiment.json
    rounds.json
    result.json
```

Mỗi TXT có câu hỏi, biến được thay đổi, cấu hình chung, ID từng run, seed, model,
manifest, chỉ số từng seed và bảng **mean ± sample SD (n-1)**. Bảng paired difference
tính **bên phải trừ bên trái** cho cùng seed. Accuracy/Macro-F1 có thêm chênh lệch
theo điểm phần trăm. Báo cáo còn có loss, worst-class recall, recall từng lớp,
confusion matrix, coverage, participation Gini, accepted/selected counts,
virtual time, round wall time, accepted/selected ratio và các overhead riêng:
`proxyEvaluationMs` (worker compute), `proxyEvaluationWallMs` (gồm localhost RPC),
`weightCalculationMs`, `aggregationMs`, `serverAggregationOverheadMs`.
Virtual time cộng proxy wall + weight calculation + aggregation, không cộng lặp proxy compute.

Các ngưỡng trong `accuracyTargets` mặc định là 65%, 68%, 69%, 70%. Báo cáo ghi lần
đầu đạt ngưỡng theo round, virtual time và round wall time; chưa đạt là `NOT_REACHED`.
`sustainedFromRound` báo round bắt đầu duy trì ngưỡng đến hết run; đạt một lần rồi mất ngưỡng không được gọi là duy trì. Thời gian có/không có selector overhead được phân biệt trong report.
Mean time chỉ tính trong các run đã đạt và luôn kèm `reached/n`, không điền 0 cho
run bị censored. 0 chỉ hợp lệ nếu model ban đầu đã đạt ngưỡng.

`coverage` là population coverage. `ramFeasibleCoverage` dùng tập đủ RAM cố định
chung cho mọi phương pháp. `estimatedFeasibleCoverage` dùng tập từng có ít nhất một
cơ hội available + đủ RAM + đáp ứng ước lượng deadline trước round; denominator
này có thể phụ thuộc lịch sử của policy và được báo riêng. Tập rỗng là `N/A`.

Communication cost ghi `NOT_MODELED`: không mô phỏng WAN/bandwidth/packet hoặc
thời gian truyền client. Có đếm `logicalModelBytesDispatched` và
`logicalUpdateBytesAccepted` từ kích thước tensor thật; chúng không bao gồm metadata,
updates bị loại/partial transfers và không được trình bày như network traffic thực.

TXT nhóm C có bốn đối chiếu: C2−C1, C4−C3, C3−C1, C4−C2; thêm interaction
`(C4−C3)−(C2−C1)` cho từng seed và bảng mean ± SD. Đây là mô tả tương tác,
không phải kiểm định ý nghĩa thống kê hoặc bằng chứng hybrid luôn tốt hơn.

Nhóm C có thêm **C2−C5: Resource-aware so với Feasible Random dưới FedAvg**.
C5 dùng chung scenario, full-population traces, partition, initial weights và training
settings với C2. C2 được tái sử dụng, không chạy lại lần hai cho cặp mới.
`feasible_random` lấy ngẫu nhiên đều không lặp tối đa K client từ tập đang available,
đủ RAM và đáp ứng ước lượng deadline trước round. Nó dùng đúng predicate
`Policies.isFeasible` như Resource-aware, nhưng không ranking theo tốc độ/reliability,
không ưu tiên training loss và không đọc dropout/jitter tương lai.
Hai policy có thể có candidate sets khác nhau ở các round sau do lịch sử timing khác
nhau; báo cáo `estimatedFeasibleIds` giữ lại evidence cho từng round.

Phần nhận xét chỉ mô tả chênh lệch quan sát được, không tuyên bố ý nghĩa thống kê
hoặc chọn một phương pháp thắng trên mọi tiêu chí. Dùng validation để tune;
không chọn hyperparameter/best checkpoint dựa trên test metrics của báo cáo.

Nếu run lỗi, cặp đó xuất báo cáo `INCOMPLETE` cùng lỗi và các run đã hoàn tất,
không tạo kết luận thắng/thua; matrix dừng trước cặp tiếp theo. SQLite giữ evidence
để chẩn đoán/resume từng experiment qua API. Khởi động lại matrix tạo một batch mới,
không tự gộp các seed từ batch lỗi. Không cần train lại để xem TXT đã ghi.

Các experiment vẫn truy cập được qua `/experiments/{id}`, `/rounds`, `/result` và
`/metrics.csv`. Sau khi build JAR, `python scripts/verify_matrix.py` kiểm tra workflow A/B/C trên dữ liệu synthetic, cổng/database riêng và một round mỗi run, **với điều kiện đã bật ba lời gọi A/B/C** trong application class. `--client-selection-only` yêu cầu chỉ bật `compareClientSelection()` (C1–C5); tùy chọn này không kiểm tra cặp riêng C5/C6. Luôn kiểm tra các lời gọi đang bật trước khi dùng script này.

## Nhóm F — FMCDM client selection

Đối chứng sâu hơn về fairness coefficient nằm ở **nhóm L0–L5**, xem [Fixed Lambda Ablation](lambda-ablation.md). Nhóm L giữ nguyên engine và protocol, so sánh fixed0/.3/.5/.7/.9 với adaptive; báo cáo riêng `L-fixed-lambda-ablation.txt`, có stability và slots changed trên cùng factual history. Nhóm L không thay thế F và không mặc định kết luận adaptive tốt hơn fixed lambda lớn.

Nhóm F bổ sung thí nghiệm đối chứng cho selection tại **Federated Server**, trước khi dispatch local training. Cả năm dòng giữ aggregation **FedAvg**; không có aggregation method tên `fuzzy_topsis` và không có package FMCDM trong registry aggregation của Python.

| Run / hàm | Selection | Mục đích |
| --- | --- | --- |
| F1 / `runF1(seed)` | `feasible_random` | Baseline ngẫu nhiên sau feasibility filter |
| F2 / `runF2(seed)` | `resource_aware` | Baseline ranking tài nguyên |
| F3 / `runF3(seed)` | `fuzzy_topsis` | Fuzzy TOPSIS thuần |
| F4 / `runF4(seed)` | `fuzzy_topsis_fair` | Fuzzy TOPSIS + Fairness Credit cố định |
| F5 / `runF5(seed)` | `adaptive_fuzzy_topsis_fair` | Điều chỉnh fairness coefficient sau round đã hoàn tất |

`compareFuzzyClientSelection()` chạy mỗi dòng một lần cho mỗi seed, rồi xuất sáu cặp: **F1–F2, F1–F3, F3–F4, F4–F5, F1–F5, F2–F5**. Ba methods mới dùng chung engine Java tại `selection/fuzzy` và cùng feasibility predicate với F1/F2. Quy trình là availability → RAM/deadline feasibility → fuzzy ranking → fairness scheduling (nếu có) → local training. Credit và lambda được commit trong SQLite snapshot; resume không reset chúng.

Protocol trong `configurations/fuzzy-matrix.json`: **25 experiments = 5 dòng × 5 seeds `[42,43,44,45,46]`**, mỗi experiment **70 rounds**, 100 clients, K=5, MLP 54→256→128→7, Non-IID alpha=.5, local epoch=1, batch=32, learning rate=.01. Mọi dòng dùng cùng manifest cố định và heterogeneous scenario availability=.9, dropout=.05, deadline=10s, RAM requirement=600MB, jitter=.1. Cùng seed phải khớp actual initial weights và full-population traces; lịch sử timing vẫn có thể khiến feasible candidate pools khác nhau ở round sau.

Sau khi chuẩn bị hai manifests và khởi động Python worker như hướng dẫn trên, chạy từ repository root:

```powershell
$env:MINIFLS_METHOD = 'fuzzy_matrix'
$env:MINIFLS_WORKSPACE = (Get-Location).Path
$env:MINIFLS_FUZZY_MATRIX_CONFIG = 'configurations/fuzzy-matrix.json'
# Bỏ override cũ để dùng đúng 70 rounds từ protocol.
Remove-Item Env:MINIFLS_MATRIX_ROUNDS -ErrorAction SilentlyContinue
Set-Location ferderatedsystem
.\gradlew.bat bootRun --no-daemon
```

Chế độ này không cần bỏ comment A/B/C. Muốn smoke trên các manifest đã chuẩn bị, đặt `MINIFLS_MATRIX_ROUNDS=2` hoặc `3`; nó vẫn dùng danh sách seeds của JSON. Muốn kiểm tra tự động trên synthetic với 2 seeds × 3 rounds, chạy từ repo root sau khi build JAR:

```powershell
.\.venv\Scripts\python.exe scripts/verify_fuzzy.py
```

Kết quả nhóm F nằm tại `artifacts/comparisons/<batch-id>/F-fuzzy-client-selection.txt`, cùng evidence trong `runs/` và shared traces trong `traces/`. Report gồm mean ± sample SD, paired differences theo seed, final accuracy/Macro-F1/per-class recall, time-to-target và sustained target, selection/completion fairness, conditional coverage/Gini, accepted ratio và selector overhead. Có `virtualSeconds` không gồm selector và `virtualSecondsWithSelector` cộng selector/bookkeeping; candidate-pool divergence được ghi riêng. Run lỗi tạo `INCOMPLETE` cùng lý do.

`configurations/fuzzy-matrix.json` là cấu hình **batch**. Không POST nguyên file này vào `/experiments`; một run API cần lấy `baseConfig`, ghép top-level `fuzzySelection`, đặt `selection` và ID riêng. Xem [API contract](api-contract.md) và [công thức, defaults, limitations và resume](fuzzy-mcdm-client-selection.md). [Validation FMCDM](validation/fuzzy-mcdm-2026-10-25.md) chỉ kiểm chứng implementation bằng synthetic; chưa phải kết quả nghiên cứu Covertype 70 rounds và không được trộn hai protocol.
