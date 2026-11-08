import threading

from app.rate_limit import RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_allows_up_to_limit_then_blocks():
    limiter = RateLimiter(3, 60, clock=FakeClock())
    assert [limiter.allow("u") for _ in range(4)] == [True, True, True, False]


def test_window_slides():
    clock = FakeClock()
    limiter = RateLimiter(2, 60, clock=clock)
    assert limiter.allow("u") and limiter.allow("u")
    assert not limiter.allow("u")
    clock.now += 61
    assert limiter.allow("u")


def test_keys_are_independent():
    limiter = RateLimiter(1, 60, clock=FakeClock())
    assert limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")


def test_retry_after():
    clock = FakeClock()
    limiter = RateLimiter(1, 60, clock=clock)
    assert limiter.retry_after("u") == 0
    limiter.allow("u")
    clock.now += 10
    assert 49 <= limiter.retry_after("u") <= 52


def test_idle_keys_are_pruned():
    clock = FakeClock()
    limiter = RateLimiter(5, 60, clock=clock)
    for i in range(999):
        limiter.allow(f"user-{i}")
    clock.now += 120
    limiter.allow("fresh") 
    assert set(limiter._events) == {"fresh"}


def test_thread_safety_never_exceeds_limit():
    limiter = RateLimiter(50, 60)
    allowed = []

    def worker():
        for _ in range(20):
            allowed.append(limiter.allow("shared"))

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(allowed) == 50