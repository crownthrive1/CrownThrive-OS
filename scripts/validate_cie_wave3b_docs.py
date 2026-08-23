#!/usr/bin/env python3
"""Validate CIE Wave 3B durable-runtime documentation and public-safe manifest."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "doctrine/cie-chlom-interoperability.mdx",
    "doctrine/cie-durable-runtime-and-evidence.mdx",
    "developers/manifests/cie-chlom-durable-runtime.v1.json",
    "changelog/cie-institutionalization-wave-3b-2026-08-23.mdx",
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        fail(f"missing Wave 3B artifact: {rel}")
    return path.read_text(encoding="utf-8")


def load_json(rel: str) -> dict:
    value = json.loads(read(rel))
    if not isinstance(value, dict):
        fail(f"JSON object required: {rel}")
    return value


def main() -> int:
    for rel in REQUIRED_FILES:
        read(rel)

    interop = read("doctrine/cie-chlom-interoperability.mdx")
    runtime_doc = read("doctrine/cie-durable-runtime-and-evidence.mdx")
    changelog = read("changelog/cie-institutionalization-wave-3b-2026-08-23.mdx")
    manifest = load_json("developers/manifests/cie-chlom-durable-runtime.v1.json")

    for text in (interop, runtime_doc, changelog):
        if "Cultural Imprint Engine" not in text:
            fail("Wave 3B documentation missing canonical Cultural Imprint Engine name")

    required_runtime_text = (
        "ct.runtime.cie-chlom.durable.v1",
        "ct.system.cie.runtime",
        "ct.system.chlom.runtime",
        "ct.contract.cie-chlom.interop.v1",
        "ct.contract.cie-chlom.persistence.v1",
        "ct.route.cie-chlom.interop.v1",
        "COMPOSED_READY_NON_EXECUTING",
        "IDEMPOTENT_DUPLICATE",
        "HOLD_REPLAY_CONFLICT",
        "HOLD_ORPHAN_CHLOM_RECEIPT",
        "controlled-test",
        "forced",
        "append-only",
        "cie_chlom_exchange_receipts_dail_event_id_idx",
        "verify_dail_chain()",
        "blocked",
        "write_effect=true",
    )
    for needle in required_runtime_text:
        if needle not in runtime_doc:
            fail(f"durable runtime doctrine missing invariant: {needle}")

    if "not a public network endpoint" not in runtime_doc:
        fail("runtime doctrine must deny public network endpoint claim")
    if "direct service-role `INSERT`, `UPDATE` and `DELETE` denied" not in runtime_doc:
        fail("direct service-role write denial missing")
    if "A replay conflict does not overwrite the canonical receipt" not in runtime_doc:
        fail("append-only replay non-rewrite rule missing")
    if "permissive policy" not in runtime_doc:
        fail("intentional RLS-no-policy advisor disposition missing")

    if "durable internal controlled-test" not in interop:
        fail("Wave 2 interoperability page not updated with current durable controlled-test state")
    if "public network endpoint" not in interop:
        fail("interop page missing public-network non-claim")

    if manifest.get("manifest_id") != "ct.manifest.cie-chlom-durable-runtime.v1":
        fail("runtime manifest identity drift")
    if manifest.get("runtime_id") != "ct.runtime.cie-chlom.durable.v1":
        fail("runtime ID drift")
    if manifest.get("framework_id") != "ct.framework.cultural-imprint-engine":
        fail("framework ID drift")
    if manifest.get("canonical_engine_name") != "Cultural Imprint Engine":
        fail("canonical engine name drift")
    if manifest.get("public_contract_id") != "ct.contract.cie-chlom.interop.v1":
        fail("public contract drift")
    if manifest.get("persistence_contract_id") != "ct.contract.cie-chlom.persistence.v1":
        fail("persistence contract drift")
    if manifest.get("route_id") != "ct.route.cie-chlom.interop.v1":
        fail("route drift")

    state = manifest.get("current_state", {})
    if state.get("runtime_live_internal") is not True:
        fail("live internal runtime state missing")
    if state.get("contract_state") != "controlled_test" or state.get("route_state") != "controlled_test":
        fail("controlled-test state drift")
    if state.get("route_certification_state") != "candidate":
        fail("route certification state drift")
    if state.get("public_network_endpoint_deployed") is not False:
        fail("manifest falsely claims public network endpoint")
    if state.get("composition_ceiling") != "COMPOSED_READY_NON_EXECUTING":
        fail("composition ceiling drift")

    live = manifest.get("live_readback", {})
    if live.get("receipt_count") != 2 or live.get("correlation_count") != 1 or live.get("pending_correlation_count") != 0:
        fail("certification readback count drift")
    if live.get("forced_rls") is not True or live.get("service_role_record_execute") is not True:
        fail("live RLS/service-role readback drift")
    if live.get("anon_record_execute") is not False or live.get("authenticated_record_execute") is not False:
        fail("public writer execution drift")

    idem = manifest.get("idempotency", {})
    if idem.get("key") != ["correlation_id", "direction"]:
        fail("idempotency key drift")
    if idem.get("same_payload") != "IDEMPOTENT_DUPLICATE":
        fail("idempotent replay state drift")
    if idem.get("different_payload_same_key") != "HOLD_REPLAY_CONFLICT":
        fail("conflicting replay must HOLD")
    if idem.get("orphan_chlom_receipt") != "HOLD_ORPHAN_CHLOM_RECEIPT":
        fail("orphan receipt must HOLD")
    if idem.get("canonical_receipt_rewrite") is not False:
        fail("canonical receipt rewrite enabled")

    access = manifest.get("access", {})
    required_true = ("rls_enabled", "rls_forced", "service_role_select", "append_only_trigger")
    required_false = (
        "anon_table_access",
        "authenticated_table_access",
        "service_role_direct_insert",
        "service_role_direct_update",
        "service_role_direct_delete",
    )
    for key in required_true:
        if access.get(key) is not True:
            fail(f"access invariant false: {key}")
    for key in required_false:
        if access.get(key) is not False:
            fail(f"access authority expansion: {key}")

    dail = manifest.get("dail", {})
    if dail.get("direct_wave3b_payload_hash_readback") != "verified":
        fail("DAIL payload hash readback missing")
    if dail.get("direct_wave3b_previous_link_readback") != "verified":
        fail("DAIL previous-link readback missing")
    if dail.get("generic_verify_dail_chain_call") != "tool_blocked_not_claimed_pass":
        fail("blocked generic DAIL verification must not be represented as pass")

    perf = manifest.get("performance", {})
    if perf.get("dail_event_foreign_key_index") != "cie_chlom_exchange_receipts_dail_event_id_idx":
        fail("DAIL FK supporting index missing")
    if perf.get("wave3b_specific_fk_index_gap") != "resolved":
        fail("Wave 3B FK performance gap unresolved")

    migrations = manifest.get("migrations", [])
    expected_migrations = [
        ("cie_chlom_durable_interop_runtime_v1", "20260823222743"),
        ("cie_chlom_durable_interop_runtime_v1_hardening", "20260823222814"),
        ("cie_chlom_durable_interop_runtime_v1_performance", "20260823223341"),
    ]
    got = [(item.get("name"), item.get("version")) for item in migrations if isinstance(item, dict)]
    if got != expected_migrations:
        fail(f"migration evidence drift: {got}")

    source = manifest.get("source", {})
    if source.get("repository") != "crownthrive1/CrownThrive-CIE" or source.get("merged_pr") != 19:
        fail("accepted CIE source projection drift")
    if source.get("merge_sha") != "2067572bd9674766b4121c904c2042a87e4d5bcb":
        fail("accepted CIE merge SHA drift")

    authority = manifest.get("authority", {})
    if authority.get("package_state") != "CONTROLLED_TEST" or authority.get("authority_ceiling") != "D2":
        fail("CIE package/authority state drift")
    if authority.get("d3_human_reserved") is not True:
        fail("D3 reservation drift")
    for key in (
        "vote_eligible",
        "provider_write_authorized",
        "production_deployment_authorized",
        "protected_score_activation_authorized",
        "economic_activation_authorized",
        "checkout_authorized",
        "entitlement_authorized",
        "license_issuance_by_inheritance",
        "sovereign_vote_effect",
    ):
        if authority.get(key) is not False:
            fail(f"Wave 3B authority expansion: {key}")

    joined = "\n".join(read(rel) for rel in REQUIRED_FILES)
    credential_patterns = (
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"\bsb_secret_[A-Za-z0-9_-]{16,}\b",
        r"\bsk-[A-Za-z0-9]{20,}\b",
        r"\bmint_[A-Za-z0-9_-]{16,}\b",
    )
    for pattern in credential_patterns:
        if re.search(pattern, joined):
            fail("credential-shaped value detected in Wave 3B public docs")

    print(
        "CIE Wave 3B docs PASS: Cultural Imprint Engine durable CHLOM runtime is live internally "
        "in controlled test with forced-RLS append-only evidence, replay/orphan fail-closed, DAIL "
        "readback and COMPOSED_READY_NON_EXECUTING ceiling; no public/economic/D3 authority."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
