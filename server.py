"""
In-Memory Key-Value Cache — Sharded Version
============================================
Yeh ek Redis-jaisa in-memory cache hai jo HTTP API ke through
key-value pairs store, retrieve aur delete karta hai.

Yeh file ab SIRF HTTP layer hai — routes define karta hai aur
ShardedCache ko delegate karta hai. Koi bhi business logic
(locking, sharding, hashing) yahan nahi hai — woh sab cache/
package ke andar hai.

Architecture:
  - Cache N shards mein split hai (config se control hota hai)
  - Har shard ka apna RWLock hai — parallel access possible
  - DJB2 hash decide karta hai key kis shard mein jaayegi
  - FastAPI se HTTP endpoints expose kiye hain
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from cache import ShardedCache
from config import HOST, MAX_ITEMS_PER_SHARD, MAX_KEY_VALUE_SIZE, NUM_SHARDS, PORT
from models import PutRequest

# ─── Logging ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("kvcache")


# ─── App Bootstrap ────────────────────────────────────────────────────────

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


# ─── Routes ───────────────────────────────────────────────────────────────

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


# ─── Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("server:app", host=HOST, port=PORT, log_level="info")