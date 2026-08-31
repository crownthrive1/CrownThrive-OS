#!/usr/bin/env python3
"""Build an evidence-derived CrownThrive commercialization catalog."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.commercialization.catalog_core import CatalogError
from scripts.commercialization.catalog_engine import build_catalog, validate_routing
from scripts.commercialization.catalog_offers import validate_offer

__all__ = ["CatalogError", "build_catalog", "validate_offer", "validate_routing"]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--require-eligible", action="store_true")
    parser.add_argument("--require-clean-sources", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        result = build_catalog(args.repo_root, args.output, args.source_sha, args.policy)
    except CatalogError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    catalog = result["catalog"]
    counts = catalog["counts"]
    print(json.dumps(counts, sort_keys=True))
    if args.require_eligible and counts["eligible_components"] == 0:
        print("ERROR: no eligible production-certified components", file=sys.stderr)
        return 3
    if args.require_clean_sources and counts["parse_failures"] != 0:
        print("ERROR: one or more configured commercialization sources could not be admitted", file=sys.stderr)
        print(json.dumps(catalog["parse_failures"], indent=2, sort_keys=True), file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
