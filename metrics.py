import requests
import time
import statistics

BASE = "http://localhost:7171"

print("\n=== IN-MEMORY KV CACHE — BENCHMARK ===\n")

# ── Step 1: Cache fill karo (200 keys) ────────────────────────────────────────
print("Step 1: Filling cache with 200 keys...")
for i in range(200):
    requests.post(f"{BASE}/put", json={"key": f"key_{i}", "value": f"value_{i}"})
print("        Done.\n")

# ── Step 2: GET hits — keys jo exist karti hain ───────────────────────────────
print("Step 2: Reading 100 existing keys (should be HITs)...")
hit_latencies = []
for i in range(100):
    start = time.perf_counter()
    requests.get(f"{BASE}/get", params={"key": f"key_{i}"})
    hit_latencies.append((time.perf_counter() - start) * 1000)
print("        Done.\n")

# ── Step 3: GET misses — keys jo exist nahi karti ─────────────────────────────
print("Step 3: Reading 50 non-existent keys (should be MISSes)...")
for i in range(50):
    requests.get(f"{BASE}/get", params={"key": f"ghost_key_{i}"})
print("        Done.\n")

# ── Step 4: Eviction trigger — cache ko 1000 se upar bharo ───────────────────
print("Step 4: Filling cache to capacity to trigger evictions...")
for i in range(200, 1010):
    requests.post(f"{BASE}/put", json={"key": f"key_{i}", "value": f"value_{i}"})
print("        Done.\n")

# ── Step 5: Delete kuch keys ──────────────────────────────────────────────────
print("Step 5: Deleting 10 keys...")
for i in range(10):
    requests.delete(f"{BASE}/delete", params={"key": f"key_{i}"})
print("        Done.\n")

# ── Step 6: Final stats fetch ─────────────────────────────────────────────────
stats = requests.get(f"{BASE}/stats").json()

# ── Output ────────────────────────────────────────────────────────────────────
print("=" * 45)
print("  RESULTS")
print("=" * 45)

print(f"\n  Cache Size")
print(f"    Total items      : {stats['total_items']} / {stats['max_capacity']}")
print(f"    Used             : {stats['used_percent']}%")
print(f"    Evictions        : {stats['evictions']}")

print(f"\n  Hit / Miss Stats")
print(f"    Hits             : {stats['hits']}")
print(f"    Misses           : {stats['misses']}")
print(f"    Hit Rate         : {stats['hit_rate_pct']}%")

print(f"\n  GET Latency (100 requests)")
print(f"    Avg              : {statistics.mean(hit_latencies):.2f} ms")
print(f"    Min              : {min(hit_latencies):.2f} ms")
print(f"    Max              : {max(hit_latencies):.2f} ms")
print(f"    P95              : {sorted(hit_latencies)[94]:.2f} ms")

print("\n" + "=" * 45)