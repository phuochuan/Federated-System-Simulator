"""FedLBW: inverse proxy-loss weights over accepted local SGD updates."""
from .algorithm import weights

STATUS = "implemented"
REFERENCE = "https://arxiv.org/abs/2608.07007"

__all__ = ["weights"]
