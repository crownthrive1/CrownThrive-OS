#!/usr/bin/env python3
"""Run authenticated repository convergence and emit public-safe evidence only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from penta.organic.body import OrganicControlPlane, OrganicError
from penta.repository_fabric.cold import ColdSnapshotVerifier
from penta.repository_fabric.fabric import ConvergenceError, RepositoryFabric, canonical_sha256
from penta.repository_fabric.github import GitHubObservationError, GitHubRepositoryObserver


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConvergenceError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def fail_envelope(message: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "ct.penta.repository-convergence-run.v1",
        "state": "HOLD_FAIL_CLOSED",
        "error": message,
        "provider_coordinates_included": False,
        "authority_effect": "none",
    }
    result["envelope_sha256"] = canonical_sha256(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run authenticated CrownThrive repository convergence")
    parser.add_argument(
        "--policy",
        default="developers/manifests/repository-federation-control-plane.v1.json",
        type=Path,
    )
    parser.add_argument("--organic-contract", default="penta/organic/contract.v1.json", type=Path)
    parser.add_argument("--output", default="evidence/repository-convergence-result.json", type=Path)
    parser.add_argument("--emergency-journal", default="evidence/repository-emergency-journal.jsonl", type=Path)
    parser.add_argument("--organic-journal", default="evidence/repository-organic-spine.jsonl", type=Path)
    parser.add_argument("--evaluated-at")
    args = parser.parse_args()

    try:
        policy = load_object(args.policy)
        raw_bindings = os.environ.get("PENTA_REPOSITORY_BINDINGS_JSON", "")
        try:
            bindings = json.loads(raw_bindings)
        except json.JSONDecodeError:
            raise GitHubObservationError("restricted repository binding JSON is invalid") from None
        if not isinstance(bindings, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in bindings.items()
        ):
            raise GitHubObservationError("restricted repository bindings must be a string map")
        observer = GitHubRepositoryObserver(
            policy,
            token=os.environ.get("PENTA_REPOSITORY_READ_TOKEN", ""),
            restricted_bindings=bindings,
        )
        observations, collection_errors = observer.collect(observed_at=args.evaluated_at)
        cold_snapshots: dict[str, Any] = {}
        cold_verifier = None
        raw_cold = os.environ.get("PENTA_REPOSITORY_COLD_SNAPSHOTS_JSON", "")
        raw_cold_key = os.environ.get("PENTA_REPOSITORY_COLD_HMAC_KEY_B64", "")
        if raw_cold or raw_cold_key:
            if not raw_cold or not raw_cold_key:
                raise ConvergenceError("cold snapshot data and verification key must be bound together")
            try:
                parsed_cold = json.loads(raw_cold)
            except json.JSONDecodeError:
                raise ConvergenceError("cold snapshot JSON is invalid") from None
            if not isinstance(parsed_cold, dict):
                raise ConvergenceError("cold snapshots must be an object keyed by stable ID")
            cold_snapshots = parsed_cold
            try:
                cold_verifier = ColdSnapshotVerifier.from_base64(raw_cold_key)
            except ValueError as exc:
                raise ConvergenceError(str(exc)) from None
        fabric = RepositoryFabric(
            policy,
            emergency_journal=args.emergency_journal,
            observation_verifier=observer.verify_observation,
            cold_snapshot_verifier=cold_verifier,
        )
        convergence = fabric.reconcile(
            observations,
            cold_snapshots=cold_snapshots,
            evaluated_at=args.evaluated_at,
        )

        organic_projection: dict[str, Any]
        identity_fingerprint = os.environ.get("PENTA_REPOSITORY_PUBLIC_KEY_FINGERPRINT", "")
        if identity_fingerprint:
            organic = OrganicControlPlane(
                load_object(args.organic_contract), journal_path=args.organic_journal
            )
            organic_projection = fabric.project_to_organic(
                convergence,
                organic,
                identity={
                    "vault_id": "vault:ct.identity.repository-fabric",
                    "public_key_fingerprint": identity_fingerprint,
                    "key_algorithm": "externally-bound",
                },
                observed_at=convergence["evaluated_at"],
            )
        else:
            organic_projection = {
                "state": "HOLD_IDENTITY_UNBOUND",
                "reason": "PENTA_REPOSITORY_PUBLIC_KEY_FINGERPRINT is not bound",
                "authority_effect": "none",
            }

        envelope: dict[str, Any] = {
            "schema": "ct.penta.repository-convergence-run.v1",
            "state": convergence["system_state"],
            "convergence": convergence,
            "provider_collection": {
                "expected_count": convergence["expected_repository_count"],
                "observed_count": len(observations),
                "failed_stable_ids": sorted(collection_errors),
                "failure_messages": {
                    stable_id: collection_errors[stable_id] for stable_id in sorted(collection_errors)
                },
                "provider_coordinates_included": False,
            },
            "organic_projection": organic_projection,
            "provider_coordinates_included": False,
            "authority_effect": "none",
        }
        envelope["envelope_sha256"] = canonical_sha256(envelope)
        write_json(args.output, envelope)
        print(
            json.dumps(
                {
                    "state": envelope["state"],
                    "observed": len(observations),
                    "held": convergence["route_counts"]["silent_emergency"],
                    "output": str(args.output),
                },
                sort_keys=True,
            )
        )
        organic_ready = organic_projection.get("state") != "HOLD_IDENTITY_UNBOUND"
        return 0 if convergence["system_state"] == "hot_operational" and organic_ready else 78
    except (OSError, json.JSONDecodeError, ConvergenceError, OrganicError) as exc:
        envelope = fail_envelope(str(exc))
        write_json(args.output, envelope)
        print(json.dumps({"state": envelope["state"], "output": str(args.output)}, sort_keys=True))
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
