"""Shared (Redis) rate limiter: counting, fallback, and limit=0 behaviour."""
from app.rate_limit import RedisLimiter, SlidingWindowLimiter


class _FakePipeline:
    def __init__(self, store):
        self.store = store
        self.key = None

    def incr(self, key):
        self.key = key
        return self

    def expire(self, key, ttl):
        return self

    def execute(self):
        self.store[self.key] = self.store.get(self.key, 0) + 1
        return [self.store[self.key]]


class _FakeRedis:
    def __init__(self):
        self.store = {}

    def pipeline(self):
        return _FakePipeline(self.store)


def test_redis_limiter_counts_within_the_window():
    limiter = RedisLimiter(limit=2, client=_FakeRedis())
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False
    # A different client gets its own budget.
    assert limiter.allow("5.6.7.8") is True


def test_redis_failure_falls_back_to_the_local_window():
    class _Broken:
        def pipeline(self):
            raise RuntimeError("connection refused")

    limiter = RedisLimiter(limit=1, client=_Broken())
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False


def test_zero_limit_disables_limiting():
    assert SlidingWindowLimiter(limit=0).allow("any") is True
    assert RedisLimiter(limit=0, client=_FakeRedis()).allow("any") is True


def test_sliding_window_limits_and_resets():
    limiter = SlidingWindowLimiter(limit=1)
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False
    limiter.reset()
    assert limiter.allow("ip") is True
