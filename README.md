# DistributedKV — In-Memory Key-Value Cache Server

A Redis-inspired, high-performance in-memory key-value cache server built entirely in Python. Uses a **16-shard architecture** with a **custom Readers-Writer Lock (RWLock)** built from scratch, DJB2 hashing for O(1) shard routing, and a FastAPI + Uvicorn HTTP layer.

---

## Table of Contents

- [What is this?](#what-is-this)
- [Why does this exist?](#why-does-this-exist)
- [Architecture](#architecture)
- [How Sharding Works](#how-sharding-works)
- [How RWLock Works](#how-rwlock-works)
- [How DJB2 Hashing Works](#how-djb2-hashing-works)
- [Project Structure](#project-structure)
- [Installation & Setup](#installation--setup)
- [Running the Server](#running-the-server)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Docker](#docker)
- [Configuration](#configuration)
- [Design Decisions](#design-decisions)
- [Limitations](#limitations)

---

## What is this?

DistributedKV is an in-memory key-value store — think of it as a lightweight Redis. It stores data as simple **key → value** pairs in RAM and exposes them over HTTP so any application on the network can use it.

```
Your App  ──►  POST /put  {"key": "user:1", "value": "Alice"}  ──►  Stored in RAM ⚡
Your App  ──►  GET  /get?key=user:1                            ──►  Returns "Alice" ⚡
```

---

## Why does this exist?

Every time an app fetches data from a database, it reads from **disk** — which is slow (50–100ms per query). Under heavy traffic, databases become bottlenecks and crash.

A cache sits in front of the database and stores frequently accessed data in **RAM** — which is ~100x faster than disk.

```
Without cache:   App → Database (disk) → ~50-100ms 😴
With cache:      App → Cache (RAM)     → ~0.1ms    ⚡
```

The cache only hits the database when data is not found (a "cache miss"). This dramatically reduces database load.

---

## Architecture

```
Incoming HTTP Request
        │
        ▼
  FastAPI (routing + validation)
        │
        ▼
  ShardedCache
        │
        │  djb2_hash(key) & shard_mask
        │
   ┌────┴────────────────────────────┐
   ▼         ▼          ▼           ▼
Shard 0   Shard 1  ...  ...     Shard 15
  │
  ├── dict {"key": "value", ...}
  └── RWLock (many readers OR one writer)
```

### Key components:

| Component | What it does |
|---|---|
| `RWLock` | Custom readers-writer lock — many parallel reads, exclusive writes |
| `CacheShard` | One independent bucket — has its own dict and its own RWLock |
| `djb2_hash` | Converts a key string into a shard index number |
| `ShardedCache` | Manages all 16 shards — routes each key to the correct shard |
| `FastAPI` | HTTP framework — defines /put, /get, /delete, /health, /stats routes |
| `Uvicorn` | ASGI server — actually listens on the port and handles connections |
| `Pydantic` | Validates incoming request data automatically |

---

## How Sharding Works

Instead of one big dictionary with one lock (which becomes a bottleneck under concurrent writes), the cache is split into **16 independent shards**:

```
cache = {}           ← BAD:  one lock, everyone waits

shard[0]  = {}  🔒  ← GOOD: 16 locks, different keys work in parallel
shard[1]  = {}  🔒
...
shard[15] = {}  🔒
```

When a request comes in for key `"user:1"`:
1. DJB2 hash converts `"user:1"` to a number, e.g. `28471`
2. Bitmask: `28471 & 15 = 7` → goes to Shard 7
3. Only Shard 7's lock is acquired — all other shards are free

This means 16 write operations to different keys can happen **completely in parallel**.

### Why power of 2 for shard count?

With 16 shards, the bitmask is `15` (binary: `0000 1111`).

```python
shard_index = hash & 15   # bitmask — O(1), very fast
# vs
shard_index = hash % 16   # modulo — slightly slower
```

Both give the same result (0–15), but bitwise AND is faster than modulo on every CPU.

---

## How RWLock Works

A standard `threading.Lock()` blocks everyone — even readers — which is wasteful since multiple readers can safely read at the same time without conflict.

**RWLock rules:**
- Many threads can **read simultaneously** ✅
- Only **one thread can write** at a time ✅
- While writing, **no readers allowed** ✅

```python
# Many threads can do this at the same time:
with lock.read():
    return self._items.get(key)

# Only one thread at a time, blocks all readers while active:
with lock.write():
    self._items[key] = value
```

This is critical for cache performance because **reads are far more frequent than writes** in real-world usage.

The RWLock is built from scratch using:
- `threading.Lock()` — basic mutual exclusion
- `threading.Condition` — allows threads to wait for a condition and be notified when it changes
- A `_readers` counter — tracks how many readers are currently active

---

## How DJB2 Hashing Works

DJB2 is a simple, fast string hash function invented by Daniel Bernstein. It converts any string into a consistent 64-bit integer:

```python
def djb2_hash(s: str) -> int:
    h = 5381                                        # magic seed value
    for ch in s.encode():                           # iterate over each byte
        h = ((h << 5) + h + ch)                     # h = h * 33 + ch
        & 0xFFFF_FFFF_FFFF_FFFF                     # keep within 64 bits
    return h
```

`h * 33` is done as `(h << 5) + h` — bit shift left by 5 equals multiply by 32, plus h equals multiply by 33. Bit operations are faster than multiplication on the CPU.

**Key property:** Same input → always same output. This guarantees a key always routes to the same shard.

---

## Project Structure

```
kv-cache/
├── server.py          # Main application — all logic lives here
├── test_server.py     # Unit tests — covers all components and endpoints
├── requirements.txt   # Python dependencies
├── Dockerfile         # Multi-stage Docker build
├── Makefile           # Developer commands
└── README.md          # This file
```

### Inside `server.py`:

```
server.py
├── Imports & Config       — libraries and environment variable settings
├── RWLock                 — custom readers-writer lock (threading primitives)
├── CacheShard             — single shard: dict + RWLock + eviction logic
├── djb2_hash()            — key → shard number
├── ShardedCache           — manages 16 shards, routes keys
├── PutRequest             — Pydantic model for request validation
├── lifespan()             — server startup/shutdown logic
├── app = FastAPI(...)     — app instance
└── Routes                 — /health, /put, /get, /delete, /stats
```

---

## Installation & Setup

### Prerequisites
- Python 3.10 or higher
- pip

### Steps

```bash
# 1. Clone or download the project
cd kv-cache

# 2. Create a virtual environment
python -m venv venv

# 3. Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

## Running the Server

```bash
uvicorn server:app --host 0.0.0.0 --port 7171 --log-level info
```

Expected output:
```
INFO: Started server process
INFO: ShardedCache initialised — 16 shards, 700000 items/shard max
INFO: UltraFastKVCache ready on 0.0.0.0:7171
INFO: Uvicorn running on http://0.0.0.0:7171
```

### Interactive UI (Swagger)

Open in browser:
```
http://localhost:7171/docs
```

FastAPI automatically generates this UI — you can test all endpoints here without writing any code.

---

## API Reference

### `GET /health`
Check if the server is running.

**Request:**
```bash
curl http://localhost:7171/health
```

**Response:**
```json
{"status": "healthy"}
```

---

### `POST /put`
Store a key-value pair. If key already exists, it gets overwritten.

**Request:**
```bash
curl -X POST http://localhost:7171/put \
  -H "Content-Type: application/json" \
  -d '{"key": "user:1", "value": "Alice"}'
```

**Response:**
```json
{"status": "OK", "message": "Key inserted/updated successfully."}
```

**Validation rules:**
- `key` — required, max 256 characters, cannot be empty
- `value` — required, max 256 characters

---

### `GET /get`
Retrieve a value by key.

**Request:**
```bash
curl "http://localhost:7171/get?key=user:1"
```

**Response (found):**
```json
{"status": "OK", "key": "user:1", "value": "Alice"}
```

**Response (not found):**
```json
{"status": "ERROR", "message": "Key not found."}
```
HTTP status: `404`

---

### `DELETE /delete`
Delete a key-value pair.

**Request:**
```bash
curl -X DELETE "http://localhost:7171/delete?key=user:1"
```

**Response (deleted):**
```json
{"status": "OK", "message": "Key 'user:1' deleted."}
```

**Response (not found):**
```json
{"status": "ERROR", "message": "Key not found."}
```
HTTP status: `404`

---

### `GET /stats`
See how many items are stored in each shard.

**Request:**
```bash
curl http://localhost:7171/stats
```

**Response:**
```json
{
  "total_items": 2,
  "num_shards": 16,
  "shard_sizes": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]
}
```

This shows how DJB2 distributes keys across shards.

---

## Testing

Run all unit tests:

```bash
pytest test_server.py -v
```

### What is tested:

| Test Class | What it covers |
|---|---|
| `TestDjb2Hash` | Hash determinism, different keys, empty string, non-negative output |
| `TestCacheShard` | put/get, missing key, update, eviction when full, delete, size tracking |
| `TestShardedCache` | Basic operations, overwrite, delete, multiple keys, stats |
| `TestHealthEndpoint` | `/health` returns 200 |
| `TestPutEndpoint` | Success, empty key, key too long, value too long, missing fields |
| `TestGetEndpoint` | Existing key, missing key, no key param |
| `TestDeleteEndpoint` | Delete existing, delete missing |
| `TestStatsEndpoint` | Returns expected fields |

---

## Docker

### Build the image:
```bash
docker build -t kv-cache-python:latest .
```

### Run the container:
```bash
docker run -d \
  --name kv-cache-python \
  -p 7171:7171 \
  --ulimit nofile=1048576:1048576 \
  --restart=unless-stopped \
  kv-cache-python:latest
```

`--ulimit nofile=1048576:1048576` — raises the OS limit on open file descriptors to 1 million. Each TCP connection uses one file descriptor, so this allows the server to handle a very large number of simultaneous connections.

### Stop the container:
```bash
docker stop kv-cache-python && docker rm kv-cache-python
```

### Dockerfile explained:
The Dockerfile uses a **multi-stage build**:
- **Stage 1 (builder):** Installs all dependencies
- **Stage 2 (runtime):** Copies only what's needed — no build tools, smaller final image
- Runs as a **non-root user** for security

---

## Configuration

All settings can be changed via environment variables — no code changes needed:

| Variable | Default | Description |
|---|---|---|
| `NUM_SHARDS` | `16` | Number of cache shards (auto-rounded to power of 2) |
| `MAX_SHARD_SIZE` | `700000` | Max items per shard before eviction kicks in |
| `MAX_KV_SIZE` | `256` | Max byte length allowed for keys and values |
| `PORT` | `7171` | HTTP port the server listens on |
| `HOST` | `0.0.0.0` | Network interface to bind to |

### Example — run with custom settings:
```bash
NUM_SHARDS=32 MAX_SHARD_SIZE=100000 uvicorn server:app --port 7171
```

---

## Design Decisions

### Why not just use Redis?
This project is a from-scratch implementation to understand what Redis actually does internally — sharding, locking, hashing, HTTP serving. Building it yourself is the best way to truly understand it.

### Why DJB2 and not MD5/SHA?
MD5 and SHA are cryptographic hash functions — designed to be slow and secure. DJB2 is a non-cryptographic hash designed purely for speed and even distribution, which is all we need for shard routing.

### Why bitmask instead of modulo?
`hash & (n-1)` and `hash % n` produce the same result when n is a power of 2. But bitwise AND is a single CPU instruction while modulo involves division — so bitmask is faster. This is why shard count is always forced to a power of 2.

### Why build RWLock from scratch?
Python's standard library does not have a built-in RWLock. `threading.Lock` blocks everyone including readers. Building it from scratch using `threading.Condition` demonstrates understanding of concurrency primitives.

### Why 16 shards?
It is a balance — more shards means less lock contention but more memory overhead. 16 is a common default in cache implementations (Redis Cluster uses 16384 hash slots).

### Why 700K entries per shard?
Pre-setting a size cap bounds total memory usage: 16 shards × 700K entries = ~11.2M max entries. Eviction removes one arbitrary item when a shard is full — same strategy as the Go reference implementation this project is inspired by.

---

## Limitations

- **No persistence** — all data is lost when the server restarts. This is intentional (it is a cache, not a database).
- **No TTL (expiry)** — keys live forever until manually deleted or evicted. A TTL feature would be a natural next addition.
- **No authentication** — anyone who can reach the server can read/write/delete. Add an API key header for production use.
- **Single node** — data lives on one machine. True distributed caching would require consistent hashing across multiple nodes.
- **Windows limitation** — `uvloop` (faster event loop) does not support Windows. The server runs with the default asyncio event loop on Windows, which is slightly slower.
- **Eviction strategy** — current eviction removes an arbitrary key when a shard is full. LRU (Least Recently Used) eviction would be more intelligent.