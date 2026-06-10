"""
Test Suite — In-Memory KV Cache
================================
Yeh file server ko test karti hai.
Server pehle chalu karo:  python server.py
Phir test chalaao:        python test_server.py

Har test ek scenario cover karta hai — pass hua toh ✓, fail hua toh ✗.
"""

import requests

BASE = "http://localhost:7171"   # server ka address


# ─── Helper ───────────────────────────────────────────────────────────────────

def check(test_name: str, condition: bool):
    """Test result print karo — simple pass/fail."""
    status = "✓ PASS" if condition else "✗ FAIL"
    print(f"  {status}  |  {test_name}")


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_health():
    print("\n[1] Health Check")
    r = requests.get(f"{BASE}/health")
    check("Status code 200", r.status_code == 200)
    check("Returns healthy", r.json().get("status") == "healthy")


def test_put_and_get():
    print("\n[2] PUT then GET")
    # Store karo
    r = requests.post(f"{BASE}/put", json={"key": "name", "value": "Pratham"})
    check("PUT returns 200", r.status_code == 200)

    # Retrieve karo
    r = requests.get(f"{BASE}/get", params={"key": "name"})
    check("GET returns 200", r.status_code == 200)
    check("Value sahi mila", r.json().get("value") == "Pratham")


def test_update_existing_key():
    print("\n[3] Update Existing Key")
    requests.post(f"{BASE}/put", json={"key": "city", "value": "Bhuj"})
    requests.post(f"{BASE}/put", json={"key": "city", "value": "Mumbai"})  # overwrite

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

    # Ab GET karo — 404 aana chahiye
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
    big_key = "x" * 300   # 300 chars — limit 256
    r = requests.post(f"{BASE}/put", json={"key": big_key, "value": "val"})
    check("Oversized key rejected (422)", r.status_code == 422)


def test_stats():
    print("\n[9] Stats Endpoint")
    r = requests.get(f"{BASE}/stats")
    check("Stats returns 200", r.status_code == 200)

    data = r.json()
    # Yeh fields honi chahiye response mein
    for field in ["total_items", "max_capacity", "hits", "misses", "hit_rate_pct"]:
        check(f"Field '{field}' present", field in data)

    print(f"\n     📊 Cache Stats:")
    print(f"        Items     : {data.get('total_items')} / {data.get('max_capacity')}")
    print(f"        Hits      : {data.get('hits')}")
    print(f"        Misses    : {data.get('misses')}")
    print(f"        Hit Rate  : {data.get('hit_rate_pct')}%")
    print(f"        Evictions : {data.get('evictions')}")


def test_eviction():
    print("\n[10] Eviction (Cache Full)")
    # /stats se current max_capacity lo
    capacity = requests.get(f"{BASE}/stats").json().get("max_capacity", 1000)

    # Cache ko bilkul bhar do
    print(f"     Filling cache with {capacity} keys...")
    for i in range(capacity):
        requests.post(f"{BASE}/put", json={"key": f"evict_key_{i}", "value": str(i)})

    # Ek aur dalo — ab eviction honi chahiye
    requests.post(f"{BASE}/put", json={"key": "overflow_key", "value": "this triggers eviction"})

    stats = requests.get(f"{BASE}/stats").json()
    check("Evictions > 0 (eviction hua)", stats.get("evictions", 0) > 0)
    check("Cache size capacity se zyada nahi", stats.get("total_items", 0) <= capacity)


# ─── Run All Tests ────────────────────────────────────────────────────────────

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
        test_eviction()

        print("\n" + "=" * 50)
        print("  All tests done!")
        print("=" * 50)

    except requests.exceptions.ConnectionError:
        print("\n❌ Server se connect nahi ho paya!")
        print("   Pehle server chalaao:  python server.py")