import time
from collections import deque

def measure_ring_buffer_latency(n: int = 50000):
    buf = deque(maxlen=20000)
    latencies = []
    for i in range(n):
        t0 = time.perf_counter_ns()
        buf.append({"id": i, "price": 100.0 + (i % 10), "qty": 10})
        t1 = time.perf_counter_ns()
        latencies.append(t1 - t0)
    
    avg_ns = sum(latencies) / len(latencies)
    print(f"Deque Insertion Latency: {avg_ns:.1f} ns/op ({1e9/avg_ns:,.0f} ops/sec)")
    return avg_ns

if __name__ == '__main__':
    measure_ring_buffer_latency()
