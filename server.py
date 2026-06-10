"""
In-Memory Key-Value Cache
=========================
Ek simple cache server — Redis jaisa, but khud banaya hua.

Sharding NAHI hai yahan — ek single cache, ek lock, simple OOP.
FastAPI se HTTP API bana ke expose kiya hai.
"""

import logging
import os
import threading
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from contextlib import asynccontextmanager


# ─── Config (environment variables se, ya defaults) ───────────────────────────

MAX_CACHE_SIZE = int(os.getenv("MAX_CACHE_SIZE", "1000"))   # kitne keys max
MAX_KV_SIZE    = int(os.getenv("MAX_KV_SIZE", "256"))       # key/value max length
PORT           = int(os.getenv("PORT", "7171"))
HOST           = os.getenv("HOST", "0.0.0.0")


# ─── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("kvcache")


# ─── Core Cache Class ──────────────────────────────────────────────────────────

class InMemoryCache:
    """
    Ek simple in-memory key-value cache.

    Andar ek Python dict hai — wahi actual storage hai.
    threading.Lock() se protect kiya hai taaki ek saath
    do threads milke data corrupt na kar sakein.

    Jab cache full ho jaata hai (MAX_CACHE_SIZE cross ho), toh
    sabse pehla key evict (delete) kar deta hai — FIFO style.
    Yeh simple hai; production mein LRU hota hai.
    """

    def __init__(self, max_size: int) -> None:
        self._store: dict[str, str] = {}   # actual data yahan hai
        self._max_size  = max_size
        self._lock      = threading.Lock() # ek hi lock, sab operations ke liye
        self._hits      = 0                # kitni baar GET successful raha
        self._misses    = 0                # kitni baar GET fail raha (key not found)
        self._evictions = 0                # kitni baar forcefully key delete hua

        log.info("InMemoryCache ready — max %d items", max_size)

    # ── PUT ────────────────────────────────────────────────────────────────────

    def put(self, key: str, value: str) -> None:
        """
        Key-value pair store karo.
        Agar key already hai toh update ho jaayegi.
        Agar cache full hai toh ek purana key hata ke space banao.
        """
        with self._lock:                        # lock lo — ek thread ek time pe
            if key not in self._store and len(self._store) >= self._max_size:
                # Cache full hai — FIFO eviction
                # next(iter(...)) dict ka pehla key deta hai
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
                self._evictions += 1
                log.debug("Cache full — evicted key '%s'", oldest_key)

            self._store[key] = value            # store karo / update karo

    # ── GET ────────────────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[str]:
        """
        Key se value lo.
        Milgaya → value return karo + hit count badhao.
        Nahi mila → None return karo + miss count badhao.
        """
        with self._lock:
            value = self._store.get(key)        # dict.get() — None if not found
            if value is not None:
                self._hits += 1
            else:
                self._misses += 1
            return value

    # ── DELETE ─────────────────────────────────────────────────────────────────

    def delete(self, key: str) -> bool:
        """
        Key hata do.
        Tha toh True return karo, nahi tha toh False.
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    # ── STATS ──────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """
        Cache ka health check — kitna bhar gaya, hits/misses kya hain.
        Yeh production mein monitoring ke kaam aata hai.
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0.0
            return {
                "total_items"  : len(self._store),
                "max_capacity" : self._max_size,
                "used_percent" : round(len(self._store) / self._max_size * 100, 2),
                "hits"         : self._hits,
                "misses"       : self._misses,
                "evictions"    : self._evictions,
                "hit_rate_pct" : round(hit_rate, 2),
            }


# ─── FastAPI App Setup ────────────────────────────────────────────────────────

_cache: Optional[InMemoryCache] = None  # global cache object


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    App start hone pe cache banao, band hone pe cleanup karo.
    Yeh FastAPI ka lifecycle hook hai.
    """
    global _cache
    _cache = InMemoryCache(MAX_CACHE_SIZE)
    log.info("Server ready on %s:%d", HOST, PORT)
    yield                     # ← yahan app run karta hai
    log.info("Shutting down.")


app = FastAPI(
    title="In-Memory KV Cache",
    description="Simple Redis-like cache — built from scratch in Python",
    version="2.0.0",
    lifespan=lifespan,
)


# ─── Request Model ────────────────────────────────────────────────────────────

class PutRequest(BaseModel):
    """
    PUT endpoint ke liye incoming JSON ka structure.
    Pydantic automatically validate karta hai.
    """
    key: str
    value: str

    @field_validator("key", "value")
    @classmethod
    def check_size(cls, v: str) -> str:
        """Key ya value zyada badi nahi honi chahiye."""
        if len(v) > MAX_KV_SIZE:
            raise ValueError(f"Must be <= {MAX_KV_SIZE} characters")
        return v

    @field_validator("key")
    @classmethod
    def check_nonempty(cls, v: str) -> str:
        """Empty key allowed nahi hai."""
        if not v.strip():
            raise ValueError("Key cannot be empty")
        return v


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Server zinda hai ya nahi — simple liveness check."""
    return {"status": "healthy"}


@app.post("/put")
async def put(req: PutRequest):
    """
    Ek key-value pair store karo.

    Example:
        POST /put
        { "key": "name", "value": "Pratham" }
    """
    _cache.put(req.key, req.value)
    return {"status": "OK", "message": "Stored successfully."}


@app.get("/get")
async def get(key: str = Query(..., min_length=1, max_length=MAX_KV_SIZE)):
    """
    Key se value nikalo.

    Example:
        GET /get?key=name
    """
    value = _cache.get(key)
    if value is None:
        return JSONResponse(
            status_code=404,
            content={"status": "ERROR", "message": f"Key '{key}' not found."},
        )
    return {"status": "OK", "key": key, "value": value}


@app.delete("/delete")
async def delete(key: str = Query(..., min_length=1, max_length=MAX_KV_SIZE)):
    """
    Key delete karo.

    Example:
        DELETE /delete?key=name
    """
    deleted = _cache.delete(key)
    if not deleted:
        return JSONResponse(
            status_code=404,
            content={"status": "ERROR", "message": f"Key '{key}' not found."},
        )
    return {"status": "OK", "message": f"Key '{key}' deleted."}


@app.get("/stats")
async def stats():
    """
    Cache ka dashboard — kitna use ho raha hai, hit rate kya hai.

    Example:
        GET /stats
    """
    return _cache.stats()


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("server:app", host=HOST, port=PORT, log_level="info")