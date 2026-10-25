# Theo dõi Java và Python

Mặc định cả hai phía dùng `INFO`. Đặt `MINIFLS_LOG_LEVEL=DEBUG` trong môi trường của
Java và Python trước khi khởi động để xem thêm chi tiết; `WARN` chỉ giữ cảnh báo
và lỗi ở cả hai phía. Python cũng chấp nhận tên `WARNING`. Các cấp thông dụng khác là `ERROR`, `INFO`, `DEBUG`.
Nếu đổi biến trong terminal, cần khởi động lại process. Với IntelliJ, đặt biến trong Run Configuration.

Java ghi các sự kiện:

- `experiment.admitted`, `experiment.initializing`, `experiment.resume`, `experiment.completed`.
- `round.started`, `selection.completed`: số client đủ điều kiện và danh sách được chọn.
- `training.dispatched`, `training.completed`: client, số mẫu, loss, thời gian và RAM worker.
- `update.accepted`, `update.rejected`: trạng thái mô phỏng, thời gian hoàn tất và deadline.
- `aggregation.weights`, `aggregation.completed`, `aggregation.skipped`.
- `evaluation.completed`, `round.committed`: accuracy, loss, Macro-F1, coverage, wall/virtual time.
- `repository.status_saved`, `result.loaded`: trạng thái lưu và round được API result đọc.
- `experiment.failed`: round đã commit gần nhất và stack trace của lỗi.

Python ghi `dataset.loading`, `data.partitioned`, `model.initialized`, `train.config`,
`train.epoch`, `train.saved`, `simulation.device`, `simulation.summary`, `aggregate.saved`
và `evaluate.metrics`. Mỗi operation có sự kiện `.started`/`.completed` cùng elapsed time.
`evaluate.config owner=server` xác định rõ evaluation thuộc server; `train.epoch` là loss local.
Lỗi validation/busy/OOM/dropout/timeout xuất hiện ở mức cảnh báo; lỗi bất ngờ có stack trace.

Ví dụ rút gọn:

```text
round.started experiment=fedavg-... round=1/20 modelVersion=0 operation=...
train.epoch epoch=1/1 loss=1.234567 samples=4358 elapsedMs=120.00
evaluate.metrics split=test loss=0.800000 accuracy=0.700000 macroF1=0.300000 worstClassRecall=0.000000
round.committed experiment=fedavg-... round=20/20 outcome=COMMITTED ...
```

Java log có `experiment`, `round`, `client` tại các sự kiện tương ứng. Python có thêm
prefix `experiment=... round=... client=... attempt=...`. Java gửi correlation headers
cho worker để giữ các ID khi evaluate/simulation không mang ID trong body.
Headers chỉ phục vụ logging; kiểm tra experiment/model version vẫn dựa trên payload và checkpoint.
`-` nghĩa là thao tác chưa có trường đó (ví dụ startup, health hoặc gọi API thủ công).
Context được xóa sau mỗi request/job để các client hoặc experiment không lẫn ID.

`DEBUG` bổ sung HTTP route/status/thời gian, checkpoint load/save, tiến độ mỗi 50 batch,
precision/recall từng lớp và confusion matrix. Tensor weights và dữ liệu từng mẫu không được dump.
INFO có thể tạo nhiều dòng khi chạy nhiều round/client; dùng `WARN` khi chỉ cần xem lỗi/cảnh báo.

Khi chạy bằng `scripts/start.ps1`:

- Java: `artifacts/logs/server.log`, stderr ở `server-error.log`.
- Python: application logs ghi stderr nên nằm trong `artifacts/logs/worker-error.log`;
  HTTP access log của uvicorn thường ở `worker.log`. Tên `worker-error.log` không có nghĩa mọi dòng là lỗi.

Khi Run Java bằng IDE, log nằm ở tab Run. Khi chạy Python bằng terminal, log nằm trong terminal đó.
Các metrics chính vẫn được lưu trong SQLite và API; log dùng để theo dõi và chẩn đoán.
