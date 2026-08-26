#!/usr/bin/env python3
"""Production cycle runner for PentaScribe.

This runner produces a deterministic evidence bundle for one reconciliation cycle.
It never promotes discovered terms or trademark states by itself.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


scribe = load_module("pentascribe", ROOT / "penta/scribe/pentascribe.py")
evidence = load_module("penta_evidence", ROOT / "penta/runtime/evidence.py")


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def cycle(registry_path: pathlib.Path, state_root: pathlib.Path, scan_roots: list[pathlib.Path], authority_ref: str) -> dict:
    registry = scribe.load_registry(registry_path)
    errors = scribe.validate_registry(registry)
    if errors:
        raise ValueError("; ".join(errors))
    reconciliation = scribe.reconcile(registry)
    if reconciliation["result"] != "PASS":
        raise ValueError("semantic reconciliation failed")

    rid = run_id()
    run_dir = state_root / "runs" / rid
    products_dir = run_dir / "products"
    discovery = scribe.discover_candidates(registry, scan_roots)
    products = scribe.compile_registry(registry, products_dir)

    status = "PASS" if discovery["candidate_count"] == 0 else "HOLD_CANDIDATES"
    summary = {
        "schema_version": "1.0.0",
        "system": "PentaScribe",
        "run_id": rid,
        "status": status,
        "term_count": reconciliation["term_count"],
        "candidate_count": discovery["candidate_count"],
        "mark_observation_count": len(discovery["mark_observations"]),
        "compiled_products": [p.name for p in products],
        "authority_ref": authority_ref,
        "promotion_state": "NO_AUTOMATIC_PROMOTION",
    }
    evidence.atomic_write_json(run_dir / "discovery.json", discovery)
    evidence.atomic_write_json(run_dir / "reconciliation.json", reconciliation)
    evidence.atomic_write_json(run_dir / "summary.json", summary)
    receipt = evidence.receipt(
        system="PentaScribe",
        operation="reconcile_compile_discover",
        status=status,
        authority_ref=authority_ref,
        inputs={"registry": registry, "scan_roots": [p.as_posix() for p in scan_roots]},
        outputs={"summary": summary, "discovery": discovery, "reconciliation": reconciliation},
    )
    evidence.atomic_write_json(run_dir / "receipt.json", receipt)
    evidence.atomic_write_json(state_root / "latest.json", {"run_id": rid, "status": status, "receipt_sha256": receipt["receipt_sha256"]})
    return {"run_dir": run_dir.as_posix(), "summary": summary, "receipt": receipt}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["cycle"])
    p.add_argument("--registry", default="penta/scribe/registry.json")
    p.add_argument("--state-root", default="var/pentascribe")
    p.add_argument("--authority-ref", default="chlom:penta.scribe:production-control-plane")
    p.add_argument("--scan", nargs="*", default=["README.md", "docs", "data", "penta"])
    args = p.parse_args(argv)
    try:
        result = cycle(pathlib.Path(args.registry), pathlib.Path(args.state_root), [pathlib.Path(x) for x in args.scan], args.authority_ref)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
