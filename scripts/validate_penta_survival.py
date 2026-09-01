#!/usr/bin/env python3
"""Repository entry point for deterministic Penta survival validation."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.penta_survival import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
