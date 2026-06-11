"""
In-Memory Key-Value Cache — Sharded Version
============================================
Yeh ek Redis-jaisa in-memory cache hai jo HTTP API ke through
key-value pairs store, retrieve aur delete karta hai.

Architecture:
  - Cache 16 shards mein split hai (16 alag dicts)
  - Har shard ka apna RWLock hai — parallel access possible
  - DJB2 hash decide karta hai key kis shard mein jaayegi
  - FastAPI se HTTP endpoints expose kiye hain
"""

import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator


# ─── Config ───────────────────────────────────────────────────────────────────
# Yeh values environment variables se aati hain.
# Agar env var set nahi hai toh default value use hogi.

NUM_SHARDS          = int(os.getenv("NUM_SHARDS", "16"))        # kitne shards — power of 2
MAX_ITEMS_PER_SHARD = int(os.getenv("MAX_SHARD_SIZE", "700000")) # ek shard mein max keys
MAX_KEY_VALUE_SIZE  = int(os.getenv("MAX_KV_SIZE", "256"))       # key/value max length
PORT                = int(os.getenv("PORT", "7171"))
HOST                = os.getenv("HOST", "127.0.0.1")


# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("kvcache")


# ─── RWLock ───────────────────────────────────────────────────────────────────

class RWLock:
    """
    Readers-Writer Lock — standard threading.Lock() se smarter.

    Problem with normal Lock:
      GET request aaye → lock lo → value padho → lock chodo
      Agar 100 GET ek saath aayein, sab queue mein wait karenge.
      Yeh bekar hai — sirf padhna toh safe hai parallel mein.

    RWLock ka solution:
      READ  → multiple threads ek saath padh sakte hain (no blocking)
      WRITE → sirf ek thread likhega, baaki sab wait karenge

    Cache mein GET (read) bahut zyada hoti hain vs PUT (write),
    isliye RWLock se performance kaafi better hoti hai.

    Internals:
      _readers   → kitne threads abhi padh rahe hain
      _read_ready → Condition object — write thread yahan wait karta hai
                    jab tak readers 0 na ho jaayein
    """

    def __init__(self) -> None:
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0

    def read_acquire(self) -> None:
        """Read lock lo — reader count badhao."""
        with self._read_ready:
            self._readers += 1

    def read_release(self) -> None:
        """Read lock chodo — reader count ghataao, writer ko notify karo."""
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()  # writer ab aage badh sakta hai

    def write_acquire(self) -> None:
        """Write lock lo — sare readers khatam hone ka wait karo."""
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()  # readers hain — wait karo

    def write_release(self) -> None:
        """Write lock chodo."""
        self._read_ready.release()

    # ── Context managers — `with lock.read():` syntax ke liye ─────────────────

    class _ReadCtx:
        def __init__(self, lock: "RWLock") -> None:
            self._lock = lock
        def __enter__(self):
            self._lock.read_acquire()
            return self
        def __exit__(self, *_):
            self._lock.read_release()

    class _WriteCtx:
        def __init__(self, lock: "RWLock") -> None:
            self._lock = lock
        def __enter__(self):
            self._lock.write_acquire()
            return self
        def __exit__(self, *_):
            self._lock.write_release()

    def read(self) -> "_ReadCtx":
        return self._ReadCtx(self)

    def write(self) -> "_WriteCtx":
        return self._WriteCtx(self)


# ─── CacheShard ───────────────────────────────────────────────────────────────

class CacheShard:
    """
    Cache ka ek shard — ek independent unit.

    Total cache = 16 CacheShard objects.
    Har shard:
      - apna dict rakhta hai (actual storage)
      - apna RWLock rakhta hai (independent locking)

    Benefit: Jab key_1 shard_3 mein hai aur key_2 shard_7 mein,
    dono operations ek saath chal sakte hain — alag alag locks!
    Single cache hoti toh ek lock sab pe wait karta.
    """

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
                # next(iter(dict)) → dict ka pehla key, O(1) time
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


# ─── DJB2 Hash ────────────────────────────────────────────────────────────────

def djb2_hash(s: str) -> int:
    """
    DJB2 — ek fast string hashing algorithm.
    Daniel J. Bernstein ne banaya tha, isliye DJB2.

    Kaam kaise karta hai:
      h = 5381  (magic seed — experimentally chosen, good distribution)
      har character ke liye:
          h = h * 33 + char_code
          (h << 5) + h  yahi h*33 hai, but bitwise shift se faster

    Result: same string → hamesha same number (deterministic)
    Alag strings → mostly alag numbers (good distribution)

    & 0xFFFF_FFFF_FFFF_FFFF → 64-bit mein rakhta hai (overflow nahi)
    """
    h = 5381
    for ch in s.encode():
        h = ((h << 5) + h + ch) & 0xFFFF_FFFF_FFFF_FFFF
    return h


# ─── ShardedCache ─────────────────────────────────────────────────────────────

class ShardedCache:
    """
    Main cache — 16 CacheShard objects ka collection.

    Routing kaise hota hai:
      1. Key ka DJB2 hash nikalo → bada number
      2. hash & mask → shard index
         mask = num_shards - 1 = 15 = 0b1111
         Bitwise AND last 4 bits rakhta hai → 0 to 15 → shard index

    Power of 2 kyun zaroori hai:
      Agar shards = 16 → mask = 15 → hash & 15  (FAST bitwise)
      Agar shards = 10 → mask kaam nahi karta → hash % 10 (SLOW modulo)
      Bitwise AND CPU pe modulo se ~10x faster hota hai.

    Same key → same hash → same shard (hamesha consistent routing)
    """

    def __init__(self, num_shards: int, max_per_shard: int) -> None:
        # Nearest power of 2 tak round up karo
        power = 1
        while power < num_shards:
            power *= 2

        self._shards = [CacheShard(max_per_shard) for _ in range(power)]
        self._mask = power - 1   # bitmask for fast routing
        log.info(
            "ShardedCache ready — %d shards × %d items/shard = %d total capacity",
            power, max_per_shard, power * max_per_shard
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
        total_capacity = len(self._shards) * self._shards[0]._max
        return {
            "total_items"    : sum(sizes),
            "total_capacity" : total_capacity,
            "num_shards"     : len(self._shards),
            "used_percent"   : round(sum(sizes) / total_capacity * 100, 2),
            "shard_sizes"    : sizes,   # per-shard breakdown
        }


# ─── App Bootstrap ────────────────────────────────────────────────────────────

_cache: Optional[ShardedCache] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server start pe cache banao, shutdown pe cleanup."""
    global _cache
    _cache = ShardedCache(NUM_SHARDS, MAX_ITEMS_PER_SHARD)
    log.info("Server ready on http://%s:%d", HOST, PORT)
    yield
    log.info("Shutting down.")


app = FastAPI(
    title="In-Memory KV Cache",
    description="High-performance sharded in-memory key-value store",
    version="3.0.0",
    lifespan=lifespan,
)


# ─── Request Model ────────────────────────────────────────────────────────────

class PutRequest(BaseModel):
    """PUT endpoint ke liye incoming JSON — Pydantic automatically validate karta hai."""
    key: str
    value: str

    @field_validator("key", "value")
    @classmethod
    def check_size(cls, v: str) -> str:
        if len(v) > MAX_KEY_VALUE_SIZE:
            raise ValueError(f"Must be <= {MAX_KEY_VALUE_SIZE} characters")
        return v

    @field_validator("key")
    @classmethod
    def check_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Key cannot be empty")
        return v


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Liveness probe — server zinda hai ya nahi."""
    return {"status": "healthy"}


@app.post("/put")
async def put(req: PutRequest):
    """Key-value pair store karo."""
    _cache.put(req.key, req.value)
    return {"status": "OK", "message": "Stored successfully."}


@app.get("/get")
async def get(key: str = Query(..., min_length=1, max_length=MAX_KEY_VALUE_SIZE)):
    """Key se value nikalo."""
    value = _cache.get(key)
    if value is None:
        return JSONResponse(
            status_code=404,
            content={"status": "ERROR", "message": f"Key '{key}' not found."},
        )
    return {"status": "OK", "key": key, "value": value}


@app.delete("/delete")
async def delete(key: str = Query(..., min_length=1, max_length=MAX_KEY_VALUE_SIZE)):
    """Key delete karo."""
    deleted = _cache.delete(key)
    if not deleted:
        return JSONResponse(
            status_code=404,
            content={"status": "ERROR", "message": f"Key '{key}' not found."},
        )
    return {"status": "OK", "message": f"Key '{key}' deleted."}


@app.get("/stats")
async def stats():
    """Cache statistics — capacity, shard distribution."""
    return _cache.stats()


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("server:app", host=HOST, port=PORT, log_level="info")