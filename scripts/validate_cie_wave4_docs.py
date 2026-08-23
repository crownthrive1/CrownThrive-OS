#!/usr/bin/env python3
"""Validate the public-safe CIE Wave 4 activation-evidence projection."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "doctrine/cie-activation-evidence-gate.mdx",
    "developers/manifests/cie-activation-evidence-gate.v1.json",
    "changelog/cie-institutionalization-wave-4-2026-08-23.mdx",
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        fail(f"missing Wave 4 artifact: {rel}")
    return path.read_text(encoding="utf-8")


def load_json(rel: str) -> dict:
    value = json.loads(read(rel))
    if not isinstance(value, dict):
        fail(f"JSON object required: {rel}")
    return value


def main() -> int:
    for rel in REQUIRED_FILES:
        read(rel)

    doctrine = read("doctrine/cie-activation-evidence-gate.mdx")
    changelog = read("changelog/cie-institutionalization-wave-4-2026-08-23.mdx")
    manifest = load_json("developers/manifests/cie-activation-evidence-gate.v1.json")

    for text in (doctrine, changelog):
        if "Cultural Imprint Engine" not in text:
            fail("Wave 4 docs missing canonical Cultural Imprint Engine name")

    required_doctrine = (
        "ct.gate.cie.activation-evidence.v1",
        "HOLD_CONTRACT_DIGEST_MISMATCH",
        "HOLD_SOURCE_INTEGRATION",
        "SOURCE_INTEGRATION_READY",
        "READY_FOR_INDEPENDENT_REVIEW_AND_FOUNDER_RATIFICATION",
        "Agent D parent certification",
        "independent semantic verification",
        "independent security review",
        "Founder first-activation ratification",
        "4676a016-2089-4599-abd6-eec745702328",
        "2b22b422d8345424d27438972691addb6f0eeba800368aa8180593efabb66a9f",
        "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2",
        "chlom_runtime.cie_wave4_activation_evidence_gate_v1(text,text,text)",
        "activation_authorized: false",
        "must_ask_founder_before_override: true",
        "override_executable: false",
    )
    for needle in required_doctrine:
        if needle not in doctrine:
            fail(f"Wave 4 doctrine missing invariant: {needle}")

    if "do **not** choose one silently" not in doctrine:
        fail("contract digest mismatch must not be silently reconciled")
    if "not execution authority" not in doctrine:
        fail("review handoff must not be represented as execution authority")

    if manifest.get("manifest_id") != "ct.manifest.cie.activation-evidence-gate.v1":
        fail("Wave 4 manifest identity drift")
    if manifest.get("gate_id") != "ct.gate.cie.activation-evidence.v1":
        fail("Wave 4 gate ID drift")
    if manifest.get("framework_id") != "ct.framework.cultural-imprint-engine":
        fail("Wave 4 framework identity drift")
    if manifest.get("canonical_engine_name") != "Cultural Imprint Engine":
        fail("Wave 4 canonical engine drift")

    state = manifest.get("current_state", {})
    if state.get("source_integration_state") != "HOLD_CONTRACT_DIGEST_MISMATCH":
        fail("source integration must remain HOLD on digest mismatch")
    if state.get("activation_gate_state") != "HOLD_SOURCE_INTEGRATION":
        fail("activation gate must remain HOLD")
    if state.get("activation_authorized") is not False or state.get("protected_score_activation_authorized") is not False:
        fail("Wave 4 falsely activates protected scoring")
    if state.get("public_cie_api_mcp_deployment_claimed") is not False:
        fail("Wave 4 falsely claims public CIE API/MCP deployment")

    runtime = manifest.get("durable_runtime", {})
    if runtime.get("runtime_id") != "ct.runtime.cie-chlom.durable.v1" or runtime.get("live") is not True:
        fail("Wave 3B durable runtime binding drift")
    if runtime.get("contract_state") != "controlled_test" or runtime.get("route_state") != "controlled_test":
        fail("durable runtime controlled-test state drift")
    if runtime.get("composition_ceiling") != "COMPOSED_READY_NON_EXECUTING":
        fail("durable runtime composition ceiling drift")

    link = manifest.get("parent_link", {})
    if link.get("link_receipt_id") != "4676a016-2089-4599-abd6-eec745702328":
        fail("refreshed parent-link receipt drift")
    if link.get("cie_head_at_refresh") != "2067572bd9674766b4121c904c2042a87e4d5bcb":
        fail("parent-link CIE exact-head drift")
    if link.get("support_head_at_refresh") != "bfe78d6955611fd43faf606c01257edc80943d51":
        fail("parent-link Support exact-head drift")
    if link.get("state") != "TECHNICALLY_LINKED_PENDING_GOVERNANCE":
        fail("parent-link governance state drift")
    for key in ("guardian_verified", "family_verified", "interoperability_verified"):
        if link.get(key) is not True:
            fail(f"parent-link verification missing: {key}")
    for key in ("operational_activation", "vote_effect", "authority_effect"):
        if link.get(key) is not False:
            fail(f"parent-link authority expansion: {key}")
    if link.get("predecessor_pr") != 18 or link.get("predecessor_state") != "closed_superseded_snapshot":
        fail("PR18 supersession state drift")

    score = manifest.get("protected_score_candidate", {})
    if score.get("source_pr") != 17 or score.get("source_pr_state") != "open_draft_hold":
        fail("PR17 protected-score source status drift")
    if score.get("candidate_public_contract_digest") != "2b22b422d8345424d27438972691addb6f0eeba800368aa8180593efabb66a9f":
        fail("candidate public-contract digest drift")
    if score.get("live_algorithm_registry_digest") != "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2":
        fail("live algorithm-registry digest snapshot drift")
    if score.get("contract_digest_match") is not False or score.get("disposition") != "HOLD_CONTRACT_DIGEST_MISMATCH":
        fail("protected-score digest mismatch must remain HOLD")
    if score.get("public_score_fallback") is not False or score.get("local_scoring_implementation") is not False:
        fail("protected scoring boundary drift")

    package = manifest.get("package_boundary", {})
    if package.get("package_state") != "controlled_test" or package.get("authority_ceiling") != "D2":
        fail("package controlled-test/D2 boundary drift")
    if package.get("can_vote") is not False or package.get("d3_human_reserved") is not True:
        fail("package voting/D3 boundary drift")
    if package.get("parent_certification_state") != "pending":
        fail("Agent D parent certification must remain pending")
    for key in ("operationally_enabled", "public_activation_allowed", "exact_price_authorized", "checkout_enabled", "customer_entitlement_active"):
        if package.get(key) is not False:
            fail(f"package activation/economic expansion: {key}")

    live = manifest.get("live_gate", {})
    if live.get("migration_version") != "20260823234034":
        fail("Wave 4 migration evidence drift")
    if live.get("durable_runtime_ok") is not True or live.get("parent_link_ok") is not True or live.get("package_boundary_ok") is not True:
        fail("Wave 4 positive prerequisites drift")
    if live.get("contract_digest_match") is not False or live.get("parent_certified") is not False:
        fail("Wave 4 HOLD predicates drift")
    if live.get("anon_execute") is not False or live.get("authenticated_execute") is not False or live.get("service_role_execute") is not True:
        fail("Wave 4 function ACL drift")

    dail = manifest.get("dail", {})
    if dail.get("payload_hash_readback") != "verified":
        fail("Wave 4 DAIL payload hash verification missing")
    if dail.get("global_previous_link_readback") != "verified":
        fail("Wave 4 DAIL global link verification missing")
    if dail.get("event_hash_readback") != "verified":
        fail("Wave 4 DAIL event hash verification missing")
    if dail.get("install_event", {}).get("sequence_id") != 1106 or dail.get("observation_event", {}).get("sequence_id") != 1108:
        fail("Wave 4 DAIL sequence evidence drift")

    prerequisites = manifest.get("activation_prerequisites_after_source_integration", [])
    expected = [
        "agent_d_parent_certification",
        "independent_semantic_verification",
        "independent_security_review",
        "exact_head_and_digest_match",
        "founder_first_activation_ratification",
    ]
    if prerequisites != expected:
        fail("Wave 4 activation prerequisites drift")

    override = manifest.get("founder_override", {})
    if override.get("ask_first") is not True or override.get("governance_deadlock_confirmed") is not False:
        fail("Founder Override ask-first/deadlock state drift")
    if override.get("override_executable") is not False or override.get("silence_is_not_authority") is not True:
        fail("Founder Override became executable")

    authority = manifest.get("authority", {})
    for key, value in authority.items():
        if value is not False:
            fail(f"Wave 4 authority expansion: {key}")

    source = manifest.get("source", {})
    if source.get("repository") != "crownthrive1/CrownThrive-CIE" or source.get("merged_pr") != 20:
        fail("accepted Wave 4 source projection drift")
    if source.get("merge_sha") != "2638cd6777023605db1ca1dcdaadbedc415a8b50":
        fail("accepted Wave 4 merge SHA drift")

    joined = "\n".join(read(rel) for rel in REQUIRED_FILES)
    credential_patterns = (
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"\bsb_secret_[A-Za-z0-9_-]{16,}\b",
        r"\bsk-[A-Za-z0-9]{20,}\b",
        r"\bmint_[A-Za-z0-9_-]{16,}\b",
        r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY",
    )
    for pattern in credential_patterns:
        if re.search(pattern, joined):
            fail("credential-shaped value detected in Wave 4 public docs")

    print(
        "CIE Wave 4 docs PASS: durable runtime and refreshed parent link pass; protected-score contract digest "
        "and Agent D certification remain HOLD/pending; no protected-score/provider/economic/D3/sovereign activation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
