#!/usr/bin/env python3
"""Intelligent Modular Test Runner & Impact Analyzer.

Separates test suites by domain module and enforces the development policy:
1. Local Development Mode: Run only unit tests for the feature being developed.
2. Pre-Push Mode: Run tests strictly for modules impacted by git changes.
3. Zero Suite Pollution: Benchmarks and irrelevant modules are never executed.

Usage:
    # Run tests for modules impacted by git changes (working dir + commits vs origin/main):
    python run_tests.py --impacted

    # Run only fast unit tests for impacted modules (blazing fast, < 2s):
    python run_tests.py --impacted --unit

    # Run tests for a specific module:
    python run_tests.py --module enrichment
    python run_tests.py --module eda --unit

    # List all available modules and their test files:
    python run_tests.py --list

    # Git pre-push hook mode (used before git push):
    python run_tests.py --pre-push
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Set

# Ensure backend root is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent if BACKEND_DIR.name == "backend" else BACKEND_DIR
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tests.module_registry import MODULE_REGISTRY, find_impacted_modules, ModuleSpec


def get_git_changed_files() -> List[str]:
    """Detects modified, staged, untracked, and committed files vs origin/main."""
    changed = set()

    # 1. Unstaged, staged, untracked working directory files
    try:
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        for line in status_res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # Handle status codes and renames ('R old -> new')
            raw_path = line[2:].strip()
            if "->" in raw_path:
                raw_path = raw_path.split("->")[-1].strip()
            # Normalize path relative to REPO_ROOT
            changed.add(raw_path.replace('"', ''))
    except Exception as e:
        print(f"[Warning] git status failed: {e}", file=sys.stderr)

    # 2. Files changed in local commits vs origin/main (or main)
    for base_ref in ["origin/main...HEAD", "main...HEAD", "HEAD~1...HEAD"]:
        try:
            diff_res = subprocess.run(
                ["git", "diff", "--name-only", base_ref],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            if diff_res.returncode == 0:
                for line in diff_res.stdout.splitlines():
                    path = line.strip()
                    if path:
                        changed.add(path.replace('"', ''))
                break
        except Exception:
            continue

    return sorted(changed)


def run_pytest_command(
    test_files: List[str],
    marker_expr: str = "",
    keyword_expr: str = "",
    extra_args: List[str] = None,
    dry_run: bool = False,
) -> int:
    """Executes pytest targeting specific files and expressions."""
    venv_python = BACKEND_DIR / ".venv" / "bin" / "pytest"
    pytest_bin = str(venv_python) if venv_python.exists() else "pytest"

    cmd = [pytest_bin]

    if marker_expr:
        cmd.extend(["-m", marker_expr])

    if keyword_expr:
        cmd.extend(["-k", keyword_expr])

    if extra_args:
        cmd.extend(extra_args)

    cmd.extend(test_files)

    print(f"\n[Test Runner] Executing: {' '.join(cmd)}")
    if dry_run:
        print("[Test Runner] Dry-run enabled. Skipping process execution.")
        return 0

    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)

    result = subprocess.run(cmd, cwd=BACKEND_DIR, env=env)
    # Pytest exit code 5 means no tests were collected (e.g., filtered by -m or -k)
    if result.returncode == 5 and (marker_expr or keyword_expr):
        print(f"[Test Runner] Notice: No tests matched filter ({marker_expr or keyword_expr}).")
        return 0
    return result.returncode


def handle_list_modules():
    print("\nRegistered PulseHR-AI Test Modules:")
    print("=" * 65)
    for name, spec in MODULE_REGISTRY.items():
        print(f"\n  • Module: {name.upper()}")
        print(f"    Description: {spec.description}")
        print(f"    Pytest Marker: @pytest.mark.{spec.pytest_marker}")
        print(f"    Test Files: ({len(spec.test_files)} files)")
        for tf in spec.test_files:
            print(f"      - {tf}")
    print("\n" + "=" * 65)


def main():
    parser = argparse.ArgumentParser(
        description="Modular Impact-Driven Test Runner for PulseHR-AI."
    )
    parser.add_argument(
        "--module",
        "-m",
        type=str,
        choices=list(MODULE_REGISTRY.keys()),
        help="Run tests strictly for a single named module.",
    )
    parser.add_argument(
        "--impacted",
        "-i",
        action="store_true",
        default=False,
        help="Automatically detect git-changed files and test impacted modules only.",
    )
    parser.add_argument(
        "--unit",
        "-u",
        action="store_true",
        default=False,
        help="Run only fast unit tests (in-memory, <0.1s per test, no DB/network).",
    )
    parser.add_argument(
        "--pre-push",
        action="store_true",
        default=False,
        help="Pre-push verification hook: tests impacted modules and guards git push.",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        default=False,
        help="List all registered test modules and their test targets.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print planned pytest commands without running them.",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        default=False,
        help="Dangerously run the entire test suite (NOT recommended).",
    )

    parser.add_argument(
        "--install-hook",
        action="store_true",
        default=False,
        help="Install git pre-push hook to automatically run impacted module tests before pushing.",
    )

    args, unknown = parser.parse_known_args()

    if args.install_hook:
        hook_path = REPO_ROOT / ".git" / "hooks" / "pre-push"
        if not hook_path.parent.exists():
            print(f"[Error] Git hooks directory not found at {hook_path.parent}", file=sys.stderr)
            return 1
        hook_content = (
            "#!/bin/sh\n"
            "# Auto-generated pre-push hook for PulseHR-AI\n"
            "echo '[Git Hook] Validating impacted modules before push...'\n"
            "python3 scripts/run_impacted_tests.py --pre-push\n"
        )
        hook_path.write_text(hook_content)
        hook_path.chmod(0o755)
        print(f"[Success] Installed pre-push hook to {hook_path}")
        return 0

    if args.list:
        handle_list_modules()
        return 0

    if args.force_all:
        print("[Architectural Warning] Running the complete test suite is discouraged by development policy.")
        confirm = input("Are you sure you want to run all tests? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Aborted.")
            return 0
        return run_pytest_command(["tests/"], dry_run=args.dry_run)

    # 1. Targeted single module
    if args.module:
        spec = MODULE_REGISTRY[args.module]
        print(f"\n[Test Runner] Targeted Module: {spec.name.upper()} ({spec.description})")

        marker = f"{spec.pytest_marker} and not benchmark"
        if args.unit:
            marker += " and not integration"

        kw_expr = " or ".join(spec.unit_only_keywords) if (args.unit and spec.unit_only_keywords) else ""
        return run_pytest_command(
            test_files=spec.test_files,
            marker_expr=marker,
            keyword_expr=kw_expr,
            extra_args=unknown,
            dry_run=args.dry_run,
        )

    # 2. Impacted mode (default if no specific module selected, or explicitly passed)
    changed_files = get_git_changed_files()
    impacted = find_impacted_modules(changed_files)

    print(f"\n[Impact Analyzer] Scanned {len(changed_files)} changed file(s) in repository.")

    if not impacted:
        # Check if non-backend files were modified
        backend_changes = [f for f in changed_files if f.startswith("backend/")]
        if not backend_changes:
            print("[Impact Analyzer] No backend Python modules impacted by changes. All good!")
            return 0
        print("[Impact Analyzer] Modified files did not map to a specific domain module. Defaulting to Core/Ingestion.")
        impacted = [MODULE_REGISTRY["ingestion"]]

    print(f"[Impact Analyzer] Identified {len(impacted)} impacted module(s):")
    for mod in impacted:
        print(f"  • {mod.name.upper()} ({len(mod.test_files)} test files)")

    overall_exit = 0
    for mod in impacted:
        print(f"\n--- Testing Module: {mod.name.upper()} ---")
        marker = f"{mod.pytest_marker} and not benchmark"
        if args.unit:
            marker += " and not integration"

        kw_expr = " or ".join(mod.unit_only_keywords) if (args.unit and mod.unit_only_keywords) else ""
        exit_code = run_pytest_command(
            test_files=mod.test_files,
            marker_expr=marker,
            keyword_expr=kw_expr,
            extra_args=unknown,
            dry_run=args.dry_run,
        )
        if exit_code != 0:
            overall_exit = exit_code
            print(f"[Impact Analyzer] ❌ Tests failed for module: {mod.name.upper()}")
            if args.pre_push:
                print("[Pre-Push Guard] Git push cancelled due to test failures in impacted module.")
                return overall_exit

    if overall_exit == 0:
        print(f"\n[Impact Analyzer] ✅ All impacted modules passed verification!")
    return overall_exit


if __name__ == "__main__":
    sys.exit(main())
