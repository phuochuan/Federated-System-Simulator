"""Durable replies for checkpoint-producing POST retries.

The API's single-worker exclusive lock must cover lookup, execution and commit.
An existing checkpoint without a reply receipt fails closed: never overwrite it
or invent its original measured duration after an interrupted receipt commit.
"""
import hashlib
import json
import os
from pathlib import Path
import uuid

from fastapi import HTTPException

from .model import load_checkpoint


def value_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def request_hash(req):
    return value_hash(req.model_dump(mode="json"))


def receipt_path(target):
    return Path(target).with_suffix(".response.json")


def cached_response(req, target):
    target = Path(target)
    receipt = receipt_path(target)
    digest = request_hash(req)
    if not receipt.exists():
        if target.exists():
            raise HTTPException(409, "Operation checkpoint exists without a committed response receipt; resume the round with a new operationId")
        return None
    saved = json.loads(receipt.read_text(encoding="utf-8"))
    if saved.get("version") != 1 or saved.get("requestHash") != digest:
        raise HTTPException(409, "Operation id reused with different request parameters")
    checkpoint = load_checkpoint(target)
    response = saved["response"]
    if saved.get("responseHash") != value_hash(response):
        raise ValueError("Operation response receipt integrity mismatch")
    if checkpoint.get("operationRequestHash") != digest or checkpoint["modelStateHash"] != response["modelStateHash"]:
        raise ValueError("Operation receipt/checkpoint integrity mismatch")
    return response


def commit_response(req, target, response):
    target = Path(target)
    destination = receipt_path(target)
    if not target.exists() or destination.exists():
        raise ValueError("Operation response requires one immutable checkpoint and a new receipt")
    temporary = destination.with_suffix(f".{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump({"version": 1, "requestHash": request_hash(req), "responseHash": value_hash(response), "response": response}, stream,
                      sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return response
