#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

from penta_runtime_custody import assert_cron, assert_function, assert_lineage, assert_migration, load

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/cie-post-activation-assurance-watch.v1.json"
LIVE_RECEIPT = ROOT / "developers/manifests/cie-post-activation-assurance-watch-live-receipt-20260824.v1.json"
DOC = ROOT / "standards/cie-post-activation-assurance-watch.md"
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
        if not path.is_file():
            fail(f"missing artifact: {path.relative_to(ROOT)}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = json.loads(LIVE_RECEIPT.read_text(encoding="utf-8"))
    doc = DOC.read_text(encoding="utf-8")
    provider = load()
    assert_lineage(provider)
    assert_migration(provider, "cie_post_activation_assurance_watch_v1", "20260824074339")
    assert_function(provider, "chlom_runtime.cie_post_activation_assurance_watch_v1")
    assert_function(provider, "chlom_runtime.repository_child_guardian_family_cycle_v1")
    assert_cron(provider, "ct-repository-child-guardian-30m", "7,37 * * * *")

    if manifest.get("watch_id") != "ct.watch.cie.post-activation-assurance.v1": fail("watch identity drift")
    if manifest.get("framework_id") != "ct.framework.cultural-imprint-engine": fail("framework identity drift")
    if manifest.get("canonical_engine_name") != "Cultural Imprint Engine": fail("canonical engine name drift")
    if manifest.get("accepted_public_contract_digest") != EXPECTED_DIGEST: fail("accepted CIE contract digest drift")
    host = manifest.get("host_schedule", {})
    if host.get("schedule_id") != "ct.schedule.repository-child-guardian-30m" or host.get("cron_expression") != "7,37 * * * *": fail("watch schedule binding drift")
    if host.get("existing_slot_reused") is not True or host.get("scheduler_slot_delta") != 0: fail("watch may not add scheduler slot")
    evidence = manifest.get("evidence_contract", {})
    if evidence.get("sql_makes_external_network_calls") is not False or evidence.get("fresh_service_ingested_github_observations_required") is not True: fail("external evidence boundary drift")
    auto = manifest.get("automatic_actions", {})
    for key in ("cie_child_head_auto_refresh","production_reactivation","founder_authority_rewrite","public_activation","commerce_activation","provider_write","rights_grant","vote_effect","d3_auto"):
        if auto.get(key) is not False: fail(f"forbidden automatic action enabled: {key}")
    require_false_map(manifest.get("hard_boundaries"), "manifest hard boundary")

    if live.get("watch_id") != manifest.get("watch_id"): fail("live receipt watch identity mismatch")
    if live.get("evidence_class") != "historical_live_runtime_certification_not_authority": fail("live receipt evidence class drift")
    db = live.get("database_migration", {})
    if db.get("source_file_version") != "20260824073728" or db.get("applied_version") != "20260824074339" or db.get("apply_state") != "success": fail("live migration receipt drift")
    real = live.get("real_watch_test", {})
    if real.get("state") != "PASS_CURRENT_ASSURANCE" or real.get("production_authority_rewritten") is not False: fail("historical watcher certification drift")
    security = live.get("security_readback", {})
    if security.get("watch_security_definer") is not True or security.get("guardian_wrapper_security_definer") is not True: fail("historical security readback drift")
    require_false_map(live.get("hard_boundaries"), "live receipt hard boundary")
    reuse = str(live.get("reuse_rule", "")).lower()
    if "not production authority" not in reuse or "must not be used to infer current github state" not in reuse: fail("live receipt reuse boundary missing")

    for text in (doc, json.dumps(manifest, sort_keys=True), json.dumps(live, sort_keys=True), json.dumps(provider, sort_keys=True)):
        for pattern in (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", r"\bsb_secret_[A-Za-z0-9_-]{16,}\b", r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY"):
            if re.search(pattern, text): fail("credential-shaped value detected")

    print("CIE post-activation assurance watch PASS: provider-applied runtime and ACL custody verified; historical source SQL not reconstructed; Guardian slot reused; live receipt remains non-authority.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
