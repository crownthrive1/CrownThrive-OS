#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

from penta_runtime_custody import assert_function, assert_lineage, assert_migration, load

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/cie-post-activation-link-assurance.v1.json"
LIVE_RECEIPT = ROOT / "developers/manifests/cie-post-activation-link-assurance-live-receipt-20260824.v1.json"
DOC = ROOT / "standards/cie-post-activation-link-assurance.md"
EXPECTED_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"


def fail(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def require_false_map(value: object, label: str) -> None:
    if not isinstance(value, dict) or not value:
        fail(f"{label} must be a non-empty object")
    for key, flag in value.items():
        if flag is not False:
            fail(f"{label} expanded: {key}")


def main() -> int:
    for path in (MANIFEST, LIVE_RECEIPT, DOC):
        if not path.is_file(): fail(f"missing artifact: {path.relative_to(ROOT)}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = json.loads(LIVE_RECEIPT.read_text(encoding="utf-8"))
    doc = DOC.read_text(encoding="utf-8")
    provider = load()
    assert_lineage(provider)
    assert_migration(provider, "cie_post_activation_link_assurance_v1", "20260824070845")
    assert_function(provider, "chlom_runtime.refresh_cie_parent_child_production_assurance_v1")
    assert_function(provider, "chlom_runtime.cie_post_activation_link_assurance_status_v1")

    if manifest.get("assurance_id") != "ct.assurance.cie.post-activation-link.v1": fail("assurance identity drift")
    if manifest.get("canonical_engine_name") != "Cultural Imprint Engine": fail("canonical engine name drift")
    if manifest.get("accepted_public_contract_digest") != EXPECTED_DIGEST: fail("CIE public contract digest drift")
    prod = manifest.get("production_authority", {})
    if prod.get("required_mode") != "founder_direct": fail("founder-direct production binding drift")
    for key in ("rewrite_original_authority_snapshot","rewrite_founder_request","rewrite_production_exact_version_ref","rewrite_production_content_sha256"):
        if prod.get(key) is not False: fail(f"production authority rewrite prohibited: {key}")
    require_false_map(manifest.get("hard_boundaries"), "manifest hard boundary")

    if live.get("assurance_id") != manifest.get("assurance_id"): fail("live receipt assurance identity mismatch")
    if live.get("evidence_class") != "historical_live_readback_not_reusable_authority": fail("live receipt evidence class drift")
    db = live.get("database_migration", {})
    if db.get("source_file_version") != "20260824070356" or db.get("applied_version") != "20260824070845" or db.get("apply_state") != "success": fail("live database migration evidence drift")
    original = live.get("original_production_authority", {})
    if original.get("authority_mode") != "founder_direct" or original.get("authority_snapshot_rewritten") is not False: fail("historical authority snapshot drift")
    assurance = live.get("live_assurance", {})
    if assurance.get("state") != "PRODUCTION_ACTIVE_CURRENT_LINK_ASSURED" or assurance.get("link_state") != "linked_governed" or assurance.get("production_authority_rewritten") is not False: fail("historical live assurance drift")
    post = live.get("post_refresh_state", {})
    for key in ("production_parent_head_unchanged","production_child_head_unchanged","production_exact_version_ref_unchanged","production_content_sha256_unchanged","production_authority_request_id_unchanged","production_activation_receipt_unchanged"):
        if post.get(key) is not True: fail(f"post-refresh authority snapshot changed: {key}")
    require_false_map(live.get("hard_boundaries"), "live receipt hard boundary")
    reuse = str(live.get("reuse_rule", "")).lower()
    if "not authority" not in reuse or "must not be reused" not in reuse: fail("live receipt reuse rule drift")
    if "does **not** reactivate cie" not in doc.lower(): fail("documentation activation boundary missing")

    joined = "\n".join((doc, json.dumps(manifest, sort_keys=True), json.dumps(live, sort_keys=True), json.dumps(provider, sort_keys=True)))
    for pattern in (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", r"\bsb_secret_[A-Za-z0-9_-]{16,}\b", r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY"):
        if re.search(pattern, joined): fail("credential-shaped value detected")

    print("CIE post-activation link assurance PASS: applied migration/runtime ACL custody verified; founder-direct snapshot remains non-rewritten; historical source SQL not reconstructed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
