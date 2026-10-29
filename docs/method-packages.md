# Packages theo phương pháp và cách gọi từ Java

Nguồn danh sách: [Federated System Simulator, §8, §9 và §16](https://app.notion.com/p/3fbb6ecc362380b29145ed0a5324deac).
Tài liệu phân biệt registry phương pháp Python và client selectors Java. Các package có nhãn `planned` dưới đây chưa có thuật toán; FMCDM/Fuzzy TOPSIS đã được triển khai riêng ở Java và có nhóm F trong Controlled Experiment Matrix.

```text
ml-python/minifls/
  methods/
    __init__.py         # registry tường minh + trạng thái từng phương pháp
    fedavg/             # sample-count weighting, chạy được
      algorithm.py
    fedlbw/             # inverse proxy-loss weighting, chạy được
      algorithm.py
    fedprox/            # planned: proximal local objective
    oort/               # planned: guided client selection
    fairfedcs/          # planned: fairness-aware selection
    longfed/            # planned: long-term participation
    fedavgm/            # planned: server momentum
    fednova/            # planned: normalized local updates
    scaffold/           # planned: control variates
  api.py                # HTTP adapter và shared local SGD/evaluation
  data.py               # dataset/split/partition dùng chung
  model.py              # shared MLP/checkpoint/tensor averaging
  simulation.py         # mô phỏng thiết bị, độc lập với phương pháp
```

FedAvg/FedLBW dùng chung local SGD; khác biệt hiện tại nằm ở cách tính trọng số.
Không sao chép trainer vào từng package. Java gọi `PythonMLClient.fedAvgWeights()` hoặc
`fedLBWWeights()` → `POST /methods/{method}/weights` → package Python tương ứng.
Java kiểm tra số lượng, tính hữu hạn, dấu và tổng trọng số trước khi yêu cầu tensor aggregation.
Java vẫn chịu trách nhiệm selection, acceptance, model version và commit SQLite.
So với bản kế hoạch Notion ban đầu, công thức scalar weights được chuyển từ Java sang Python
theo yêu cầu tổ chức thuật toán theo package; các file JSON cấu hình hiện tại vẫn dùng được.

| Method ID | Hàm Java trong `PaperExperiments` | Trạng thái |
| --- | --- | --- |
| `fedavg` | `runFedAvg()` | Chạy được |
| `fedlbw` | `runFedLBW()` | Chạy được |
| `fedprox` | `runFedProx()` | Khung package, chưa có thuật toán |
| `oort` | `runOort()` | Khung package, chưa có thuật toán |
| `fairfedcs` | `runFairFedCS()` | Khung package, chưa có thuật toán |
| `longfed` | `runLongFed()` | Khung package, chưa có thuật toán |
| `fedavgm` | `runFedAvgM()` | Khung package, chưa có thuật toán |
| `fednova` | `runFedNova()` | Khung package, chưa có thuật toán |
| `scaffold` | `runScaffold()` | Khung package, chưa có thuật toán |

`GET /methods` liệt kê cả phương pháp chạy được và các package dự kiến.
Gọi phương pháp chưa triển khai sẽ dừng trước khi tạo experiment. HTTP weights trả 501;
tên không tồn tại trả 400. Không có fallback sang thuật toán khác.
Resource-aware hiện là heuristic chọn client ở Java, không phải một bản triển khai Oort.
FMCDM (Fuzzy Multi-Criteria Decision Making) được triển khai trong Java `selection/fuzzy`, gọi tại `RoundCoordinator` trước local training. Các tên `fuzzy_topsis`, `fuzzy_topsis_fair`, `adaptive_fuzzy_topsis_fair` là giá trị **selection**, không phải tên Python package hoặc aggregation. Chúng không xuất hiện trong `GET /methods` và không được gọi qua `/methods/{method}/weights`.

Nhóm F dùng `ControlledExperiments.compareFuzzyClientSelection()` với F1 Feasible Random, F2 Resource-aware, F3 Fuzzy TOPSIS thuần, F4 thêm Fairness Credit và F5 adaptive credit. Aggregation giữ FedAvg cho cả năm dòng. Xem [controlled matrix](controlled-matrix.md#nhóm-f--fmcdm-client-selection) và [công thức/cấu hình FMCDM](fuzzy-mcdm-client-selection.md). FedA2L/FedIPSA vẫn là ghi chú liên quan, chưa được ghép vào pipeline centralized này.

## Chạy trong IDE từ application class

1. Chuẩn bị dataset theo README và khởi động Python worker trước, với đúng một uvicorn worker.
2. Mở Run Configuration của `FerderatedsystemApplication` và đặt các biến môi trường bên dưới.
3. Run/Debug application. Với single-run mode, bean `paperExperiment` gọi `experiments.runConfigured()` khi Spring sẵn sàng. `fuzzy_matrix` gọi `matrix.compareFuzzyClientSelection()`; `lambda_ablation` gọi `matrix.compareFixedLambdaAblation()`; `matrix` chỉ chạy các lời gọi A/B/C bạn bật.
4. Đọc log để lấy ID; xem trạng thái ở `/experiments/{id}` và kết quả ở `/experiments/{id}/rounds`.

| Biến môi trường | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `MINIFLS_METHOD` | `none` | `fedavg`/`fedlbw`: một run; `fuzzy_matrix`: nhóm F; `lambda_ablation`: nhóm L; `matrix`: các lời gọi A/B/C được bật; `none`: chỉ mở API |
| `MINIFLS_WORKSPACE` | Tìm thư mục repo hiện tại hoặc thư mục cha | Root dùng chung cho Java và Python |
| `MINIFLS_CONFIG` | `configurations/fedavg.json` | File JSON, tính từ workspace; chấp nhận đường dẫn tuyệt đối |
| `MINIFLS_EXPERIMENT_ID` | `<method>-<UUID>` | ID duy nhất cho lần chạy mới |
| `MINIFLS_MANIFEST` | Giữ giá trị JSON | Thư mục dataset đã chuẩn bị, tương đối với workspace |
| `MINIFLS_SELECTION` | Giữ giá trị JSON | Single-run: `random`, `feasible_random`, `resource_aware`, `fuzzy_topsis`, `fuzzy_topsis_fair`, `adaptive_fuzzy_topsis_fair`; fuzzy cần `fuzzySelection` trong JSON |
| `MINIFLS_ROUNDS` | Giữ giá trị JSON | Số round |
| `MINIFLS_SEED` | Giữ giá trị JSON | Seed của experiment |
| `MINIFLS_MATRIX_CONFIG` | `configurations/controlled-matrix.json` | Batch A/B/C khi `MINIFLS_METHOD=matrix` |
| `MINIFLS_FUZZY_MATRIX_CONFIG` | `configurations/fuzzy-matrix.json` | Batch F1–F5 khi `MINIFLS_METHOD=fuzzy_matrix` |
| `MINIFLS_LAMBDA_MATRIX_CONFIG` | `configurations/lambda-ablation.json` | Batch L0–L5; xem [lambda ablation](lambda-ablation.md) |
| `MINIFLS_MATRIX_ROUNDS` | `baseConfig.rounds` | Override round cho cả ba batch mode; để trống cho protocol 70 rounds |
| `MINIFLS_WORKER_URL` | `http://127.0.0.1:8000` | Địa chỉ Python |
| `MINIFLS_SERVER_PORT` | `8080` | Cổng Java |
| `MINIFLS_DATABASE` | `../artifacts/minifls.db` | Nên dùng đường dẫn tuyệt đối khi chạy IDE |
| `MINIFLS_TORCH_THREADS` | `1` | Số thread CPU ở Python |
| `MINIFLS_MODEL_ARCHITECTURE` | `mlp_54_256_128_7` | Đặt ở môi trường Python; chọn model cho experiment mới |

Model mới mặc định là `54 → 256 → 128 → 7` (47.879 tham số), dùng ReLU và logits như baseline.
Muốn so sánh với bản cũ, đặt `$env:MINIFLS_MODEL_ARCHITECTURE = 'mlp_54_128_64_7'`
trước khi khởi động Python. Khi gọi `runFedAvg()`/`runFedLBW()` ở Java, worker sẽ dùng mặc định này
cho checkpoint ban đầu. Cần tạo experiment mới để đổi kiến trúc; resume luôn giữ kiến trúc trong checkpoint.
Không cần tạo lại dataset. Các số liệu validation đã lưu trong repo thuộc model nhỏ, chưa chứng minh
model lớn cải thiện accuracy/Macro-F1. `requiredRamMb` vẫn là giả định mô phỏng, không tự hiệu chỉnh theo model.

Benchmark tập trung có cùng lựa chọn, ví dụ:
`python -m minifls.benchmark artifacts/partitions/covertype-iid-42 --architecture mlp_54_256_128_7 --name centralized-large-42`.

Thứ tự áp dụng: đọc JSON → chọn aggregation theo hàm/method → áp dụng biến override → validate → submit.
ID trong JSON được thay bằng `MINIFLS_EXPERIMENT_ID` hoặc UUID mới để tránh trùng ID qua các lần test.
`MINIFLS_SEED` không tạo lại dataset: split/partition vẫn lấy từ manifest đã chuẩn bị.
Các override single-run (`MINIFLS_CONFIG`, `MINIFLS_SELECTION`, `MINIFLS_ROUNDS`, `MINIFLS_SEED`, manifest/ID) không áp dụng cho ba batch mode. File matrix có cấu trúc riêng; không dùng nguyên `fuzzy-matrix.json` hay `lambda-ablation.json` làm `MINIFLS_CONFIG` hay body `POST /experiments`. Xem [ví dụ tạo body API đầy đủ](api-contract.md).
Để resume một run cũ, đặt `MINIFLS_METHOD=none` rồi dùng endpoint resume/CLI hiện có.

Ví dụ PowerShell từ thư mục gốc repo, sau khi đã chuẩn bị dataset synthetic:

```powershell
# Terminal 1
$env:MINIFLS_WORKSPACE = (Get-Location).Path
.\.venv\Scripts\python.exe -m uvicorn minifls.api:app --host 127.0.0.1 --port 8000 --workers 1

# Terminal 2
$env:MINIFLS_WORKSPACE = (Get-Location).Path
$env:MINIFLS_DATABASE = Join-Path $env:MINIFLS_WORKSPACE 'artifacts/minifls.db'
$env:MINIFLS_METHOD = 'fedlbw'
$env:MINIFLS_CONFIG = 'configurations/smoke.json'
$env:MINIFLS_ROUNDS = '2'
Set-Location ferderatedsystem
.\gradlew.bat bootRun
```

Muốn gọi trực tiếp trong Java, thay dòng `experiments.runConfigured()` ở
`FerderatedsystemApplication.paperExperiment()` bằng đúng một hàm:

```java
experiments.runFedAvg();
// hoặc: experiments.runFedLBW();
```

Hàm gọi trực tiếp quyết định phương pháp; các biến cấu hình khác vẫn có hiệu lực.
Không gọi đồng thời nhiều hàm vì coordinator chỉ nhận một experiment tại một thời điểm.
File `.env.example` là mẫu cấu hình; Spring/PowerShell không tự nạp `.env`.

## Thêm thuật toán mới

Triển khai logic vào package tương ứng, kèm test công thức và các ràng buộc riêng của bài báo.
Local objectives như FedProx cần nối vào trainer; selector như Oort cần contract selection/history;
SCAFFOLD/FedAvgM cần bổ sung state và snapshot phục hồi. Chỉ tạo `weights()` không đủ cho các phương pháp này.
Sau khi có luồng thực thi đầy đủ, nối registry, API, schema/config Java và coordinator rồi mới chuyển trạng thái
package từ `planned` sang `implemented`. Registry chỉ chứa các package tường minh, không import module theo chuỗi người dùng.
