from datetime import UTC, datetime, timedelta

import pytest

from travel_backend import rate_limit
from travel_backend.errors import APIError
from travel_backend.rate_limit import check_rate_limit, reset_rate_limits


@pytest.fixture(autouse=True)
def _clean_buckets():
    reset_rate_limits()
    yield
    reset_rate_limits()


def test_expired_bucket_does_not_accumulate_dead_entries():
    check_rate_limit("chat:user-1", limit=5, window_seconds=60)
    # Age the only timestamp past the window.
    rate_limit._requests["chat:user-1"][0] = datetime.now(UTC) - timedelta(seconds=120)
    # Revisiting the key drains the stale entry; it must not be retained.
    check_rate_limit("chat:user-1", limit=5, window_seconds=60)
    assert len(rate_limit._requests["chat:user-1"]) == 1


def test_fully_expired_bucket_is_deleted_before_reuse():
    from collections import deque

    stale = deque([datetime.now(UTC) - timedelta(seconds=120)])
    rate_limit._requests["chat:user-stale"] = stale
    check_rate_limit("chat:user-stale", limit=5, window_seconds=60)
    # The stale bucket object must be discarded (key deleted) rather than mutated
    # in place, proving expired keys do not linger.
    assert rate_limit._requests["chat:user-stale"] is not stale
    assert len(rate_limit._requests["chat:user-stale"]) == 1


def test_active_key_is_retained_and_limit_enforced():
    for _ in range(3):
        check_rate_limit("chat:user-3", limit=3, window_seconds=60)
    assert "chat:user-3" in rate_limit._requests
    with pytest.raises(APIError) as exc:
        check_rate_limit("chat:user-3", limit=3, window_seconds=60)
    assert exc.value.code == "rate_limited"


def test_checking_any_key_sweeps_fully_expired_unique_keys():
    from collections import deque

    stale_time = datetime.now(UTC) - timedelta(seconds=120)
    for idx in range(10):
        rate_limit._requests[f"chat:stale-{idx}"] = deque([stale_time])

    check_rate_limit("chat:fresh", limit=5, window_seconds=60)

    assert sorted(rate_limit._requests) == ["chat:fresh"]
