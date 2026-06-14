from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from .errors import APIError

_requests: dict[str, deque[datetime]] = defaultdict(deque)


def check_rate_limit(key: str, limit: int = 20, window_seconds: int = 60) -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=window_seconds)
    bucket = _requests[key]
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= limit:
        raise APIError(429, "rate_limited")
    bucket.append(now)
