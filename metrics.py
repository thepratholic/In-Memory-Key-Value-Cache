"""
Benchmark — In-Memory KV Cache (Sharded)
=========================================
Server pehle chalu karo:  python server.py
Phir chalaao:             python metrics.py
"""

import requests
import time
import statistics

BASE = "http://localhost:7171"

print("\n=== IN-MEMORY KV CACHE — BENCHMARK ===\n")

print("Step 1: Filling cache with 500 keys...")
for i in range(500):
    requests.post(f"{BASE}/put", json={"key": f"key_{i}", "value": f"value_{i}"})
print("        Done.\n")

print("Step 2: Reading 100 existing keys (HITs)...")
hit_latencies = []
for i in range(100):
    start = time.perf_counter()
    requests.get(f"{BASE}/get", params={"key": f"key_{i}"})
    hit_latencies.append((time.perf_counter() - start) * 1000)
print("        Done.\n")

print("Step 3: Reading 50 non-existent keys (MISSes)...")
for i in range(50):
    requests.get(f"{BASE}/get", params={"key": f"ghost_{i}"})
print("        Done.\n")

print("Step 4: Deleting 20 keys...")
for i in range(20):
    requests.delete(f"{BASE}/delete", params={"key": f"key_{i}"})
print("        Done.\n")

stats = requests.get(f"{BASE}/stats").json()

print("=" * 45)
print("  RESULTS")
print("=" * 45)
print(f"\n  Cache")
print(f"    Total items   : {stats['total_items']} / {stats['total_capacity']:,}")
print(f"    Shards        : {stats['num_shards']}")
print(f"    Used          : {stats['used_percent']}%")
print(f"    Shard sizes   : {stats['shard_sizes']}")

print(f"\n  GET Latency (100 requests)")
print(f"    Avg           : {statistics.mean(hit_latencies):.2f} ms")
print(f"    Min           : {min(hit_latencies):.2f} ms")
print(f"    Max           : {max(hit_latencies):.2f} ms")
print(f"    P95           : {sorted(hit_latencies)[94]:.2f} ms")

print("\n" + "=" * 45)