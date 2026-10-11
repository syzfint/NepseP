#!/usr/bin/env python3
"""
scripts/git_sync.py

One-Command GitHub Sync & Contribution Logger for SYZ-FINT
==========================================================
Automatically stages, verifies author credentials (SYZ-FINT <syzfint@gmail.com>),
commits, and pushes to origin/master so your GitHub contribution graph stays green.

Usage:
    python scripts/git_sync.py "feat: update feature calculation"
    python scripts/git_sync.py
"""

import sys
import subprocess
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

AUTHOR_NAME = "SYZ-FINT"
AUTHOR_EMAIL = "syzfint@gmail.com"

def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True)

def main():
    print("=" * 70)
    print("  SYZ-FINT GITHUB CONTRIBUTION & SYNC ENGINE")
    print("=" * 70)

    # 1. Enforce git config
    run_cmd(["git", "config", "user.name", AUTHOR_NAME])
    run_cmd(["git", "config", "user.email", AUTHOR_EMAIL])

    # 2. Check status
    status = run_cmd(["git", "status", "--porcelain"])
    if not status.stdout.strip():
        print("  [OK] Working tree is clean. No unstaged changes.")
        # Push any pending commits
        print("  [*] Checking for unpushed commits...")
        push_res = run_cmd(["git", "push", "origin", "master"])
        if push_res.returncode == 0:
            print("  [OK] Repository is up to date with origin/master.")
        else:
            print(f"  Note: {push_res.stderr.strip()}")
        return

    # 3. Determine commit message
    if len(sys.argv) > 1:
        commit_msg = " ".join(sys.argv[1:])
    else:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        commit_msg = f"chore(sync): automated progress sync [{now_str}]"

    # 4. Stage changes
    print("  [*] Staging changes...")
    run_cmd(["git", "add", "-A"])

    # 5. Commit with enforced author
    import os
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = AUTHOR_NAME
    env["GIT_AUTHOR_EMAIL"] = AUTHOR_EMAIL
    env["GIT_COMMITTER_NAME"] = AUTHOR_NAME
    env["GIT_COMMITTER_EMAIL"] = AUTHOR_EMAIL

    commit_res = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=str(BASE_DIR),
        env=env,
        capture_output=True,
        text=True
    )

    if commit_res.returncode != 0:
        print(f"  Commit error: {commit_res.stderr.strip()}")
        return

    commit_hash = run_cmd(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    print(f"  [OK] Created commit [{commit_hash}]: {commit_msg}")
    print(f"       Author: {AUTHOR_NAME} <{AUTHOR_EMAIL}>")

    # 6. Push to origin
    print(f"  [*] Pushing commit [{commit_hash}] to origin/master...")
    push_res = run_cmd(["git", "push", "origin", "master"])
    if push_res.returncode == 0:
        print("  [OK] Successfully pushed to origin/master!")
        print(f"  [+] Green square registered on https://github.com/{AUTHOR_NAME.lower()}!")
    else:
        print(f"  Push warning: {push_res.stderr.strip()}")

    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
