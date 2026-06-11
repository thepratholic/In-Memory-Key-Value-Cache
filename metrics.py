import requests, time, statistics

BASE = "http://localhost:7171"
latencies = []

for i in range(200):
    requests.post(f"{BASE}/put", json={"key": f"key_{i}", "value": f"value_{i}"})

for i in range(100):
    start = time.perf_counter()
    requests.get(f"{BASE}/get", params={"key": f"key_{i}"})
    latencies.append((time.perf_counter() - start) * 1000)

stats = requests.get(f"{BASE}/stats").json()

print("=== METRICS ===")
print(f"Avg GET latency  : {statistics.mean(latencies):.2f} ms")
print(f"Min GET latency  : {min(latencies):.2f} ms")
print(f"Max GET latency  : {max(latencies):.2f} ms")
print(f"P95 latency      : {sorted(latencies)[94]:.2f} ms")
print(f"Total items      : {stats['total_items']}")
print(f"Hit rate         : {stats['hit_rate_pct']}%")
print(f"Evictions        : {stats['evictions']}")