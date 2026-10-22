import math

def verify_cscv_combinations(s: int = 16):
    n = s // 2
    combinations = math.comb(s, n)
    assert combinations == 12870, f"Expected 12870, got {combinations}"
    print(f"CSCV Matrix S={s}, N={n}: {combinations} combinations verified.")

if __name__ == '__main__':
    verify_cscv_combinations()
