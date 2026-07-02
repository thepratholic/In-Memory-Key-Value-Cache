"""
CacheShard
==========
Cache ka ek shard — ek independent unit.

Total cache = N CacheShard objects.
Har shard:
  - apna dict rakhta hai (actual storage)
  - apna RWLock rakhta hai (independent locking)

Benefit: Jab key_1 shard_3 mein hai aur key_2 shard_7 mein,
dono operations ek saath chal sakte hain — alag alag locks!
Single cache hoti toh ek lock sab pe wait karta.
"""

import logging
from typing import Optional

from cache.rwlock import RWLock

log = logging.getLogger("kvcache")


class CacheShard:
    __slots__ = ("_items", "_count", "_max", "_lock")
    # __slots__ memory optimization hai — dict ke bajaye fixed attributes

    def __init__(self, max_items: int) -> None:
        self._items: dict[str, str] = {}   # actual key-value storage
        self._count: int = 0               # kitne items hain (len() se fast)
        self._max: int = max_items         # max capacity
        self._lock = RWLock()              # is shard ka apna lock

    def put(self, key: str, value: str) -> None:
        """
        Key-value store karo is shard mein.
        Full hone par FIFO eviction — pehla key hata do.
        """
        with self._lock.write():
            if self._count >= self._max:
                # Shard full — pehla key nikalo (FIFO)
                # next(iter(dict)) -> dict ka pehla key, O(1) time
                evict_key = next(iter(self._items))
                del self._items[evict_key]
                self._count -= 1
                log.debug("Shard full — evicted key '%s'", evict_key)

            if key not in self._items:
                self._count += 1           # naya key hai toh count badhao
            self._items[key] = value       # insert ya update

    def get(self, key: str) -> Optional[str]:
        """Value padho — read lock use karo (parallel reads allowed)."""
        with self._lock.read():
            return self._items.get(key)    # None if not found

    def delete(self, key: str) -> bool:
        """Key hata do — True agar mila, False agar nahi tha."""
        with self._lock.write():
            if key in self._items:
                del self._items[key]
                self._count -= 1
                return True
            return False

    @property
    def size(self) -> int:
        """Shard mein kitne items hain."""
        with self._lock.read():
            return self._count

    @property
    def max_items(self) -> int:
        """Shard ki max capacity."""
        return self._max