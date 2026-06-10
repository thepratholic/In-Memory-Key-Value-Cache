# In-Memory Key-Value Cache

A Redis-like in-memory cache built from scratch in Python — featuring a REST API, FIFO eviction, thread safety, and Docker support.

---

## What Problem Does This Solve?

Every time a user requests data, your app queries the database. If 1000 users request the same data, that's 1000 database hits — slow and expensive.

```
Without Cache:  Request → Database (every single time) ❌
With Cache:     Request → Cache HIT  → instant response ✅
                Request → Cache MISS → Database → store in Cache → response
```

This project implements that cache layer — the same idea behind Redis and Memcached — built from scratch to understand how it works internally.

---

## Features

- **PUT / GET / DELETE** — core key-value operations via HTTP
- **FIFO Eviction** — when cache is full, oldest key is removed automatically
- **Thread Safety** — `threading.Lock()` ensures safe concurrent access
- **Stats Endpoint** — tracks hits, misses, evictions, and hit rate %
- **Input Validation** — empty keys and oversized values are rejected
- **Dockerized** — runs anywhere with a single command

---

## Project Structure

```
.
├── server.py          # Core cache logic + FastAPI HTTP server
├── test_server.py     # Test suite (run after starting server)
├── Dockerfile         # Container definition
├── requirements.txt   # Python dependencies
├── Makefile           # Shortcuts for common commands
└── README.md          # You are here
```

---

## Quickstart

### Option 1 — Run Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server
python server.py

# 3. Server is live at http://localhost:7171
```

### Option 2 — Run with Docker

```bash
# Build the image
docker build -t kvcache .

# Run the container
docker run -p 7171:7171 kvcache
```

### Option 3 — Use Make (easiest)

```bash
make run        # start server locally
make docker-run # start with Docker
make test       # run all tests
```

---

## API Reference

### `POST /put` — Store a key-value pair

```bash
curl -X POST http://localhost:7171/put \
  -H "Content-Type: application/json" \
  -d '{"key": "username", "value": "pratham"}'
```

```json
{ "status": "OK", "message": "Stored successfully." }
```

---

### `GET /get?key=...` — Retrieve a value

```bash
curl http://localhost:7171/get?key=username
```

```json
{ "status": "OK", "key": "username", "value": "pratham" }
```

---

### `DELETE /delete?key=...` — Delete a key

```bash
curl -X DELETE http://localhost:7171/delete?key=username
```

```json
{ "status": "OK", "message": "Key 'username' deleted." }
```

---

### `GET /stats` — Cache statistics

```bash
curl http://localhost:7171/stats
```

```json
{
  "total_items": 42,
  "max_capacity": 1000,
  "used_percent": 4.2,
  "hits": 381,
  "misses": 19,
  "evictions": 0,
  "hit_rate_pct": 95.25
}
```

---

### `GET /health` — Liveness check

```bash
curl http://localhost:7171/health
```

```json
{ "status": "healthy" }
```

---

## Configuration

All settings can be overridden via environment variables — no code changes needed.

| Variable        | Default | Description                        |
|-----------------|---------|------------------------------------|
| `MAX_CACHE_SIZE` | `1000`  | Max number of keys in cache        |
| `MAX_KV_SIZE`    | `256`   | Max length of any key or value     |
| `PORT`           | `7171`  | Port the server listens on         |
| `HOST`           | `0.0.0.0` | Host address                     |

Example — run with custom config:
```bash
MAX_CACHE_SIZE=500 PORT=8080 python server.py
```

---

## Running Tests

Make sure the server is running first, then:

```bash
python test_server.py
```

Expected output:
```
==================================================
  In-Memory KV Cache — Test Suite
==================================================

[1] Health Check
  ✓ PASS  |  Status code 200
  ✓ PASS  |  Returns healthy

[2] PUT then GET
  ✓ PASS  |  PUT returns 200
  ✓ PASS  |  GET returns 200
  ✓ PASS  |  Value sahi mila
...
```

---

## How It Works — Internals

```
HTTP Request (FastAPI)
        │
        ▼
  Input Validation (Pydantic)
        │
        ▼
  threading.Lock() ──── acquired
        │
        ▼
  Python dict  ←─── actual storage
  (key → value)
        │
   Is cache full?
   YES → evict oldest key (FIFO)
   NO  → store directly
        │
        ▼
  Lock released ──── other threads can proceed
        │
        ▼
  HTTP Response
```

**Why `threading.Lock()`?**
FastAPI handles multiple requests concurrently. Without a lock, two requests could modify the dict at the same time and corrupt data. The lock ensures only one thread touches the dict at a time.

**Why FIFO eviction?**
When cache hits capacity, the oldest inserted key is removed. Simple and predictable. Production systems use LRU (Least Recently Used) — evicting the key that hasn't been accessed the longest — which is more cache-efficient but more complex to implement.

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| **Python 3.12** | Core language |
| **FastAPI** | HTTP API framework |
| **Pydantic** | Request validation |
| **Uvicorn** | ASGI server (runs FastAPI) |
| **Docker** | Containerization |

---

## Future Improvements

- **TTL (Time-To-Live)** — keys expire automatically after N seconds
- **LRU Eviction** — smarter eviction based on access recency
- **Persistence** — save cache to disk so data survives restarts
- **Sharding** — split cache across multiple nodes for horizontal scaling