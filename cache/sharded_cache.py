"""
ShardedCache
============
Main cache — N CacheShard objects ka collection.

Routing kaise hota hai:
  1. Key ka DJB2 hash nikalo -> bada number
  2. hash & mask -> shard index
     mask = num_shards - 1 = 15 = 0b1111
     Bitwise AND last 4 bits rakhta hai -> 0 to 15 -> shard index

Power of 2 kyun zaroori hai:
  Agar shards = 16 -> mask = 15 -> hash & 15  (FAST bitwise)
  Agar shards = 10 -> mask kaam nahi karta -> hash % 10 (SLOW modulo)
  Bitwise AND CPU pe modulo se ~10x faster hota hai.

Same key -> same hash -> same shard (hamesha consistent routing)
"""

import logging
from typing import Optional

from cache.hashing import djb2_hash
from cache.shard import CacheShard

log = logging.getLogger("kvcache")


class ShardedCache:
    def __init__(self, num_shards: int, max_per_shard: int) -> None:
        # Nearest power of 2 tak round up karo
        power = 1
        while power < num_shards:
            power *= 2

        self._shards = [CacheShard(max_per_shard) for _ in range(power)]
        self._mask = power - 1   # bitmask for fast routing
        log.info(
            "ShardedCache ready — %d shards x %d items/shard = %d total capacity",
            power, max_per_shard, power * max_per_shard,
        )

    def _shard(self, key: str) -> CacheShard:
        """Key ko sahi shard pe route karo."""
        return self._shards[djb2_hash(key) & self._mask]

    # Delegation pattern — ShardedCache khud kaam nahi karta,
    # sahi shard ko delegate karta hai

    def put(self, key: str, value: str) -> None:
        self._shard(key).put(key, value)

    def get(self, key: str) -> Optional[str]:
        return self._shard(key).get(key)

    def delete(self, key: str) -> bool:
        return self._shard(key).delete(key)

    def stats(self) -> dict:
        """Saare shards ka combined stats."""
        sizes = [s.size for s in self._shards]
        total_capacity = len(self._shards) * self._shards[0].max_items
        return {
            "total_items"    : sum(sizes),
            "total_capacity" : total_capacity,
            "num_shards"     : len(self._shards),
            "used_percent"   : round(sum(sizes) / total_capacity * 100, 2),
            "shard_sizes"    : sizes,   # per-shard breakdown
        }