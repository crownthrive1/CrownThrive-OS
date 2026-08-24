#!/usr/bin/env python3
"""Validate the bounded CHLOM Cell 08 TEVV packet.

A green validator means the TEVV packet is internally coherent. It never turns
an open or revalidation-pending high/critical finding into a pass. A high or
critical finding may become resolved only when closure evidence is recorded and
the packet no longer marks it blocking.
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
    if invariants.get("fixture_version") != "1.1.0":
        fail("TEVV fixture must remain on remediation-aware version 1.1.0")
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
        "ct.tevv.contract.untrusted-no-implicit-legacy-downgrade",
        "ct.tevv.authn.unauthenticated-default-deny",
        "ct.tevv.authz.cross-tenant-isolation",
        "ct.tevv.authority.approval-not-self-proving",
        "ct.tevv.authority.verified-context-bound-relationship-delegation",
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
    if packet.get("packet_version") != "1.1.1":
        fail("Cell 08 packet must remain closure-evidence version 1.1.1")
    if packet.get("cell_id") != "ct.chlom.cell.tevv" or packet.get("issue") != 75:
        fail("Cell 08 ownership drifted")
    if packet.get("parent_pr") != 67 or packet.get("stacked_on_pr") != 82:
        fail("Cell 08 stack/parent relationship drifted")
    if packet.get("tested_kernel_head") != "30d7b49bf6b01d6d094f62fa357dd31647ef078a":
        fail("Cell 08 tested kernel head drifted")
    if packet.get("tevv_revalidation_head") != "396d69fefb43fee447644a4f7e65e1c5cf336916":
        fail("Cell 08 revalidation evidence head drifted")
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
    by_id = {item.get("finding_id"): item for item in findings}
    required_findings = {
        "ct.finding.tevv.authority-approval-self-assertion",
        "ct.finding.tevv.restricted-evidence-reference-unsanitized",
        "ct.finding.tevv.policy-bundle-state-unverified",
    }
    if not required_findings.issubset(by_id):
        fail("Known TEVV findings were removed instead of adjudicated")

    unresolved_high = []
    resolved_high = []
    for finding_id in (
        "ct.finding.tevv.authority-approval-self-assertion",
        "ct.finding.tevv.restricted-evidence-reference-unsanitized",
    ):
        item = by_id[finding_id]
        if item.get("severity") != "high":
            fail(f"{finding_id} severity drifted")
        status = item.get("status")
        if status in {"open", "remediated_pending_exact_head_tevv_revalidation"}:
            if item.get("blocking") is not True:
                fail(f"{finding_id} must block until exact-head revalidation resolves it")
            unresolved_high.append(item)
        elif status == "resolved":
            if item.get("blocking") is not False:
                fail(f"resolved {finding_id} cannot remain marked blocking")
            closure = str(item.get("closure_evidence", ""))
            if "32221488101" not in closure or "95972654206" not in closure or "396d69f" not in closure:
                fail(f"resolved {finding_id} requires exact TEVV run/job/head closure evidence")
            resolved_high.append(item)
        else:
            fail(f"unsupported finding lifecycle state for {finding_id}: {status!r}")

    medium = by_id["ct.finding.tevv.policy-bundle-state-unverified"]
    if medium.get("severity") != "medium" or medium.get("status") != "open":
        fail("policy-bundle trust gap must remain an explicit open medium finding")

    revalidation = packet.get("revalidation", {})
    if revalidation.get("original_high_vectors_changed") is not False:
        fail("Original HIGH acceptance vectors must not be weakened")
    if revalidation.get("original_high_vectors_rerun_passed") is not True:
        fail("Resolved HIGH findings require original vector rerun PASS")
    if revalidation.get("native_tests_passed") != 16 or revalidation.get("invariant_vectors_defined") != 17:
        fail("Cell 08 exact revalidation test/vector counts drifted")
    for key in (
        "full_cell_08_ci_passed_on_revalidation_head",
        "full_parent_chlom_validation_passed_on_revalidation_head",
        "security_governance_passed_on_revalidation_head",
        "documentation_governance_passed_on_revalidation_head",
    ):
        if revalidation.get(key) is not True:
            fail(f"Resolved HIGH findings require {key}=true")

    if unresolved_high:
        if packet.get("promotion_state") != "blocked_pending_exact_head_tevv_revalidation_and_parent_sequence":
            fail("promotion state must remain blocked while high findings await revalidation")
    else:
        if len(resolved_high) != 2:
            fail("both original HIGH findings must be explicitly resolved")
        if packet.get("promotion_state") != "high_findings_resolved_parent_sequence_and_medium_policy_gap_remain":
            fail("promotion state must record resolved highs without erasing remaining parent/medium gates")

    if not str(packet.get("phase_3_effect", "")).startswith("no_phase_3_entry"):
        fail("Cell 08 may not open Phase 3")

    print("CHLOM Cell 08 TEVV packet validation passed.")
    print(f"Invariant vectors: {len(vectors)}; unresolved critical/high findings: {len(unresolved_high)}; resolved high findings: {len(resolved_high)}.")
    print("Finding lifecycle is fail-closed; resolution requires exact closure evidence and cannot weaken vectors.")
    print("Backends remain non-authoritative until invariant-equivalence and adoption gates pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
