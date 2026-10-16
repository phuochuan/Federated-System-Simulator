"""Independent virtual devices; no sleeps or OS resource constraints."""
import math
import random

import simpy


def simulate_round(jobs, seed, deadline=None, enabled=True, dropout=0.0, jitter=0.0):
    if deadline is not None and (not math.isfinite(deadline) or deadline <= 0):
        raise ValueError("Deadline must be finite and positive")
    env = simpy.Environment()
    results = []
    durations = []

    def device(job):
        # Independent stream per client prevents outcome changes caused by selection order.
        rng = random.Random(seed * 100003 + job["clientId"])
        duration = job["actualTrainingMs"] / 1000
        if enabled:
            duration = duration / job["cpu"] * rng.uniform(1 - jitter, 1 + jitter)
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("Invalid duration")
        status = "COMPLETED"
        if enabled and job["requiredRamMb"] > job["ramMb"]:
            status, duration = "SIMULATED_OOM", 0.0
        elif enabled and rng.random() < dropout:
            status = "DROPPED"
        completion = duration
        if deadline is not None and duration > deadline:
            status, completion = "TIMEOUT", deadline
        yield env.timeout(completion)
        durations.append(completion)
        results.append(dict(clientId=job["clientId"], status=status, virtualTrainingSeconds=duration,
                            completionSeconds=completion))

    for job in jobs:
        env.process(device(job))
    env.run()
    return dict(results=sorted(results, key=lambda r: r["clientId"]), virtualRoundSeconds=max(durations, default=0.0))
