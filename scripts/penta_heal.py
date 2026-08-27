#!/usr/bin/env python3
"""PentaHeal: convert PentaGate findings into bounded PentaImmune repairs.

PentaHeal does not execute arbitrary edits and cannot certify or promote itself.
It produces deterministic, rollback-bound repair packets for PentaBuild/PentaPR
and PentaCertify to execute and verify on the exact head.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.penta_immune import WeaknessCandidate, build_repair_plan  # noqa: E402
from penta_gate import scan_repository  # noqa: E402

SCHEMA = "ct.penta.heal-packet.20260826.v1"


def _candidate(index: int, finding: dict[str, Any]) -> WeaknessCandidate:
    code = str(finding.get("code", "unknown"))
    path = str(finding.get("path", "unknown"))
    handler = str(finding.get("repair_class") or "patch_known_code")
    if handler not in {"patch_known_code", "repair_workflow"}:
        handler = "patch_known_code"
    return WeaknessCandidate(
        id=f"pentagate-{index}-{code}",
        kind="ci_failure" if code == "missing_test_import" else "test_failure",
        source_ref=f"pentagate:{path}:{code}",
        authority_level="D1",
        handler=handler,
        severity=4,
        recurrence=2,
        confidence=5,
        reversibility=5,
        testability=5,
        blast_radius=1,
        rollback={"method": "git_revert", "scope": path},
        fallback={"method": "hold", "redundancy": "known-good-main"},
        metadata={
            "finding": code,
            "path": path,
            "module": finding.get("module"),
            "detail": finding.get("detail"),
            "producer": "PentaGate",
            "executor": "PentaBuild",
            "verifier": "PentaCertify",
            "orchestrator": "PentaPR",
        },
    )


def build_heal_packet(gate_report: dict[str, Any]) -> dict[str, Any]:
    plans: list[dict[str, Any]] = []
    for index, finding in enumerate(gate_report.get("findings", []), start=1):
        candidate = _candidate(index, dict(finding))
        plans.append(build_repair_plan(candidate))
    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "gate_receipt_sha256": gate_report.get("receipt_sha256"),
        "gate_status": gate_report.get("status"),
        "repair_count": len(plans),
        "repairs": plans,
        "routing": ["PentaGate", "PentaHeal", "PentaBuild", "PentaCertify", "PentaPR", "PentaMerge|PentaCloser"],
        "exact_head_test_required": True,
        "independent_certification_required": True,
        "automatic_arbitrary_edit_authorized": False,
        "self_certification_authorized": False,
        "production_promotion_authorized": False,
    }
    encoded = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode("utf-8")
    packet["packet_sha256"] = hashlib.sha256(encoded).hexdigest()
    return packet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--gate-report")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.gate_report:
        gate_report = json.loads(Path(args.gate_report).read_text(encoding="utf-8"))
    else:
        gate_report = scan_repository(Path(args.root))
    packet = build_heal_packet(gate_report)
    rendered = json.dumps(packet, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    # A clean scan needs no repair and is healthy. A dirty scan stays HOLD so
    # downstream lanes cannot treat a generated repair plan as certification.
    return 0 if gate_report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
