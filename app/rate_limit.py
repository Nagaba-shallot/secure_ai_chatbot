import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float, clock=time.monotonic):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._events = {}
        self._lock = threading.Lock()
        self._calls = 0

    def allow(self, client_id: str) -> bool:
        now = self._clock()
        with self._lock:
            events = self._events.setdefault(client_id, deque())
            self._evict(events, now)
            if len(events) >= self.max_requests:
                return False
            events.append(now)
            self._calls += 1
            if self._calls % 1000 == 0:
                self._prune(now)
            return True

    def retry_after(self, key: str) -> int:
        now = self._clock()
        with self._lock:
            events = self._events.get(key)
            if not events:
                return 0
            self._evict(events, now)
            if len(events) < self.max_requests:
                return 0
            return max(1, int(events[0] + self.window_seconds - now) + 1)

    def _evict(self, events, now):
        cutoff = now - self.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()

    def _prune(self, now):
        for key in list(self._events):
            self._evict(self._events[key], now)
            if not self._events[key]:
                del self._events[key]