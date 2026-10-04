import subprocess
import sys
import time

def run_step(script_name):
    print(f"\n>>> RUNNING {script_name}...")
    start = time.time()
    res = subprocess.run([sys.executable, script_name], capture_output=False)
    if res.returncode != 0:
        print(f"FAILED: {script_name} returned exit code {res.returncode}")
        sys.exit(res.returncode)
    print(f">>> COMPLETED {script_name} in {time.time() - start:.2f}s")

def main():
    print("=" * 70)
    print("STARTING FULL ANTIGRAVITY PIPELINE EXECUTION")
    print("=" * 70)
    
    run_step("scripts/init_duckdb.py")
    run_step("scripts/01_build_master_union.py")
    run_step("scripts/02_feature_engineering.py")
    run_step("scripts/03_train_and_backtest.py")

    print("\n" + "=" * 70)
    print("ALL ANTIGRAVITY PIPELINES EXECUTED SUCCESSFULLY WITH ZERO ERRORS!")
    print("=" * 70)

if __name__ == "__main__":
    main()
