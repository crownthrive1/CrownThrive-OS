#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

from penta_runtime_custody import assert_function, assert_lineage, assert_migration, load

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/cie-production-certification-bridge.v1.json"
LIVE_RECEIPT = ROOT / "developers/manifests/cie-production-certification-bridge-live-receipt-20260823.v1.json"
DOC = ROOT / "standards/cie-production-certification-bridge.md"
EXPECTED_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    for path in (MANIFEST, LIVE_RECEIPT, DOC):
        if not path.is_file(): fail(f"missing artifact: {path.relative_to(ROOT)}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    receipt = json.loads(LIVE_RECEIPT.read_text(encoding="utf-8"))
    doc = DOC.read_text(encoding="utf-8")
    provider = load()
    assert_lineage(provider)
    assert_migration(provider, "cie_production_certification_bridge_v1", "20260824012320")
    for name in (
        "chlom_runtime.cie_parent_certification_reconcile_v1",
        "chlom_runtime.cie_wave4_activation_evidence_gate_v1",
        "chlom_runtime.cie_lifecycle_release_reconcile_v1",
        "chlom_runtime.cie_production_certification_bridge_status_v1",
    ):
        assert_function(provider, name)

    if manifest.get("bridge_id") != "ct.bridge.cie.production-certification.v1": fail("bridge identity drift")
    if manifest.get("framework_id") != "ct.framework.cultural-imprint-engine": fail("framework identity drift")
    if manifest.get("canonical_engine_name") != "Cultural Imprint Engine": fail("canonical engine name drift")
    if manifest.get("accepted_public_contract_digest") != EXPECTED_DIGEST: fail("accepted contract digest drift")
    authority = manifest.get("authority_model", {})
    for key in ("originator_may_certify","service_role_may_manufacture_verifier_disposition","vote_effect","provider_write_effect","economic_effect","rights_effect","production_activation_effect"):
        if authority.get(key) is not False: fail(f"authority expansion: {key}")
    if authority.get("agent_d_resolution_required") is not True or authority.get("agent_d_certification_exact_snapshot_bound") is not True: fail("Agent D exact-snapshot boundary drift")
    if authority.get("lifecycle_verifier") != "ct.gen7.agent-q": fail("lifecycle verifier drift")
    if authority.get("semantic_evidence_required") is not True or authority.get("security_evidence_required") is not True: fail("independent evidence boundary drift")
    if authority.get("d3_human_reserved") is not True: fail("D3 reservation drift")

    if receipt.get("receipt_class") != "LIVE_CONTROLLED_TEST_EVIDENCE_NOT_REUSABLE_AUTHORITY": fail("live receipt classification drift")
    if receipt.get("bridge_id") != manifest.get("bridge_id"): fail("live bridge identity drift")
    thrivebase = receipt.get("thrivebase", {})
    if thrivebase.get("migration_name") != "cie_production_certification_bridge_v1" or thrivebase.get("apply_state") != "success": fail("live migration receipt drift")
    if str(thrivebase.get("migration_version")) != "20260824012320": fail("live applied migration version drift")
    status = receipt.get("live_status_readback", {})
    if status.get("bridge_state") != "HOLD_AGENT_D_EXACT_CERTIFICATION": fail("live bridge must remain Agent D HOLD")
    for key in ("activation_authorized","operational_activation","provider_write_effect","economic_effect","rights_effect","vote_effect","D3_auto"):
        if status.get(key) is not False: fail(f"live receipt authority expansion: {key}")
    semantics = receipt.get("snapshot_semantics", {})
    if semantics.get("historical_evidence_only") is not True or semantics.get("not_reusable_authority") is not True: fail("historical evidence boundary drift")
    if "deliberately **not** an activation function" not in doc.lower(): fail("documentation activation boundary missing")

    joined = "\n".join((doc, json.dumps(manifest, sort_keys=True), json.dumps(receipt, sort_keys=True), json.dumps(provider, sort_keys=True)))
    for pattern in (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", r"\bsb_secret_[A-Za-z0-9_-]{16,}\b", r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY"):
        if re.search(pattern, joined): fail("credential-shaped value detected")

    print("CIE production certification bridge PASS: provider-applied runtime and ACL custody verified; exact-snapshot fail-closed authority preserved; historical source SQL not reconstructed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
