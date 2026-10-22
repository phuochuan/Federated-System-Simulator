"""Algorithm-specific logic; tensor validation/averaging stays in minifls.model."""
import math


def weights(samples, losses):
    if not samples or any(n <= 0 for n in samples):
        raise ValueError("Positive sample counts required")
    total = math.fsum(samples)
    return [n / total for n in samples]
