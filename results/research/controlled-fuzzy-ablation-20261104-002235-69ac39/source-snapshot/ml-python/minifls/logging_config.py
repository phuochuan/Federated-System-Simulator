"""Console logging and per-operation context shared by worker/CLI modules."""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
import logging
import os
import time

_context = ContextVar("minifls_log_context", default={})


class OperationFilter(logging.Filter):
    def filter(self, record):
        context = _context.get()
        for field in ("experiment", "round_id", "client_id", "attempt"):
            setattr(record, field, context.get(field, "-"))
        return True


def configure_logging():
    logger = logging.getLogger("minifls")
    level = os.environ.get("MINIFLS_LOG_LEVEL", "INFO").upper()
    logger.setLevel(logging.getLevelNamesMapping().get(level, logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.addFilter(OperationFilter())
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-5s %(name)s experiment=%(experiment)s round=%(round_id)s "
            "client=%(client_id)s attempt=%(attempt)s %(message)s"))
        logger.addHandler(handler)
    # Dedicated handler works under uvicorn and direct CLI runs without duplicate root output.
    logger.propagate = False


def set_log_context(**fields):
    _context.set({**_context.get(), **fields})


@contextmanager
def log_context(**fields):
    token = _context.set({**_context.get(), **fields})
    try:
        yield
    finally:
        _context.reset(token)


def logged_operation(name):
    """Keep IDs scoped to one sync FastAPI worker call and log failures with context."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            request = kwargs.get("req")
            if request is None:
                request = next((arg for arg in args if hasattr(arg, "model_dump")), None)
            inherited = _context.get()
            token = _context.set(dict(experiment=getattr(request, "experimentId", inherited.get("experiment", "-")),
                                      round_id=getattr(request, "roundId", inherited.get("round_id", "-")),
                                      client_id=getattr(request, "clientId", inherited.get("client_id", "-")),
                                      attempt=getattr(request, "operationId", inherited.get("attempt", "-"))))
            logger = logging.getLogger(function.__module__)
            started = time.perf_counter()
            logger.info("%s.started", name)
            try:
                result = function(*args, **kwargs)
                logger.info("%s.completed elapsedMs=%.2f", name, (time.perf_counter() - started) * 1000)
                return result
            except Exception as exc:
                if isinstance(exc, (ValueError, FileNotFoundError)) or 400 <= getattr(exc, "status_code", 0) < 500:
                    logger.warning("%s.rejected error=%s", name, exc)
                else:
                    logger.exception("%s.failed elapsedMs=%.2f", name, (time.perf_counter() - started) * 1000)
                raise
            finally:
                _context.reset(token)
        return wrapped
    return decorate
