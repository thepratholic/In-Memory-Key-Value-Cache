"""
CacheShard
==========
Cache ka ek shard — ek independent unit.

Eviction policy: CLOCK (Second-Chance Approximate LRU)
  - Fixed-size circular array of slots (jaise ek ghadi ka face)
  - Har slot ke saath ek reference bit — "recently accessed?"
  - GET sirf apne reference bit ko True karta hai (lightweight,
    read-lock ke andar safe — GIL ki wajah se atomic assignment hai)
  - PUT (eviction ke time) "hand" circularly ghumti hai, jis slot
    ka reference bit False mile, wahi evict hoti hai; True mile to
    second chance dekar (bit ko False karke) aage badh jaati hai
"""

import logging
from typing import Optional

from cache.rwlock import RWLock

log = logging.getLogger("kvcache")


class CacheShard:
    __slots__ = (
        "_slots", "_values", "_ref_bits", "_key_to_slot",
        "_free_slots", "_hand", "_count", "_max", "_lock",
    )

    def __init__(self, max_items: int) -> None:
        self._max = max_items
        self._slots: list = [None] * max_items   # clock face — slot -> key
        self._values: dict = {}                    # key -> value
        self._ref_bits: dict = {}                   # key -> bool
        self._key_to_slot: dict = {}                # key -> slot index
        self._free_slots: list = list(range(max_items - 1, -1, -1))  # stack of empty slots
        self._hand: int = 0                         # clock hand position
        self._count: int = 0
        self._lock = RWLock()

    def put(self, key: str, value: str) -> None:
        with self._lock.write():
            # Case 1: existing key — sirf value update, "fresh" mark karo
            if key in self._values:
                self._values[key] = value
                self._ref_bits[key] = True
                return

            # Case 2: khaali slot available hai — seedha bhar do
            if self._free_slots:
                idx = self._free_slots.pop()
                self._slots[idx] = key
                self._key_to_slot[key] = idx
                self._values[key] = value
                self._ref_bits[key] = True
                self._count += 1
                return

            # Case 3: shard full — clock hand se eviction dhundo
            while True:
                idx = self._hand
                candidate_key = self._slots[idx]

                if self._ref_bits[candidate_key]:
                    # Second chance do — recently used tha
                    self._ref_bits[candidate_key] = False
                    self._hand = (self._hand + 1) % self._max
                else:
                    # Evict karo — yeh victim hai
                    del self._values[candidate_key]
                    del self._ref_bits[candidate_key]
                    del self._key_to_slot[candidate_key]

                    self._slots[idx] = key
                    self._key_to_slot[key] = idx
                    self._values[key] = value
                    self._ref_bits[key] = True

                    self._hand = (self._hand + 1) % self._max
                    log.debug("Shard full — CLOCK evicted key '%s'", candidate_key)
                    return

    def get(self, key: str) -> Optional[str]:
        # Lightweight write hai (sirf ek bool flag), but pure "read"
        # semantics chahiye — RWLock ke read() se kaam chal jaata hai
        # kyunki dict assignment GIL ki wajah se atomic hai.
        with self._lock.read():
            if key not in self._values:
                return None
            self._ref_bits[key] = True
            return self._values[key]

    def delete(self, key: str) -> bool:
        with self._lock.write():
            if key not in self._values:
                return False

            idx = self._key_to_slot[key]
            del self._values[key]
            del self._ref_bits[key]
            del self._key_to_slot[key]
            self._slots[idx] = None
            self._free_slots.append(idx)
            self._count -= 1
            return True

    @property
    def size(self) -> int:
        with self._lock.read():
            return self._count

    @property
    def max_items(self) -> int:
        return self._max