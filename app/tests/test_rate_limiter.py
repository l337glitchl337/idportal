import time
import pytest
from helpers.rate_limiter import RateLimiter


@pytest.fixture
def limiter():
    return RateLimiter(max_calls=3, period=60)


def test_allows_calls_under_limit(limiter):
    assert limiter.is_allowed("key1") is True
    assert limiter.is_allowed("key1") is True
    assert limiter.is_allowed("key1") is True


def test_blocks_when_limit_reached(limiter):
    limiter.is_allowed("key1")
    limiter.is_allowed("key1")
    limiter.is_allowed("key1")
    assert limiter.is_allowed("key1") is False


def test_different_keys_tracked_independently(limiter):
    limiter.is_allowed("a")
    limiter.is_allowed("a")
    limiter.is_allowed("a")
    # 'a' is blocked, 'b' should still be allowed
    assert limiter.is_allowed("a") is False
    assert limiter.is_allowed("b") is True


def test_calls_expire_after_period():
    short_limiter = RateLimiter(max_calls=2, period=1)
    short_limiter.is_allowed("x")
    short_limiter.is_allowed("x")
    assert short_limiter.is_allowed("x") is False
    time.sleep(1.05)
    assert short_limiter.is_allowed("x") is True


def test_window_is_sliding_not_fixed():
    short_limiter = RateLimiter(max_calls=2, period=1)
    short_limiter.is_allowed("x")
    time.sleep(0.6)
    short_limiter.is_allowed("x")
    # First call has not expired yet, so third should be blocked
    assert short_limiter.is_allowed("x") is False
    time.sleep(0.5)
    # First call expired, one slot opens up
    assert short_limiter.is_allowed("x") is True


def test_zero_calls_allowed():
    l = RateLimiter(max_calls=0, period=60)
    assert l.is_allowed("x") is False


def test_new_key_is_always_allowed(limiter):
    for i in range(10):
        assert limiter.is_allowed(f"fresh-key-{i}") is True
