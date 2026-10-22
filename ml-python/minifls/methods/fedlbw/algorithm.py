"""Same inverse-loss formula and zero-loss policy as the original coordinator."""
import math


def weights(samples, losses):
    if not samples or any(n <= 0 for n in samples):
        raise ValueError("Positive sample counts required")
    if len(losses) != len(samples) or any(not math.isfinite(loss) or loss < 0 for loss in losses):
        raise ValueError("Finite nonnegative proxy losses required for every update")
    clamped = [max(loss, 1e-12) for loss in losses]
    minimum = min(clamped)
    inverse = [minimum / loss for loss in clamped]
    total = math.fsum(inverse)
    return [value / total for value in inverse]
