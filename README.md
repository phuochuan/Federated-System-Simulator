# MiniFLS — Resource-Aware Federated Learning Simulator

Research testbed dùng **Java Spring Boot + Python/PyTorch + SimPy**, chạy CPU với **100 logical clients**, chọn **5 clients/round** và chỉ **một local training job** tại một thời điểm. Dữ liệu chính: **UCI Covertype**; MLP **54 → 128 → 64 → 7**.

Đã triển khai pipeline thực: chuẩn bị dữ liệu → Java chọn client → PyTorch local training từ cùng checkpoint → SimPy quyết định kết quả mô phỏng → Java lọc update và tính weights → Python aggregate/evaluate → SQLite commit. Có FedAvg, FedLBW, Random/Resource-aware Selection, exploration, metrics, CSV/JSON, plots và resume sau gián đoạn.

Thiết kế dựa trên [kế hoạch Notion](https://app.notion.com/p/3fbb6ecc362380b29145ed0a5324deac). Kết quả smoke test không chứng minh một thuật toán tốt hơn thuật toán khác.

## Cài đặt trên Windows

Yêu cầu **JDK 17+** (đã kiểm chứng trên 17; hỗ trợ 21), **Python 3.11–3.13**, mạng cho lần tải dependencies và Covertype đầu tiên. Chạy PowerShell tại repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python -m pip install -e 'ml-python[test]'
```

`ml-python/requirements-validated.txt` ghi phiên bản môi trường Windows đã kiểm chứng. Để tái tạo, cài bằng `pip install -r ml-python/requirements-validated.txt --extra-index-url https://download.pytorch.org/whl/cpu`, rồi `pip install --no-deps -e ml-python`. Trên Linux thay đường dẫn Python bằng `.venv/bin/python`.

## Chuẩn bị dữ liệu

```powershell
# Dataset thật: split 435759 / 29051 / 116202.
.\.venv\Scripts\python -m minifls.data --dataset covertype --output artifacts/partitions/covertype-iid-42

# Non-IID, cùng seed; không ghi đè manifest cũ.
.\.venv\Scripts\python -m minifls.data --dataset covertype --strategy dirichlet_label_skew --alpha 0.5 --output artifacts/partitions/covertype-dirichlet-42

# Synthetic chỉ dùng kiểm thử nhanh.
.\.venv\Scripts\python -m minifls.data --dataset synthetic --output artifacts/partitions/synthetic-iid-42
```

Chỉ scale 10 numerical features của Covertype bằng statistics từ train. Labels chuyển 1–7 → 0–6. Proxy/test không nằm trong client partitions. Các mode khác: `iid_quantity_skew`, `dirichlet_mixed_skew`. Manifest lưu seed, indices, hashes, scaler và class histograms.

## Khởi động và chạy

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
.\.venv\Scripts\python -m minifls.experiment configurations/fedavg.json
```

Script build Java và chạy hai service ẩn, ghi PID vào `artifacts/processes.json`, logs vào `artifacts/logs/`. Java ở `http://127.0.0.1:8080`, Python ở `http://127.0.0.1:8000`; OpenAPI của Python ở `/docs`.

| Config | Dataset | Selection / aggregation | Simulation |
| --- | --- | --- | --- |
| `configurations/fedavg.json` | Covertype IID | Random / FedAvg, 20 rounds | Tắt |
| `configurations/resource-aware-fedlbw.json` | Covertype Dirichlet | Resource-aware / FedLBW | CPU/RAM, availability, dropout, deadline |
| `configurations/smoke.json` | Synthetic | Random / FedAvg, 20 rounds | Heterogeneous |

Mỗi run mới cần `experimentId` mới. Tiếp tục run `FAILED`/`INTERRUPTED` bằng đúng config với `--resume`:

```powershell
.\.venv\Scripts\python -m minifls.experiment configurations/fedavg.json --resume
Invoke-RestMethod http://127.0.0.1:8080/experiments
```

Chạy thủ công: tạo `artifacts` trước và dùng hai terminal:

```powershell
# Terminal 1, tại repo root; luôn --workers 1.
.\.venv\Scripts\python -m uvicorn minifls.api:app --host 127.0.0.1 --port 8000 --workers 1

# Terminal 2
cd ferderatedsystem
.\gradlew.bat bootRun
```

Dừng service chạy bằng script: xem PID trong `artifacts/processes.json`, dùng `Stop-Process -Id <PID>` cho từng service. Biến môi trường: `MINIFLS_WORKSPACE`, `MINIFLS_WORKER_URL`, `MINIFLS_SERVER_PORT`, `MINIFLS_DATABASE`, `MINIFLS_TORCH_THREADS`.

## Kết quả và kiểm chứng

SQLite: `artifacts/minifls.db`. CLI xuất `artifacts/results/<experimentId>/experiment.json`, `rounds.json`, `metrics.csv`. Snapshot chứa config, manifest, Git commit, checkpoint và client histories. Round JSON chứa selection decisions, statuses, model versions, weights, proxy losses, test metrics và hai loại thời gian.

```powershell
.\.venv\Scripts\python -m minifls.plot artifacts/results/covertype-fedavg-42/metrics.csv
.\.venv\Scripts\python -m minifls.benchmark artifacts/partitions/covertype-iid-42 --epochs 5
.\.venv\Scripts\python -m pytest ml-python/tests -q
Push-Location ferderatedsystem
.\gradlew.bat test bootJar --no-daemon
Pop-Location
.\.venv\Scripts\python scripts/verify_e2e.py
```

Integration test tự khởi động service trên port riêng, chạy 100 clients/20 rounds, kiểm tra OOM/dropout/timeout exclusion, FedLBW và worker crash/resume. CI chạy cùng bộ kiểm tra trên Linux.

CPU/RAM là **virtual simulation**. RSS đo được thuộc toàn worker. CPU scaling, `requiredRamMb` và cold-start prior cần hiệu chỉnh theo benchmark trước khi kết luận về hiệu quả tài nguyên. Virtual time phụ thuộc thời gian training đo thật; seed không bảo đảm wall time giống tuyệt đối. Không có 100 processes/containers.

Chi tiết: [kiến trúc](docs/architecture.md), [API](docs/api-contract.md), [quy trình thí nghiệm và coverage](docs/experiment-protocol.md). FedProx, Oort, Lyapunov fairness, fuzzy selection và WAN emulation là phần mở rộng chưa triển khai.
