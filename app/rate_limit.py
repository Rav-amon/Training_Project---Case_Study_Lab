"""Лимит запросов по client_id. Счётчик живёт в памяти процесса."""

import math
import threading
import time
from collections.abc import Callable

# Окно лимита — одна минута. Само число запросов берётся из окружения.
WINDOW_SECONDS = 60

RATE_LIMITED_CODE = 'rate_limited'
RATE_LIMITED_MESSAGE = 'Слишком много запросов'
RATE_LIMIT_STATUS = 429


class ClientRateLimiter:
    """Словарь client_id → времена запросов за последнее окно."""

    def __init__(
        self,
        limit: int,
        clock: Callable[[], float] = time.monotonic,
        window_seconds: int = WINDOW_SECONDS,
    ) -> None:
        self._limit = limit
        self._clock = clock
        self._window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def hit(self, client_id: str) -> int | None:
        """Отмечает запрос. Если лимит исчерпан, возвращает секунды до повтора."""

        now = self._clock()
        with self._lock:
            recent = _within_window(
                self._hits.get(client_id, []),
                now,
                self._window_seconds,
            )
            if len(recent) >= self._limit:
                self._hits[client_id] = recent
                return _retry_after_seconds(recent, now, self._window_seconds)
            self._hits[client_id] = [*recent, now]
            return None


def _within_window(
    stamps: list[float],
    now: float,
    window_seconds: int,
) -> list[float]:
    """Оставляет только метки, которые ещё входят в окно."""

    return [stamp for stamp in stamps if now - stamp < window_seconds]


def _retry_after_seconds(
    stamps: list[float],
    now: float,
    window_seconds: int,
) -> int:
    """Сколько целых секунд ждать, пока самая ранняя метка выйдет из окна."""

    oldest = min(stamps)
    remaining = oldest + window_seconds - now
    return max(1, math.ceil(remaining))
