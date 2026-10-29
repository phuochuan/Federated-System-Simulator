# E0 → E1: Fairness-Matched Fixed Lambda vs Adaptive

> Legacy Python prototype. The current Java implementation, three-repeat E0,
> multi-metric matching and locked evaluation are documented in
> [Java E0/E1 protocol](reproducibility-fairness-matched.md).

Protocol: [`configurations/fairness-matched.json`](../configurations/fairness-matched.json).
Runner: [`scripts/fairness_matched.py`](../scripts/fairness_matched.py).

## E0 — điều kiện trước E1

L3 (fixed λ=.7) và L5 (adaptive, initial λ=.3) chạy seed45, partition Covertype Non-IID42 hiện tại, 70 rounds, mỗi policy hai lần trong **mỗi** duration mode. Tổng 8 runs; không gộp hai duration modes. Có thể tăng số lần lặp bằng protocol mới trước khi đóng băng.

Runner sao chép JAR, Python package, Java source, config, protocol, scripts và dependency versions; lưu SHA-256 trước khi chạy. Mỗi experiment có database riêng và dịch vụ khởi động mới, một torch thread. Chỉ dùng binary/Python đã sao chép; thay đổi worktree sau đó không thay runtime của batch. Các file partition và trace được kiểm tra hash. Không chạy nhiều experiments đồng thời.

`timing.mode=measured` giữ hành vi cũ. `deterministic` dùng:

```
unscaledDurationSeconds = numSamples × localEpochs × timing.secondsPerSample
estimatedSeconds(next) = unscaledDurationSeconds / client.cpu
virtualTrainingSeconds = unscaledDurationSeconds / client.cpu × trace.jitterMultiplier
```

`secondsPerSample=.0005` là giả định protocol cố định, bằng cold-start prior hiện tại, **chưa được hiệu chuẩn phần cứng**. Dropout, RAM và deadline vẫn áp dụng. CPU chỉ được chia một lần. `actualTrainingMs` luôn là thời gian đo thực; `durationInputMs` ghi input dùng trong mô phỏng/lịch sử. Không sửa số đo thực thành số giả lập.

E0 replay độc lập TOPSIS, credit, controller, serialized decision history và timing estimates. Gate yêu cầu **trùng chính xác** ordered selected IDs, accepted IDs, candidate sets, scores, credits, λ, local/global tensor hashes, learning metrics mỗi round và simulated training time ở deterministic mode. Hash tensor không bao gồm UUID/checkpoint path. Với measured mode, kiểm tra cùng base model/client/round seed phải cho cùng local tensor hash/loss; thay đổi lịch chọn sau timing divergence được ghi riêng. Nếu kiểm tra này hoặc deterministic replay thất bại, E1 bị chặn.

Wall time, RSS, evaluation time, selector/bookkeeping overhead và server overhead là số đo thực, được miễn kiểm tra bằng nhau. `simulatedTrainingRoundSeconds` là thời gian train giả lập thuần; `virtualRoundSeconds` vẫn cộng measured server overhead như trước; `cumulativeVirtualSecondsWithSelector` cộng thêm measured selector/bookkeeping. Vì vậy **deterministic duration không làm mọi metric thời gian trở thành deterministic**. Learning/decision replay không được phép miễn trừ.

Audit measured trước đó: [`artifacts/seed45-audit/20261027-183349/report.md`](../artifacts/seed45-audit/20261027-183349/report.md). Bốn run seed45 cùng frozen runtime có accuracy mean=.723961, sample SD=.005906; Macro-F1 mean=.400438, sample SD=.022320. Đây là số đo conditional run-to-run variability của adaptive, chưa thay thế E0 L3/L5 trong build mới.

## E1 — validation và khóa policy

| Giai đoạn | Partition seeds | Training/scenario seeds | Policies | Runs |
| --- | --- | --- | --- | ---: |
| Validation | 1001,1002 | 42,43,44 | Fixed .60/.625/.65/.675/.70/.725 và Adaptive | 42 |
| Held-out evaluation | 2001,2002,2003 | 42–46 | Một fixed đã khóa và Adaptive | 30 |

Covertype, α=.5, 70 rounds, 100 clients, K=5, FedAvg, MLP54–256–128–7, epoch1/batch32/LR.01. Fuzzy engine, weights, uncertainty và adaptive controller giữ nguyên. Main protocol dùng deterministic duration; measured-duration sensitivity cần batch riêng, không gộp kết quả.

`--partition-seed` chỉ đổi RNG phân chia train rows cho clients. Split seed42 cố định train/proxy/test pools và scaler; partition seed không đổi test set. Các partition mới chưa dùng trong thí nghiệm cũ, nhưng held-out partitions không có nghĩa là một dataset test hoàn toàn mới. Runner xác minh hashes features/labels/splits trùng giữa các partitions.

Validation đánh giá trên **proxy split**, không gọi test evaluation. Chỉ final `feasibleOpportunityAdjustedGini` tham gia chọn λ. Adaptive parameters giữ nguyên, không chọn theo learning scores.

Với mỗi λ, tính `mean(|Gini_fixed(p,s) − Gini_adaptive(p,s)|)` trên sáu cặp partition/seed. Chọn minimum, tie chọn λ nhỏ hơn. Tolerance định trước: mean absolute paired gap ≤.025 và không partition nào có mean absolute gap >.05. Đây là tiêu chí matching thực dụng, **không phải kiểm định thống kê equivalence**. Không dùng absolute difference of overall means vì các sai lệch trái dấu có thể triệt tiêu nhau.

Nếu không candidate nào đạt: ghi `NO_MATCH`, không khởi chạy held-out evaluation, không tự nới tolerance/mở grid sau khi xem test. Grid/tolerance mới cần protocol exploratory mới. Nếu đạt, ghi `policy-lock.json` gồm λ đã chọn, adaptive config, protocol/runtime/input hashes trước khi chạy partitions2001–2003. Lock không được ghi đè bằng quyết định khác.

Held-out evaluation dùng test split; kiểm tra lại fairness gap nhưng **không retune**. Nếu fairness lệch ngoài tolerance trên held-out, báo trade-off, không gọi đó là learning advantage ở fairness tương đương.

## Kết quả và phân tích

Mỗi run xuất config, experiment/rounds/result JSON, logs, database và audit. Trajectories gốc chứa Gini, λ, selection staleness, slots changed và model hashes. `outcomes.csv/json` gồm final accuracy/F1, sample SD last10 rounds, maximum accuracy drop, unselected ratios, accepted ratio, first time-to-target và sustained-through-final status. Worst-case final accuracy là min của từng nhóm trong `summary-by-partition.json`.

Summary giữ seeds bên trong từng partition, không xem tất cả partition×seed cells là các samples độc lập. Accuracy–Gini Pareto PNG/SVG là mô tả trên grid đã thử, không phải chứng minh optimal frontier. Policy order được shuffle có seed trong mỗi cell để giảm run-order bias. `firstThreeRoundsBelowControllerTarget` là diagnostic: first start round của ba Gini liên tiếp ≤ controller target, không phải phát hiện change-point có kiểm định.

## Chạy và dừng

```powershell
Push-Location ferderatedsystem
.\gradlew.bat test bootJar --no-daemon
Pop-Location
.\.venv\Scripts\python.exe -m pytest ml-python/tests scripts/test_fairness_matched.py -q

# Kiểm tra synthetic3 rounds; smoke không mở gate E1 nghiên cứu.
.\.venv\Scripts\python.exe -u scripts/fairness_matched.py --stage e0 --smoke

# E0 Covertype8 runs, rồi dừng tại báo cáo gate.
.\.venv\Scripts\python.exe -u scripts/fairness_matched.py --stage e0

# Dùng CHÍNH folder E0 đã đạt để tiếp tục cùng frozen runtime.
.\.venv\Scripts\python.exe -u scripts/fairness_matched.py --stage validation --folder artifacts/fairness-matched/<batch>
.\.venv\Scripts\python.exe -u scripts/fairness_matched.py --stage evaluation --folder artifacts/fairness-matched/<batch>

# Hoặc E0→validation→evaluation tự động, có gate E0/NO_MATCH.
.\.venv\Scripts\python.exe -u scripts/fairness_matched.py --stage all
```

Tạo file `STOP` trong batch folder để dừng vòng đang chạy và dịch vụ của nó. Không xóa hoặc ghi đè dữ liệu đã hoàn tất. Runner tái dùng completed evidence chỉ khi config khớp chính xác; gặp run dở thì dừng để kiểm tra/recovery, không tự resubmit cùng ID. Tổng8+42+30 runs có thể mất vài giờ; E2/E3 không nằm trong runner này.
