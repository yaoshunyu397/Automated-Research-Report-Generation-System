from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: float
    created_at: float
    hits: int = 0


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int = 600, max_size: int = 128) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._items: dict[str, CacheEntry[T]] = {}

    def get(self, key: str) -> T | None:
        now = time.time()
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            self._items.pop(key, None)
            return None
        entry.hits += 1
        return entry.value

    def set(self, key: str, value: T) -> None:
        now = time.time()
        self._items[key] = CacheEntry(
            value=value,
            expires_at=now + self.ttl_seconds,
            created_at=now,
        )
        self._evict_if_needed()

    def clear(self) -> None:
        self._items.clear()

    def stats(self) -> dict[str, int]:
        self._remove_expired()
        return {
            "size": len(self._items),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "total_hits": sum(entry.hits for entry in self._items.values()),
        }

    def _remove_expired(self) -> None:
        now = time.time()
        expired_keys = [key for key, entry in self._items.items() if entry.expires_at <= now]
        for key in expired_keys:
            self._items.pop(key, None)

    def _evict_if_needed(self) -> None:
        self._remove_expired()
        while len(self._items) > self.max_size:
            oldest_key = min(self._items, key=lambda key: self._items[key].created_at)
            self._items.pop(oldest_key, None)
