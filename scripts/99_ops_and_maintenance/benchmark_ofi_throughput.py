import time
import numpy as np

def benchmark_ofi_calculation(iterations: int = 10000):
    weights = np.exp(-0.40 * np.arange(5))
    bids = np.random.uniform(100, 5000, (iterations, 5))
    asks = np.random.uniform(100, 5000, (iterations, 5))
    
    t0 = time.perf_counter()
    diff = bids - asks
    denom = bids + asks
    nofi = np.dot(diff, weights) / np.dot(denom, weights)
    elapsed = time.perf_counter() - t0
    
    avg_us = (elapsed / iterations) * 1e6
    print(f"OFI Vectorized Throughput: {iterations/elapsed:,.0f} ops/sec | Latency: {avg_us:.2f} us/calc")
    return avg_us

if __name__ == '__main__':
    benchmark_ofi_calculation()
