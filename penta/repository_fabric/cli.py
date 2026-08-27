#!/usr/bin/env python3
"""Command-line interface for offline/provider-produced repository evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from penta.organic.body import OrganicControlPlane

from .fabric import ConvergenceError, RepositoryFabric


def _load(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConvergenceError(f"JSON root must be an object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile the CrownThrive repository fabric")
    parser.add_argument("--policy", default="developers/manifests/repository-federation-control-plane.v1.json")
    parser.add_argument("--observations", required=True)
    parser.add_argument("--cold-snapshots")
    parser.add_argument("--evaluated-at")
    parser.add_argument("--emergency-journal")
    parser.add_argument("--organic-contract", default="penta/organic/contract.v1.json")
    parser.add_argument("--organic-journal")
    parser.add_argument("--command-center-output")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        policy = _load(args.policy)
        observations = _load(args.observations)
        cold = _load(args.cold_snapshots) if args.cold_snapshots else {}
        fabric = RepositoryFabric(
            policy,
            emergency_journal=Path(args.emergency_journal) if args.emergency_journal else None,
        )
        result = fabric.reconcile(
            observations,
            cold_snapshots=cold,
            evaluated_at=args.evaluated_at,
        )
        if args.command_center_output:
            organic = OrganicControlPlane(
                _load(args.organic_contract),
                journal_path=Path(args.organic_journal) if args.organic_journal else None,
            )
            identity = {
                "vault_id": "vault:ct.identity.repository-fabric",
                "public_key_fingerprint": "sha256:" + "1" * 64,
                "key_algorithm": "external",
            }
            projection = fabric.project_to_organic(
                result,
                organic,
                identity=identity,
                observed_at=result["evaluated_at"],
            )
            Path(args.command_center_output).write_text(
                json.dumps(projection, indent=2, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            Path(args.output).write_text(encoded, encoding="utf-8")
        else:
            print(encoded, end="")
        return 0 if result["system_state"] != "hold_emergency" else 2
    except (OSError, json.JSONDecodeError, ConvergenceError) as exc:
        print(json.dumps({"ok": False, "state": "hold_fail_closed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
