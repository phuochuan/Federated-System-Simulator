"""Mô phỏng thiết bị ảo độc lập; không sleep hoặc giới hạn tài nguyên hệ điều hành."""
import math
import random
import logging
from collections import Counter

import simpy

log = logging.getLogger(__name__)


def simulate_round(jobs, seed, deadline=None, enabled=True, dropout=0.0, jitter=0.0):
    log.info("simulation.config jobs=%s seed=%s enabled=%s deadline=%s dropout=%s jitter=%s",
             len(jobs), seed, enabled, deadline, dropout, jitter)
    if deadline is not None and (not math.isfinite(deadline) or deadline <= 0):
        raise ValueError("Deadline must be finite and positive")
    env = simpy.Environment()
    results = []
    durations = []

    def device(job):
        # Mỗi client có luồng ngẫu nhiên riêng, tránh phụ thuộc thứ tự chọn client.
        rng = random.Random(seed * 100003 + job["clientId"])
        simulated_ms = job.get("simulatedTrainingMs")
        duration = (job["actualTrainingMs"] if simulated_ms is None else simulated_ms) / 1000
        multiplier = job.get("jitterMultiplier")
        dropout_event = job.get("dropoutEvent")
        if enabled:
            multiplier = rng.uniform(1 - jitter, 1 + jitter) if multiplier is None else multiplier
            if not math.isfinite(multiplier) or not 0 < multiplier < 2:
                raise ValueError("Invalid jitter multiplier")
            duration = duration / job["cpu"] * multiplier
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("Invalid duration")
        status = "COMPLETED"
        # OOM ở đây là kết quả mô phỏng theo ngân sách RAM, không phải lỗi PyTorch thật.
        if enabled and job["requiredRamMb"] > job["ramMb"]:
            status, duration = "SIMULATED_OOM", 0.0
        elif enabled and (rng.random() < dropout if dropout_event is None else dropout_event):
            status = "DROPPED"
        completion = duration
        # Deadline cắt thời gian chờ; update đến muộn không được Java đưa vào aggregation.
        if deadline is not None and duration > deadline:
            status, completion = "TIMEOUT", deadline
        yield env.timeout(completion)
        durations.append(completion)
        results.append(dict(clientId=job["clientId"], status=status, virtualTrainingSeconds=duration,
                            completionSeconds=completion, dropoutEvent=dropout_event, jitterMultiplier=multiplier))
        log.log(logging.INFO if status == "COMPLETED" else logging.WARNING,
                "simulation.device client=%s status=%s virtualSeconds=%.6f completionSeconds=%.6f cpu=%s ramMb=%s requiredRamMb=%s",
                job["clientId"], status, duration, completion, job["cpu"], job["ramMb"], job["requiredRamMb"])

    for job in jobs:
        env.process(device(job))
    env.run()
    log.info("simulation.summary statuses=%s virtualRoundSeconds=%.6f", dict(Counter(r["status"] for r in results)), max(durations, default=0.0))
    # Thiết bị ảo chạy song song nên round lấy thời gian lớn nhất, không cộng từng client.
    return dict(results=sorted(results, key=lambda r: r["clientId"]), virtualRoundSeconds=max(durations, default=0.0))
