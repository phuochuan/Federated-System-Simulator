# Chạy controlled experiment matrix bằng các hàm Java

Trong `FerderatedsystemApplication.paperExperiment()`, chế độ `MINIFLS_METHOD=matrix` gọi tuần tự:

```java
matrix.compareModelSizes();       // A1 và A2
matrix.compareAggregations();     // B1 và B2
matrix.compareClientSelection();  // C1/C2/C3/C4: factorial 2x2
```

Các hàm nằm trong `ControlledExperiments`. A/B gọi hai hàm tương ứng cho từng seed;
C gọi bốn hàm của thiết kế 2x2. Mỗi experiment phải hoàn thành trước khi chạy tiếp.
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

Mặc định là **8 dòng × 5 seeds (42–46) = 40 experiment**, mỗi experiment 100 round.
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

Riêng C1–C4 cùng lấy `heterogeneousScenario`: resourceProfile=heterogeneous,
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

Phần nhận xét chỉ mô tả chênh lệch quan sát được, không tuyên bố ý nghĩa thống kê
hoặc chọn một phương pháp thắng trên mọi tiêu chí. Dùng validation để tune;
không chọn hyperparameter/best checkpoint dựa trên test metrics của báo cáo.

Nếu run lỗi, cặp đó xuất báo cáo `INCOMPLETE` cùng lỗi và các run đã hoàn tất,
không tạo kết luận thắng/thua; matrix dừng trước cặp tiếp theo. SQLite giữ evidence
để chẩn đoán/resume từng experiment qua API. Khởi động lại matrix tạo một batch mới,
không tự gộp các seed từ batch lỗi. Không cần train lại để xem TXT đã ghi.

Các experiment vẫn truy cập được qua `/experiments/{id}`, `/rounds`, `/result` và
`/metrics.csv`. Chạy `python scripts/verify_matrix.py` sau khi build JAR để kiểm tra
toàn bộ workflow trên dữ liệu synthetic, cổng/database riêng và một round mỗi run.
