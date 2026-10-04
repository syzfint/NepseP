import subprocess
import sys

if __name__ == "__main__":
    cmd = [sys.executable, "scripts/run_all_pipelines.py"]
    subprocess.run(cmd, check=True)
