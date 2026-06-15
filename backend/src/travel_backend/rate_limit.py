from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from .errors import APIError

_requests: dict[str, deque[datetime]] = defaultdict(deque)


def reset_rate_limits() -> None:
    _requests.clear()


def check_rate_limit(key: str, limit: int = 20, window_seconds: int = 60) -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=window_seconds)
    for existing_key, existing_bucket in list(_requests.items()):
        while existing_bucket and existing_bucket[0] < cutoff:
            existing_bucket.popleft()
        if not existing_bucket:
            del _requests[existing_key]
    bucket = _requests.get(key)
    if bucket is not None and len(bucket) >= limit:
        raise APIError(429, "rate_limited")
    if bucket is None:
        bucket = _requests[key]
    bucket.append(now)
