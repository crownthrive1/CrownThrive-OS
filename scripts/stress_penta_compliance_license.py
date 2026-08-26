#!/usr/bin/env python3
"""Parallel deterministic stress gate for PentaCompliance/PentaLicense."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.penta_compliance_license import evaluate_compliance, evaluate_license_request, verify_receipt  # noqa: E402


def fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    source = "support/master-licensing-and-rights-architecture.mdx"
    obligation = {
        "obligation_id": "ct.internal.stress-license-v1", "title": "Exact license evidence",
        "source_ref": source, "source_sha256": sha256(source.encode()).hexdigest(),
        "jurisdictions": ["internal"], "scopes": ["licensing"], "owner_ref": "role:rights-steward",
        "status": "active", "effective_from": "2026-08-26", "effective_to": None,
        "evidence_requirements": ["rights-profile"],
        "controls": [{"control_id": "rights-profile", "requirement": "Exact rights profile is registered."}],
    }
    compliance = evaluate_compliance(
        [obligation], jurisdictions=["internal"], scopes=["licensing"],
        evidence_index={"rights-profile": ["evidence:rights:stress"]}, as_of=date(2026, 8, 26),
    )
    asset = {
        "asset_id": "asset:stress", "version": "1.0.0", "content_sha256": "a" * 64,
        "title": "Stress fixture", "owner_ref": "CrownThrive LLC", "status": "active",
        "rights_control_refs": ["chlom:rights:stress"], "allowed_rights": ["display"],
        "prohibited_rights": ["sublicense"], "territories": ["US"], "media": ["web"],
    }
    return asset, compliance


def request(index: int, compliance: dict[str, Any]) -> tuple[dict[str, Any], str]:
    mode = index % 4
    packet = {
        "request_id": f"request:stress:{index}", "asset_id": "asset:stress", "asset_version": "1.0.0",
        "asset_sha256": "a" * 64, "licensee_ref": f"party:stress:{index}", "requested_rights": ["display"],
        "territories": ["US"], "media": ["web"], "use_case": "bounded stress fixture", "lane": "self_serve",
        "risk_class": "D1", "valid_from": "2026-08-26", "valid_until": "2027-08-26",
        "template_ref": "template:stress:v1", "acceptance_ref": f"acceptance:stress:{index}",
        "commercial_terms_ref": "terms:stress:v1",
        "authority_trace": {"chlom_ref": "chlom:rights:stress", "accountable_owner": "role:rights-steward"},
        "human_gate": {"required": False, "satisfied": False, "approver_refs": []},
        "compliance_receipt": compliance, "provider_effect": False, "provider_binding_ref": None,
        "readback_strategy": None, "idempotency_key": f"stress:{index}",
    }
    expected = "ISSUE_READY_INTERNAL"
    if mode == 1:
        packet["requested_rights"] = ["sublicense"]
        expected = "HOLD_FAIL_CLOSED"
    elif mode == 2:
        packet["provider_effect"] = True
        expected = "HOLD_FAIL_CLOSED"
    elif mode == 3:
        packet["risk_class"] = "D3"
        packet["lane"] = "reviewed"
        packet["human_gate"] = {"required": True, "satisfied": False, "approver_refs": []}
        expected = "HUMAN_REVIEW_REQUIRED"
    return packet, expected


def run_case(index: int, asset: dict[str, Any], compliance: dict[str, Any]) -> tuple[int, str, str, bool]:
    packet, expected = request(index, compliance)
    first = evaluate_license_request(asset, packet)
    second = evaluate_license_request(asset, packet)
    return index, expected, first["disposition"], first == second and verify_receipt(first)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    if args.cases < 1 or args.cases > 100000:
        raise SystemExit("--cases must be between 1 and 100000")
    if args.workers < 1 or args.workers > 64:
        raise SystemExit("--workers must be between 1 and 64")
    asset, compliance = fixture()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(lambda index: run_case(index, asset, compliance), range(args.cases)))
    failures = [index for index, expected, actual, deterministic in rows if expected != actual or not deterministic]
    counts: dict[str, int] = {}
    for _index, _expected, actual, _deterministic in rows:
        counts[actual] = counts.get(actual, 0) + 1
    receipt = {
        "schema": "ct.penta.compliance-license-stress.v1",
        "disposition": "PASS" if not failures else "FAIL",
        "cases": args.cases,
        "workers": args.workers,
        "disposition_counts": dict(sorted(counts.items())),
        "failures": failures[:20],
        "deterministic_replay_required": True,
        "unauthorized_issuance_count": sum(1 for _index, expected, actual, _deterministic in rows if expected != "ISSUE_READY_INTERNAL" and actual.startswith("ISSUE_READY")),
    }
    receipt["receipt_sha256"] = sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    print(json.dumps(receipt, sort_keys=True))
    return 0 if not failures and receipt["unauthorized_issuance_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
