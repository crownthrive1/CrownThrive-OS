#!/usr/bin/env python3
"""Validate the bounded CHLOM Cell 08 TEVV packet.

A green validator means the test/evidence packet is internally consistent. It does
not mean open security findings are resolved; open high/critical findings must
remain explicitly promotion-blocking until repaired and independently reverified.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVARIANTS = ROOT / "contracts/chlom/tevv/invariants.v1.json"
PACKET = ROOT / "contracts/chlom/tevv/packet.v1.json"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load(path: Path) -> dict:
    if not path.is_file():
        fail(f"Missing required TEVV file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    invariants = load(INVARIANTS)
    packet = load(PACKET)

    if invariants.get("fixture_id") != "ct.fixture.chlom.tevv.invariants.v1":
        fail("TEVV invariant fixture ID drifted")
    if invariants.get("state") != "phase_2_99_prototype":
        fail("TEVV invariants must remain Phase 2.99 prototype state")
    if invariants.get("authority_rule") != "no_backend_may_expand_permission_beyond_canonical_contract":
        fail("External backend authority boundary drifted")
    if invariants.get("provider_mutation") is not False:
        fail("TEVV must not mutate production providers")
    if invariants.get("free_form_docs_executable") is not False:
        fail("Free-form documentation must never execute as policy")
    if invariants.get("severity_policy", {}).get("critical") != "block":
        fail("Critical TEVV failures must block")
    if invariants.get("severity_policy", {}).get("high") != "block":
        fail("High TEVV failures must block")

    vectors = invariants.get("vectors", [])
    ids = {item.get("vector_id") for item in vectors}
    required_vectors = {
        "ct.tevv.authn.unauthenticated-default-deny",
        "ct.tevv.authz.cross-tenant-isolation",
        "ct.tevv.authority.approval-not-self-proving",
        "ct.tevv.d3.never-autonomous-allow",
        "ct.tevv.policy.unknown-condition-fail-closed",
        "ct.tevv.policy.prompt-rule-injection-no-authority",
        "ct.tevv.policy.stale-superseded-bundle-rejected",
        "ct.tevv.replay.idempotent-retry-single-decision",
        "ct.tevv.replay.idempotency-key-payload-conflict",
        "ct.tevv.dail.tamper-detected",
        "ct.tevv.evidence.restricted-material-not-persisted-as-reference",
        "ct.tevv.provider.outage-malformed-output-fail-closed",
        "ct.tevv.webhook.replay-idempotent-rejected",
        "ct.tevv.ai.confidence-cannot-create-authority",
        "ct.tevv.recovery.known-good-restore",
    }
    missing = sorted(required_vectors - ids)
    if missing:
        fail("Missing TEVV invariant vectors: " + ", ".join(missing))

    valid_backends = {"native", "opa_adapter", "openfga_adapter", "cedar_adapter", "temporal_workflow"}
    for item in vectors:
        severity = item.get("severity_if_failed")
        if severity not in {"critical", "high", "medium", "low"}:
            fail(f"Invalid TEVV severity for {item.get('vector_id')}")
        applies = set(item.get("applies_to", []))
        if not applies or not applies.issubset(valid_backends):
            fail(f"Invalid backend applicability for {item.get('vector_id')}: {sorted(applies)}")

    if packet.get("packet_id") != "ct.packet.chlom.cell.tevv.invariants-v1":
        fail("Cell 08 packet ID drifted")
    if packet.get("cell_id") != "ct.chlom.cell.tevv" or packet.get("issue") != 75:
        fail("Cell 08 ownership drifted")
    if packet.get("parent_pr") != 67 or packet.get("stacked_on_pr") != 82:
        fail("Cell 08 stack/parent relationship drifted")
    if packet.get("risk_class") != "D2":
        fail("TEVV packet must remain D2")
    if set(packet.get("required_specialists", [])) != {
        "security_privacy", "ai_ml_llm_tevv", "operations_sre"
    }:
        fail("Cell 08 specialist gates drifted")
    if packet.get("provider_mutation") is not False or packet.get("production_activation") is not False:
        fail("TEVV packet cannot activate or mutate production")
    if packet.get("backend_authority_rule") != "external_backend_cannot_expand_permission_beyond_canonical_contract":
        fail("Backend authority rule drifted")
    if packet.get("advanced_crypto_state") != "phase_9_research_only":
        fail("Advanced crypto/token security must remain Phase 9 research only")

    findings = packet.get("known_findings", [])
    finding_ids = {item.get("finding_id") for item in findings}
    required_open = {
        "ct.finding.tevv.authority-approval-self-assertion",
        "ct.finding.tevv.restricted-evidence-reference-unsanitized",
    }
    if not required_open.issubset(finding_ids):
        fail("Known blocking TEVV findings were removed without adjudication")
    open_high = [
        item for item in findings
        if item.get("status") == "open" and item.get("severity") in {"critical", "high"}
    ]
    if not open_high:
        fail("TEVV packet currently requires explicit open high findings")
    if any(item.get("blocking") is not True for item in open_high):
        fail("Every open critical/high TEVV finding must block promotion")
    if packet.get("promotion_state") != "blocked_by_open_high_findings":
        fail("Promotion must remain blocked while high findings are open")
    if packet.get("phase_3_effect") != "no_phase_3_entry; open_high_tevv_findings_are_blocking":
        fail("Phase 3 TEVV gate drifted")

    print("CHLOM Cell 08 TEVV packet validation passed.")
    print(f"Invariant vectors: {len(vectors)}; open critical/high findings: {len(open_high)}.")
    print("Green validator = evidence packet is coherent; promotion remains blocked by open high findings.")
    print("Backends remain non-authoritative until invariant-equivalence and adoption gates pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
