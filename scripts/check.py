#!/usr/bin/env python3
"""Minimal acceptance gate for the i2ctool repository.

Runs syntax-level, unit-test and functional smoke checks without extra tooling:
1. `python -m compileall` over all Python source directories.
2. `python -m pytest`, the project's unit test suite.
3. `python test_gui.py`, the project's functional verification script.

Exits 0 only if every step passes; otherwise exits with a non-zero code.

Usage: python scripts/check.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SOURCE_DIRS = [
    PROJECT_ROOT / "i2ctool_core",
    PROJECT_ROOT / "adapters",
    PROJECT_ROOT / "ui_pyside6",
    PROJECT_ROOT / "tests",
]

TOP_LEVEL_SCRIPTS = [
    PROJECT_ROOT / "main.py",
    PROJECT_ROOT / "final_demo.py",
    PROJECT_ROOT / "run_demo.py",
    PROJECT_ROOT / "test_gui.py",
]


def run_step(name: str, cmd: list[str]) -> bool:
    print(f"\n=== [check] {name} ===")
    print(f"    $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"=== [check] {name}: FAILED (exit code {result.returncode}) ===")
        return False
    print(f"=== [check] {name}: PASSED ===")
    return True


def main() -> int:
    compile_targets = [str(p) for p in SOURCE_DIRS if p.exists()]
    compile_targets += [str(p) for p in TOP_LEVEL_SCRIPTS if p.exists()]

    steps = [
        (
            "Syntax check (python -m compileall)",
            [sys.executable, "-m", "compileall", "-q", *compile_targets],
        ),
        (
            "Unit tests (pytest)",
            [sys.executable, "-m", "pytest", "-q"],
        ),
        (
            "Functional smoke test (test_gui.py)",
            [sys.executable, str(PROJECT_ROOT / "test_gui.py")],
        ),
    ]

    failed = False
    for name, cmd in steps:
        if not run_step(name, cmd):
            failed = True
            break  # stop at the first failing step

    if failed:
        print("\n=== [check] GATE FAILED ===")
        return 1
    print("\n=== [check] ALL CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
