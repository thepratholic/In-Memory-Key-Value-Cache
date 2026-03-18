# In-Memory-Key-Value-Cache


## Features

| Feature | Detail |
|---|---|
| **Sharded cache** | 16 shards (configurable), each protected by an RWLock |
| **DJB2 hashing** | Same algorithm as the Go reference for shard routing |
| **Fast HTTP** | FastAPI + uvicorn + uvloop + httptools + orjson |
| **Multi-core** | `workers=cpu_count()` — one worker per CPU |
| **Docker** | Multi-stage build, non-root user |

## Quick Start

```bash
# Install dependencies
make install

# Run locally (multi-worker)
make run

# Run with hot reload (dev mode)
make run-dev

# Run tests
make test

# Smoke test (server must be running)
make smoke-test
```

## API

### PUT `/put`
```bash
curl -X POST http://localhost:7171/put \
  -H "Content-Type: application/json" \
  -d '{"key": "name", "value": "Alice"}'
```

### GET `/get`
```bash
curl "http://localhost:7171/get?key=name"
```

### DELETE `/delete`
```bash
curl -X DELETE "http://localhost:7171/delete?key=name"
```

### GET `/stats`
```bash
curl "http://localhost:7171/stats"
```

### GET `/health`
```bash
curl "http://localhost:7171/health"
```

## Docker

```bash
make docker-build
make docker-up
make smoke-test
make docker-down
```

## Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `NUM_SHARDS` | `16` | Number of cache shards (rounded to power of 2) |
| `MAX_SHARD_SIZE` | `700000` | Max items per shard before eviction |
| `MAX_KV_SIZE` | `256` | Max byte length for keys and values |
| `PORT` | `7171` | HTTP port |
| `HOST` | `0.0.0.0` | Bind address |

## Architecture

```
Request
   │
   ▼
FastAPI (uvicorn + uvloop + httptools)
   │
   ▼
ShardedCache
   │  djb2_hash(key) & shard_mask
   ▼
CacheShard[N]
   │  RWLock (many readers / one writer)
   ▼
dict[str, str]  ← O(1) get/put
```
