"""Explicit registry of implemented research methods; no dynamic module imports."""
from . import fedavg, fedlbw, fedprox, oort, fairfedcs, longfed, fedavgm, fednova, scaffold

METHODS = {"fedavg": fedavg, "fedlbw": fedlbw}
PLANNED = {"fedprox": fedprox, "oort": oort, "fairfedcs": fairfedcs, "longfed": longfed,
           "fedavgm": fedavgm, "fednova": fednova, "scaffold": scaffold}


def catalog():
    return [dict(name=name, status=module.STATUS, package=module.__name__,
                 reference=getattr(module, "REFERENCE", None))
            for name, module in {**METHODS, **PLANNED}.items()]


def get_method(name):
    if name in PLANNED:
        raise NotImplementedError(f"Method {name!r} is planned, not implemented")
    try:
        return METHODS[name]
    except KeyError:
        raise ValueError(f"Unknown method {name!r}; supported: {', '.join(METHODS)}") from None
