"""Límite de frecuencia por Sesión (token bucket) para el canal de colaboración."""

import time
from collections.abc import Callable

# Pico legítimo: arrastre de nodo (~30/s, 33 ms) + cursor (~12/s, 80 ms) a la vez ≈ 43/s
# (collaboration-tuning.ts y CURSOR_BROADCAST_THROTTLE_MS en uml-editor.facade.ts).
MAX_MESSAGES_PER_SECOND = 60


class TokenBucket:
    def __init__(
        self, rate_per_second: float, burst: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._rate = rate_per_second
        self._capacity = burst
        self._clock = clock
        self._tokens = burst
        self._updated = clock()

    def allow(self) -> bool:
        now = self._clock()
        self._tokens = min(self._capacity, self._tokens + (now - self._updated) * self._rate)
        self._updated = now
        if self._tokens < 1:
            return False
        self._tokens -= 1
        return True
