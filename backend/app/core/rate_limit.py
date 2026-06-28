import time
from dataclasses import dataclass, field
from threading import Lock

from fastapi import HTTPException, Request, status

from app.core.config import settings


@dataclass
class _Bucket:
    attempts: list[float] = field(default_factory=list)


class InMemoryLoginRateLimiter:
    """Small per-process limiter for local/MVP deployments.

    For multi-process production deployments, replace this with Redis or another
    shared store. The contract stays the same.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._lock = Lock()

    def _ip_key(self, request: Request) -> str:
        host = request.client.host if request.client else "unknown"
        return f"ip:{host}"

    def _email_key(self, email: str) -> str:
        normalized_email = (email or "").strip().lower()
        return f"email:{normalized_email}"

    def _keys(self, request: Request, email: str) -> tuple[str, str]:
        return self._ip_key(request), self._email_key(email)

    def _prune(self, bucket: _Bucket, now: float, window: int) -> None:
        bucket.attempts = [ts for ts in bucket.attempts if now - ts < window]

    def check(self, request: Request, email: str) -> None:
        keys = self._keys(request, email)
        now = time.time()
        window = max(1, int(settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS))
        limit = max(1, int(settings.LOGIN_RATE_LIMIT_ATTEMPTS))
        with self._lock:
            for key in keys:
                bucket = self._buckets.setdefault(key, _Bucket())
                self._prune(bucket, now, window)
                if len(bucket.attempts) >= limit:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many login attempts. Try again later.",
                        headers={"Retry-After": str(window)},
                    )

    def register_failure(self, request: Request, email: str) -> None:
        keys = self._keys(request, email)
        now = time.time()
        window = max(1, int(settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS))
        with self._lock:
            for key in keys:
                bucket = self._buckets.setdefault(key, _Bucket())
                self._prune(bucket, now, window)
                bucket.attempts.append(now)

    def reset(self, request: Request, email: str) -> None:
        with self._lock:
            for key in self._keys(request, email):
                self._buckets.pop(key, None)


login_rate_limiter = InMemoryLoginRateLimiter()
