import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    def __init__(self, max_calls: int, period: int):
        self.max_calls = max_calls
        self.period = period
        self._calls = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            calls = self._calls[key]
            calls[:] = [t for t in calls if now - t < self.period]
            if len(calls) >= self.max_calls:
                return False
            calls.append(now)
            return True


forgot_password_limiter = RateLimiter(max_calls=5, period=300)
