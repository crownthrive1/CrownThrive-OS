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


def cycle(
    registry_path: pathlib.Path,
    state_root: pathlib.Path,
    scan_roots: list[pathlib.Path],
    authority_ref: str,
    sources_path: pathlib.Path | None = None,
) -> dict:
    registry = scribe.load_registry(registry_path)
    sources = scribe.load_sources(sources_path) if sources_path and sources_path.is_file() else None
    errors = scribe.validate_registry(registry)
    if errors:
        raise ValueError("; ".join(errors))
    reconciliation = scribe.reconcile(registry)
    if reconciliation["result"] != "PASS":
        raise ValueError("semantic reconciliation failed")

    rid = run_id()
    run_dir = state_root / "runs" / rid
    products_dir = run_dir / "products"
    discovery = scribe.discover_candidates(registry, scan_roots, sources)
    products = scribe.compile_registry(registry, products_dir)
    federation = scribe.federated_index_document(registry, sources) if sources else {
        "schema_version": "1.0.0",
        "index_id": "crownthrive.pentascribe.federated-vocabulary",
        "resolved_identity_count": len(registry.get("terms", [])),
        "lookup_form_count": len(registry.get("terms", [])),
        "blocked_term_count": 0,
        "identities": [],
        "authority_note": "Federation disabled for this cycle.",
    }

    status = "PASS" if discovery["candidate_count"] == 0 else "HOLD_CANDIDATES"
    summary = {
        "schema_version": "1.1.0",
        "system": "PentaScribe",
        "run_id": rid,
        "status": status,
        "seed_term_count": reconciliation["term_count"],
        "federated_identity_count": federation["resolved_identity_count"],
        "candidate_count": discovery["candidate_count"],
        "federated_observation_count": discovery.get("federated_observation_count", 0),
        "rejected_observation_count": discovery.get("rejected_observation_count", 0),
        "mark_observation_count": len(discovery["mark_observations"]),
        "compiled_products": [path.name for path in products],
        "authority_ref": authority_ref,
        "promotion_state": "NO_AUTOMATIC_PROMOTION",
    }
    evidence.atomic_write_json(run_dir / "federated-index.json", federation)
    evidence.atomic_write_json(run_dir / "discovery.json", discovery)
    evidence.atomic_write_json(run_dir / "reconciliation.json", reconciliation)
    evidence.atomic_write_json(run_dir / "summary.json", summary)
    receipt = evidence.receipt(
        system="PentaScribe",
        operation="federate_reconcile_compile_discover",
        status=status,
        authority_ref=authority_ref,
        inputs={
            "registry": registry,
            "sources": sources or {},
            "scan_roots": [path.as_posix() for path in scan_roots],
        },
        outputs={
            "summary": summary,
            "federation": federation,
            "discovery": discovery,
            "reconciliation": reconciliation,
        },
    )
    evidence.atomic_write_json(run_dir / "receipt.json", receipt)
    evidence.atomic_write_json(state_root / "latest.json", {
        "run_id": rid,
        "status": status,
        "candidate_count": discovery["candidate_count"],
        "federated_identity_count": federation["resolved_identity_count"],
        "receipt_sha256": receipt["receipt_sha256"],
    })
    return {"run_dir": run_dir.as_posix(), "summary": summary, "receipt": receipt}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["cycle"])
    parser.add_argument("--registry", default="penta/scribe/registry.json")
    parser.add_argument("--sources", default="penta/scribe/sources.registry.json")
    parser.add_argument("--state-root", default="var/pentascribe")
    parser.add_argument("--authority-ref", default="chlom:penta.scribe:production-control-plane")
    parser.add_argument("--scan", nargs="*", default=["README.md", "docs", "data", "penta"])
    args = parser.parse_args(argv)
    try:
        result = cycle(
            pathlib.Path(args.registry),
            pathlib.Path(args.state_root),
            [pathlib.Path(item) for item in args.scan],
            args.authority_ref,
            pathlib.Path(args.sources) if args.sources else None,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
