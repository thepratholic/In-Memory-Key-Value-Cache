
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, field_validator



NUM_SHARDS = int(os.getenv("NUM_SHARDS", "16"))       # Must be power of 2
MAX_ITEMS_PER_SHARD = int(os.getenv("MAX_SHARD_SIZE", "700_000"))
MAX_KEY_VALUE_SIZE = int(os.getenv("MAX_KV_SIZE", "256"))
PORT = int(os.getenv("PORT", "7171"))
HOST = os.getenv("HOST", "0.0.0.0")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("kvcache")



class RWLock:
    """Classic readers-writer lock built on threading primitives."""

    def __init__(self) -> None:
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0

    # ---- context-manager helpers ----

    def read_acquire(self) -> None:
        with self._read_ready:
            self._readers += 1

    def read_release(self) -> None:
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def write_acquire(self) -> None:
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def write_release(self) -> None:
        self._read_ready.release()


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




class CacheShard:
    """
    A single shard of the cache.
    Stores items in a plain dict protected by an RWLock.
    When full, evicts one arbitrary key.
    """

    __slots__ = ("_items", "_count", "_max", "_lock")

    def __init__(self, max_items: int) -> None:
        self._items: dict[str, str] = {}
        self._count: int = 0
        self._max: int = max_items
        self._lock = RWLock()

    def put(self, key: str, value: str) -> None:
        with self._lock.write():
            if self._count >= self._max:
                # Evict one arbitrary key (same strategy as Go impl)
                evict_key = next(iter(self._items))
                del self._items[evict_key]
                self._count -= 1
                log.debug("Shard full — evicted key '%s'", evict_key)

            if key not in self._items:
                self._count += 1
            self._items[key] = value

    def get(self, key: str) -> Optional[str]:
        with self._lock.read():
            return self._items.get(key)

    def delete(self, key: str) -> bool:
        with self._lock.write():
            if key in self._items:
                del self._items[key]
                self._count -= 1
                return True
            return False

    @property
    def size(self) -> int:
        with self._lock.read():
            return self._count




def djb2_hash(s: str) -> int:
    h = 5381
    for ch in s.encode():
        h = ((h << 5) + h + ch) & 0xFFFF_FFFF_FFFF_FFFF  # keep 64-bit
    return h



class ShardedCache:
    """
    Distributes keys across N shards using DJB2 hashing.
    N is rounded up to the nearest power-of-2 so we can use bitmask routing.
    """

    def __init__(self, num_shards: int, max_per_shard: int) -> None:
        # Round up to power of 2
        power = 1
        while power < num_shards:
            power *= 2
        self._shards = [CacheShard(max_per_shard) for _ in range(power)]
        self._mask = power - 1
        log.info("ShardedCache initialised — %d shards, %d items/shard max", power, max_per_shard)

    def _shard(self, key: str) -> CacheShard:
        return self._shards[djb2_hash(key) & self._mask]

    def put(self, key: str, value: str) -> None:
        self._shard(key).put(key, value)

    def get(self, key: str) -> Optional[str]:
        return self._shard(key).get(key)

    def delete(self, key: str) -> bool:
        return self._shard(key).delete(key)

    def stats(self) -> dict:
        sizes = [s.size for s in self._shards]
        return {
            "total_items": sum(sizes),
            "num_shards": len(self._shards),
            "shard_sizes": sizes,
        }


# App bootstrap

_cache: Optional[ShardedCache] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cache
    _cache = ShardedCache(NUM_SHARDS, MAX_ITEMS_PER_SHARD)
    log.info("UltraFastKVCache ready on %s:%d", HOST, PORT)
    yield
    log.info("Shutting down.")


app = FastAPI(
    title="UltraFastKVCache",
    description="High-performance sharded in-memory key-value store",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)


# Request / Response models

class PutRequest(BaseModel):
    key: str
    value: str

    @field_validator("key", "value")
    @classmethod
    def check_size(cls, v: str) -> str:
        if len(v) > MAX_KEY_VALUE_SIZE:
            raise ValueError(f"Exceeds max size of {MAX_KEY_VALUE_SIZE} bytes")
        return v

    @field_validator("key")
    @classmethod
    def check_nonempty(cls, v: str) -> str:
        if not v:
            raise ValueError("Key must not be empty")
        return v


# Routes

@app.get("/health", response_class=ORJSONResponse)
async def health():
    """Liveness probe."""
    return {"status": "healthy"}


@app.post("/put", response_class=ORJSONResponse)
async def put(req: PutRequest):
    """Insert or update a key-value pair."""
    _cache.put(req.key, req.value)
    return {"status": "OK", "message": "Key inserted/updated successfully."}


@app.get("/get", response_class=ORJSONResponse)
async def get(key: str = Query(..., min_length=1, max_length=MAX_KEY_VALUE_SIZE)):
    """Retrieve a value by key."""
    value = _cache.get(key)
    if value is None:
        return ORJSONResponse(
            status_code=404,
            content={"status": "ERROR", "message": "Key not found."},
        )
    return {"status": "OK", "key": key, "value": value}


@app.delete("/delete", response_class=ORJSONResponse)
async def delete(key: str = Query(..., min_length=1, max_length=MAX_KEY_VALUE_SIZE)):
    """Delete a key."""
    deleted = _cache.delete(key)
    if not deleted:
        return ORJSONResponse(
            status_code=404,
            content={"status": "ERROR", "message": "Key not found."},
        )
    return {"status": "OK", "message": f"Key '{key}' deleted."}


@app.get("/stats", response_class=ORJSONResponse)
async def stats():
    """Cache statistics per shard."""
    return _cache.stats()


# Entry point


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=HOST,
        port=PORT,
        workers=os.cpu_count(),       # one worker per CPU core
        loop="uvloop",                # fastest asyncio event loop
        http="httptools",             # fastest HTTP parser
        log_level="warning",          # reduce logging overhead
        access_log=False,             # disable access log for speed
    )
