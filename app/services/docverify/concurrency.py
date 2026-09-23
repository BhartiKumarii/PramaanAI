"""Concurrency control for the CPU-heavy verification pipeline.

The API process stays responsive (health checks, listing, auth) while at
most PRAMAAN_MAX_CONCURRENT_VERIFICATIONS pipelines run in worker threads;
up to PRAMAAN_MAX_QUEUED_VERIFICATIONS more wait. Beyond that the request is
refused with 503 + Retry-After instead of piling up until memory runs out —
the client (the Android sync worker) backs off and retries, and a load
balancer can route to another instance. The server keeps no per-request
state in memory (images are never stored), so horizontal scaling is just
more uvicorn workers or more instances behind a load balancer.
"""
from __future__ import annotations

import functools
import os
import threading
from typing import Any, Callable, TypeVar

import anyio

from app.core.config import get_settings

T = TypeVar("T")


class ServerBusy(Exception):
    retry_after_seconds = 15


_limiter: anyio.CapacityLimiter | None = None
_waiting = 0
_waiting_lock = threading.Lock()


def _get_limiter() -> anyio.CapacityLimiter:
    global _limiter
    if _limiter is None:
        _limiter = anyio.CapacityLimiter(max_concurrent())
    return _limiter


def max_concurrent() -> int:
    configured = get_settings().pramaan_max_concurrent_verifications
    return configured if configured > 0 else max(1, min(4, (os.cpu_count() or 2) // 2))


async def run_heavy(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a blocking pipeline call in a worker thread under the limiter."""
    global _waiting
    limiter = _get_limiter()
    with _waiting_lock:
        if limiter.available_tokens == 0 and _waiting >= get_settings().pramaan_max_queued_verifications:
            raise ServerBusy()
        _waiting += 1
    try:
        return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs), limiter=limiter)
    finally:
        with _waiting_lock:
            _waiting -= 1


def load() -> dict[str, int]:
    limiter = _get_limiter()
    return {"max_concurrent": int(limiter.total_tokens), "running": int(limiter.borrowed_tokens),
            "waiting": max(0, _waiting - int(limiter.borrowed_tokens)),
            "max_queued": get_settings().pramaan_max_queued_verifications}
