#!/usr/bin/env python3
"""Compatibility test entrypoint for Commercial Release Factory v2."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commercial_release_factory import self_test

if __name__ == "__main__":
    result = self_test()
    assert result == {
        "tests": 7,
        "state": "PASS",
        "packages": 30,
        "current_gates": 310,
        "pass": 30,
        "hold": 280,
        "legacy_aliases": 210,
        "retained_rows": 520,
    }
    print(result)
