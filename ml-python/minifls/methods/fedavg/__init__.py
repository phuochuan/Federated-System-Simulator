"""FedAvg: sample-count weights over accepted local SGD updates."""
from .algorithm import weights

STATUS = "implemented"
REFERENCE = "https://proceedings.mlr.press/v54/mcmahan17a.html"

__all__ = ["weights"]
