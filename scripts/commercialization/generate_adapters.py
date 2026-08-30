#!/usr/bin/env python3
"""Generate deterministic language-specific registry adapter packages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.commercialization.adapter_core import AdapterError
from scripts.commercialization.adapter_engine import generate_adapters

__all__ = ["AdapterError", "generate_adapters"]

def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        if not isinstance(catalog, Mapping):
            raise AdapterError("catalog root must be an object")
        index = generate_adapters(catalog, args.output)
    except (OSError, json.JSONDecodeError, AdapterError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"components": index["component_count"], "ecosystems": len(index["ecosystems"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
