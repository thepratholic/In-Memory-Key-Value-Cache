"""
Test Suite — In-Memory KV Cache (Sharded)
==========================================
Server pehle chalu karo:  python server.py
Phir test chalaao:        python test_server.py
"""

import requests

BASE = "http://localhost:7171"


def check(test_name: str, condition: bool):
    status = "✓ PASS" if condition else "✗ FAIL"
    print(f"  {status}  |  {test_name}")


def test_health():
    print("\n[1] Health Check")
    r = requests.get(f"{BASE}/health")
    check("Status code 200", r.status_code == 200)
    check("Returns healthy", r.json().get("status") == "healthy")


def test_put_and_get():
    print("\n[2] PUT then GET")
    r = requests.post(f"{BASE}/put", json={"key": "name", "value": "Pratham"})
    check("PUT returns 200", r.status_code == 200)
    r = requests.get(f"{BASE}/get", params={"key": "name"})
    check("GET returns 200", r.status_code == 200)
    check("Value sahi mila", r.json().get("value") == "Pratham")


def test_update_existing_key():
    print("\n[3] Update Existing Key")
    requests.post(f"{BASE}/put", json={"key": "city", "value": "Bhuj"})
    requests.post(f"{BASE}/put", json={"key": "city", "value": "Mumbai"})
    r = requests.get(f"{BASE}/get", params={"key": "city"})
    check("Value updated to Mumbai", r.json().get("value") == "Mumbai")


def test_get_missing_key():
    print("\n[4] GET Non-Existent Key")
    r = requests.get(f"{BASE}/get", params={"key": "this_key_does_not_exist"})
    check("Returns 404", r.status_code == 404)
    check("Error message present", "not found" in r.json().get("message", "").lower())


def test_delete():
    print("\n[5] DELETE Key")
    requests.post(f"{BASE}/put", json={"key": "temp", "value": "bye"})
    r = requests.delete(f"{BASE}/delete", params={"key": "temp"})
    check("DELETE returns 200", r.status_code == 200)
    r = requests.get(f"{BASE}/get", params={"key": "temp"})
    check("Key ab exist nahi karta", r.status_code == 404)


def test_delete_missing_key():
    print("\n[6] DELETE Non-Existent Key")
    r = requests.delete(f"{BASE}/delete", params={"key": "ghost_key"})
    check("Returns 404", r.status_code == 404)


def test_empty_key_rejected():
    print("\n[7] Empty Key Validation")
    r = requests.post(f"{BASE}/put", json={"key": "", "value": "test"})
    check("Empty key rejected (422)", r.status_code == 422)


def test_oversized_key_rejected():
    print("\n[8] Oversized Key Validation")
    big_key = "x" * 300
    r = requests.post(f"{BASE}/put", json={"key": big_key, "value": "val"})
    check("Oversized key rejected (422)", r.status_code == 422)


def test_stats():
    print("\n[9] Stats Endpoint")
    r = requests.get(f"{BASE}/stats")
    check("Stats returns 200", r.status_code == 200)
    data = r.json()
    for field in ["total_items", "total_capacity", "num_shards", "shard_sizes"]:
        check(f"Field '{field}' present", field in data)
    print(f"\n     Cache Stats:")
    print(f"        Items     : {data.get('total_items')} / {data.get('total_capacity')}")
    print(f"        Shards    : {data.get('num_shards')}")
    print(f"        Used      : {data.get('used_percent')}%")


def test_shard_distribution():
    print("\n[10] Shard Distribution")
    for i in range(160):
        requests.post(f"{BASE}/put", json={"key": f"dist_key_{i}", "value": str(i)})
    data = requests.get(f"{BASE}/stats").json()
    shard_sizes = data.get("shard_sizes", [])
    non_empty_shards = sum(1 for s in shard_sizes if s > 0)
    check("Keys multiple shards mein distribute hue", non_empty_shards > 1)
    check("16 shards hain", data.get("num_shards") == 16)
    print(f"\n     Shard distribution: {shard_sizes}")


def test_eviction():
    print("\n[11] Eviction Config Check")
    data = requests.get(f"{BASE}/stats").json()
    check("Total capacity > 0", data.get("total_capacity", 0) > 0)
    print(f"\n     Total capacity: {data.get('total_capacity'):,} keys")


if __name__ == "__main__":
    print("=" * 50)
    print("  In-Memory KV Cache — Test Suite")
    print("=" * 50)
    try:
        test_health()
        test_put_and_get()
        test_update_existing_key()
        test_get_missing_key()
        test_delete()
        test_delete_missing_key()
        test_empty_key_rejected()
        test_oversized_key_rejected()
        test_stats()
        test_shard_distribution()
        test_eviction()
        print("\n" + "=" * 50)
        print("  All tests done!")
        print("=" * 50)
    except requests.exceptions.ConnectionError:
        print("\n❌ Server se connect nahi ho paya!")
        print("   Pehle server chalaao:  python server.py")