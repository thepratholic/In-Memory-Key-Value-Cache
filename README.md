# In-Memory Key-Value Cache

A Redis-like in-memory cache built from scratch in Python — featuring a sharded architecture, custom Readers-Writer lock, REST API, FIFO eviction, and Docker support.

---

## What Problem Does This Solve?

Every time a user requests data, your app queries the database. If 1000 users request the same profile page, that's 1000 database hits — slow and expensive.

```
Without Cache:  Request → Database (every time) ❌

With Cache:     Request → Cache HIT  → instant response ✅
                Request → Cache MISS → Database → store in Cache → response
```

This project implements that cache layer — the same idea behind Redis and Memcached — built from scratch to understand how it works internally.

---

## Features

- **Sharded Architecture** — 16 independent cache shards for parallel access
- **DJB2 Hashing** — consistent key-to-shard routing using bitmask (faster than modulo)
- **Custom RWLock** — multiple threads can read simultaneously; writes are exclusive
- **FIFO Eviction** — oldest key removed automatically when a shard hits capacity
- **PUT / GET / DELETE** — core key-value operations via HTTP
- **Input Validation** — empty keys and oversized values rejected (Pydantic)
- **Dockerized** — runs anywhere with a single command

---

## Project Structure

```
.
├── server.py          # Core cache logic + FastAPI HTTP server
├── test_server.py     # Test suite
├── metrics.py         # Benchmark script
├── Dockerfile         # Container definition
├── requirements.txt   # Python dependencies
├── Makefile           # Shortcuts for common commands
└── README.md          # You are here
```

---

## Quickstart

### Run Locally

```bash
pip install -r requirements.txt
python server.py
# Server live at http://localhost:7171
```

### Run with Docker

```bash
docker build -t kvcache .
docker run -p 7171:7171 kvcache
```

### Use Make

```bash
make install      # install dependencies
make run          # start server
make test         # run tests
make docker-run   # build + run in Docker
```

---

## API Reference

### `POST /put`
```bash
curl -X POST http://localhost:7171/put \
  -H "Content-Type: application/json" \
  -d '{"key": "username", "value": "pratham"}'
```
```json
{ "status": "OK", "message": "Stored successfully." }
```

### `GET /get?key=...`
```bash
curl http://localhost:7171/get?key=username
```
```json
{ "status": "OK", "key": "username", "value": "pratham" }
```

### `DELETE /delete?key=...`
```bash
curl -X DELETE http://localhost:7171/delete?key=username
```
```json
{ "status": "OK", "message": "Key 'username' deleted." }
```

### `GET /stats`
```bash
curl http://localhost:7171/stats
```
```json
{
  "total_items": 42,
  "total_capacity": 11200000,
  "num_shards": 16,
  "used_percent": 0.0,
  "shard_sizes": [3, 2, 4, 1, 3, 2, 4, 5, 2, 3, 2, 1, 4, 2, 3, 1]
}
```

### `GET /health`
```bash
curl http://localhost:7171/health
```
```json
{ "status": "healthy" }
```

---

## Configuration

| Variable          | Default     | Description                          |
|-------------------|-------------|--------------------------------------|
| `NUM_SHARDS`      | `16`        | Number of shards (must be power of 2)|
| `MAX_SHARD_SIZE`  | `700000`    | Max keys per shard                   |
| `MAX_KV_SIZE`     | `256`       | Max length of key or value           |
| `PORT`            | `7171`      | Server port                          |
| `HOST`            | `127.0.0.1` | Host address                         |

```bash
NUM_SHARDS=8 MAX_SHARD_SIZE=1000 python server.py
```

---

## How It Works

```
HTTP Request
     │
     ▼
Input Validation (Pydantic)
     │
     ▼
DJB2 Hash(key) & mask  ──→  Shard Index (0–15)
     │
     ▼
CacheShard._lock (RWLock)
  ├── GET  → read lock  → multiple threads parallel
  └── PUT  → write lock → exclusive, others wait
     │
     ▼
Python dict (key → value)
  └── Full? → evict oldest key (FIFO)
     │
     ▼
HTTP Response
```

**Why sharding?**
Single cache = one lock = all threads queue up. With 16 shards, keys spread across 16 independent dicts — each with its own lock. Two threads touching different shards run fully in parallel.

**Why RWLock over threading.Lock()?**
Cache reads (GET) vastly outnumber writes (PUT). A normal lock blocks all readers even when no write is happening. RWLock allows concurrent reads — only writes require exclusivity.

**Why power-of-2 shards?**
`hash & (n-1)` is a bitwise AND — significantly faster than `hash % n`. Only works when n is a power of 2.

---

## Running Tests

```bash
# Terminal 1
python server.py

# Terminal 2
python test_server.py   # functional tests
python metrics.py       # latency benchmark
```

---

## Tech Stack

| Technology  | Purpose               |
|-------------|-----------------------|
| Python 3.12 | Core language         |
| FastAPI     | HTTP API framework    |
| Pydantic    | Request validation    |
| Uvicorn     | ASGI server           |
| Docker      | Containerization      |

---

## Future Improvements

- **TTL (Time-To-Live)** — keys expire automatically after N seconds
- **LRU Eviction** — evict least recently used key instead of oldest inserted
- **Persistence** — snapshot cache to disk for restart recovery
- **Consistent Hashing** — for distributed multi-node cache clusters