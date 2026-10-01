#!/usr/bin/env python3
"""Root convenience script to run impacted tests or module-specific tests."""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_RUNNER = REPO_ROOT / "backend" / "run_tests.py"

if __name__ == "__main__":
    if not BACKEND_RUNNER.exists():
        print(f"Error: {BACKEND_RUNNER} not found.", file=sys.stderr)
        sys.exit(1)
    
    cmd = [sys.executable, str(BACKEND_RUNNER)] + sys.argv[1:]
    exit_code = os.spawnv(os.P_WAIT, sys.executable, cmd)
    sys.exit(exit_code)
