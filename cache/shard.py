"""
CacheShard
==========
Cache ka ek shard — ek independent unit.

Total cache = N CacheShard objects.
Har shard:
  - apna OrderedDict rakhta hai (actual storage + recency order)
  - apna RWLock rakhta hai (independent locking)

Benefit: Jab key_1 shard_3 mein hai aur key_2 shard_7 mein,
dono operations ek saath chal sakte hain — alag alag locks!
Single cache hoti toh ek lock sab pe wait karta.

Eviction policy: LRU (Least Recently Used)
  - OrderedDict apna insertion/access order maintain karta hai
  - move_to_end(key) se koi bhi key O(1) mein "most recent" ban jaati hai
  - popitem(last=False) se sabse "purani" (least recently used) key nikalti hai
  - Trade-off: get() ab order modify karta hai, isliye write() lock leta hai
    read() ki jagah — parallel-read benefit yahan LRU ki correctness ke
    liye trade off kiya gaya hai.
"""

import logging
from collections import OrderedDict
from typing import Optional

from cache.rwlock import RWLock

log = logging.getLogger("kvcache")


class CacheShard:
    __slots__ = ("_items", "_count", "_max", "_lock")
    # __slots__ memory optimization hai — dict ke bajaye fixed attributes

    def __init__(self, max_items: int) -> None:
        self._items: OrderedDict[str, str] = OrderedDict()  # storage + recency order
        self._count: int = 0               # kitne items hain (len() se fast)
        self._max: int = max_items         # max capacity
        self._lock = RWLock()              # is shard ka apna lock

    def put(self, key: str, value: str) -> None:
        """
        Key-value store karo is shard mein.
        Existing key ho to use "most recently used" bana do.
        Full hone par LRU eviction — sabse kam-recently-used key hata do.
        """
        with self._lock.write():
            if key in self._items:
                # Existing key update ho rahi hai — isse "fresh" mark karo
                self._items.move_to_end(key)
                self._items[key] = value
                return

            if self._count >= self._max:
                # Shard full — sabse least-recently-used key nikalo
                # popitem(last=False) -> OrderedDict ka pehla (sabse purana) item, O(1)
                evict_key, _ = self._items.popitem(last=False)
                self._count -= 1
                log.debug("Shard full — evicted key '%s' (LRU)", evict_key)

            self._items[key] = value
            self._count += 1

    def get(self, key: str) -> Optional[str]:
        """
        Value padho — access hote hi key ko "most recently used" mark karo.
        NOTE: order modify hota hai, isliye write() lock lena padta hai,
        read() nahi — yeh LRU ka trade-off hai.
        """
        with self._lock.write():
            if key not in self._items:
                return None
            self._items.move_to_end(key)   # is key ko "fresh" bana do
            return self._items[key]

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