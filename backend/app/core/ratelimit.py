"""Per-IP rate limiting for sensitive endpoints.

A simple in-memory, fixed-window limiter. Acceptable for this phase since
the API runs as a single process (`ROLE=api`); the full implementation
plan's token-bucket-in-MongoDB design (plan §9.3), which coordinates
rate limits across multiple API instances, is deferred until there is
more than one instance to coordinate. State resets on process restart --
documented here as a known scope limit, not an oversight.
"""

import time
from collections import defaultdict

from app.core.errors import AppError, ErrorCode


class RateLimiter:
    """A fixed-window, per-key request counter."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        """Record one request for `key`; return whether it's within the limit."""
        now = time.monotonic()
        window_start = now - self._window_seconds
        hits = self._hits[key]
        while hits and hits[0] < window_start:
            hits.pop(0)
        if len(hits) >= self._max_requests:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        """Clear all recorded hits.

        Exists so tests can isolate the module-level `login_rate_limiter`
        singleton between cases -- without this, a test file making more
        than `max_requests` login calls (e.g. a 5-failed-attempts lockout
        test followed by other login-exercising tests) would start
        failing with 429s unrelated to what each individual test is
        checking, since the TestClient's requests all share one apparent
        client IP.
        """
        self._hits.clear()


# Per Requirement 9.5: the login endpoint rejects excess per-IP requests
# with HTTP 429. 10 requests/minute is a reasonable default for this
# phase; later phases may make this configurable per `Settings`.
login_rate_limiter = RateLimiter(max_requests=10, window_seconds=60.0)


def enforce_login_rate_limit(client_ip: str) -> None:
    """Raise `RATE_LIMITED` / 429 if `client_ip` has exceeded the login limit."""
    if not login_rate_limiter.check(client_ip):
        raise AppError(
            ErrorCode.RATE_LIMITED,
            "Too many login attempts. Try again in a minute.",
        )
