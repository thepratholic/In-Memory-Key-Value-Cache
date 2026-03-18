
from fastapi.testclient import TestClient

from server import app, djb2_hash, ShardedCache, CacheShard

client = TestClient(app)


# ---------------------------------------------------------------------------
# DJB2 hash tests
# ---------------------------------------------------------------------------

class TestDjb2Hash:
    def test_deterministic(self):
        assert djb2_hash("hello") == djb2_hash("hello")

    def test_different_keys_differ(self):
        assert djb2_hash("foo") != djb2_hash("bar")

    def test_empty_string(self):
        assert djb2_hash("") == 5381   # DJB2 seed value

    def test_returns_non_negative(self):
        for key in ["abc", "xyz", "123", "!@#"]:
            assert djb2_hash(key) >= 0


# ---------------------------------------------------------------------------
# CacheShard tests
# ---------------------------------------------------------------------------

class TestCacheShard:
    def test_put_and_get(self):
        shard = CacheShard(max_items=100)
        shard.put("k1", "v1")
        assert shard.get("k1") == "v1"

    def test_get_missing_returns_none(self):
        shard = CacheShard(max_items=100)
        assert shard.get("no_such_key") is None

    def test_update_existing(self):
        shard = CacheShard(max_items=100)
        shard.put("k", "old")
        shard.put("k", "new")
        assert shard.get("k") == "new"

    def test_eviction_when_full(self):
        shard = CacheShard(max_items=3)
        shard.put("a", "1")
        shard.put("b", "2")
        shard.put("c", "3")
        # Adding one more should evict something — total stays at 3
        shard.put("d", "4")
        assert shard.size == 3

    def test_delete_existing(self):
        shard = CacheShard(max_items=100)
        shard.put("x", "y")
        assert shard.delete("x") is True
        assert shard.get("x") is None

    def test_delete_missing(self):
        shard = CacheShard(max_items=100)
        assert shard.delete("ghost") is False

    def test_size_tracking(self):
        shard = CacheShard(max_items=100)
        assert shard.size == 0
        shard.put("a", "1")
        assert shard.size == 1
        shard.put("b", "2")
        assert shard.size == 2
        shard.delete("a")
        assert shard.size == 1


# ---------------------------------------------------------------------------
# ShardedCache tests
# ---------------------------------------------------------------------------

class TestShardedCache:
    def test_basic_put_get(self):
        cache = ShardedCache(num_shards=4, max_per_shard=1000)
        cache.put("name", "Alice")
        assert cache.get("name") == "Alice"

    def test_missing_key(self):
        cache = ShardedCache(num_shards=4, max_per_shard=1000)
        assert cache.get("ghost") is None

    def test_overwrite(self):
        cache = ShardedCache(num_shards=4, max_per_shard=1000)
        cache.put("x", "1")
        cache.put("x", "2")
        assert cache.get("x") == "2"

    def test_delete(self):
        cache = ShardedCache(num_shards=4, max_per_shard=1000)
        cache.put("z", "val")
        assert cache.delete("z") is True
        assert cache.get("z") is None

    def test_multiple_keys_across_shards(self):
        cache = ShardedCache(num_shards=4, max_per_shard=1000)
        keys = [f"key:{i}" for i in range(100)]
        for k in keys:
            cache.put(k, f"val:{k}")
        for k in keys:
            assert cache.get(k) == f"val:{k}"

    def test_stats(self):
        cache = ShardedCache(num_shards=4, max_per_shard=1000)
        for i in range(10):
            cache.put(f"k{i}", f"v{i}")
        stats = cache.stats()
        assert stats["total_items"] == 10
        assert stats["num_shards"] == 4


# ---------------------------------------------------------------------------
# HTTP API tests
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestPutEndpoint:
    def test_put_success(self):
        resp = client.post("/put", json={"key": "foo", "value": "bar"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "OK"

    def test_put_empty_key_rejected(self):
        resp = client.post("/put", json={"key": "", "value": "bar"})
        assert resp.status_code == 422

    def test_put_key_too_long(self):
        resp = client.post("/put", json={"key": "x" * 300, "value": "v"})
        assert resp.status_code == 422

    def test_put_value_too_long(self):
        resp = client.post("/put", json={"key": "k", "value": "v" * 300})
        assert resp.status_code == 422

    def test_put_missing_fields(self):
        resp = client.post("/put", json={"key": "only_key"})
        assert resp.status_code == 422


class TestGetEndpoint:
    def test_get_existing_key(self):
        client.post("/put", json={"key": "mykey", "value": "myval"})
        resp = client.get("/get", params={"key": "mykey"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OK"
        assert data["key"] == "mykey"
        assert data["value"] == "myval"

    def test_get_missing_key(self):
        resp = client.get("/get", params={"key": "does_not_exist_xyz"})
        assert resp.status_code == 404
        assert resp.json()["status"] == "ERROR"

    def test_get_no_key_param(self):
        resp = client.get("/get")
        assert resp.status_code == 422


class TestDeleteEndpoint:
    def test_delete_existing(self):
        client.post("/put", json={"key": "del_me", "value": "bye"})
        resp = client.delete("/delete", params={"key": "del_me"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "OK"
        # Confirm gone
        assert client.get("/get", params={"key": "del_me"}).status_code == 404

    def test_delete_missing(self):
        resp = client.delete("/delete", params={"key": "ghost_key_xyz"})
        assert resp.status_code == 404


class TestStatsEndpoint:
    def test_stats_returns_expected_fields(self):
        resp = client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_items" in data
        assert "num_shards" in data
        assert "shard_sizes" in data
