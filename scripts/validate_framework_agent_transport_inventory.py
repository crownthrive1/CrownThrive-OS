#!/usr/bin/env python3
"""Fail-closed validation for the CIE pre-cert parent/child transport binding."""
from __future__ import annotations
import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")

class ValidationError(RuntimeError):
    pass

def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)

def validate(data: dict[str, Any]) -> None:
    need(data.get("manifest_id") == "ct.manifest.framework-agent-transport-inventory.v1", "manifest identity drift")
    need(data.get("classification") == "PUBLIC_STANDARD", "binding projection must remain public-safe metadata only")
    need(data.get("program_authority_issue") == 148, "Framework Factory authority drift")
    need(data.get("current_constitution") == "CT-ADR-GOV-011", "current constitution drift")
    need(data.get("binding_model") == "two_phase_non_circular_pre_cert_anchor", "binding model drift")

    parent = data.get("parent_anchor", {})
    need(parent.get("repo_id") == "ct.repo.crownthrive-support", "parent repo id drift")
    need(parent.get("github_repository_id") == 1336348391, "parent immutable repository id drift")
    need(parent.get("pull_request") == 169, "parent PR drift")
    need(bool(SHA40.fullmatch(str(parent.get("anchor_sha", "")))), "parent anchor SHA must be exact")
    need(bool(SHA64.fullmatch(str(parent.get("federation_manifest_sha256", "")))), "parent manifest digest must be SHA-256")
    need(parent.get("governed_acceptance_from_anchor") is False, "binding anchor cannot imply governed acceptance")
    need(str(parent.get("current_main_collision_state", "")).startswith("DIVERGED_"), "current-main collision must remain explicit")

    children = data.get("children", [])
    need(isinstance(children, list) and len(children) == 1, "only CIE may be bound in this packet")
    child = children[0]
    need(child.get("order") == 1 and child.get("framework_id") == "ct.framework.cultural-imprint-engine", "CIE sequence drift")
    need(child.get("repo_id") == "ct.repo.cie" and child.get("github_repository_id") == 1341314455, "child repository identity drift")
    need(bool(SHA40.fullmatch(str(child.get("child_sha", "")))), "child SHA must be exact")
    need(bool(SHA64.fullmatch(str(child.get("child_contract_sha256", "")))), "child contract digest must be SHA-256")
    need(child.get("repository_state") == "PROVISIONED_UNLINKED", "child may not be promoted by binding metadata")
    need(child.get("parent_certification_agent") == "ct.relay.agent-d", "Agent D must remain parent certifier")
    need(child.get("parent_certification_state") == "PENDING", "parent certification must remain pending")

    backlink = child.get("backlink", {})
    need(backlink.get("reference_type") == "child_backlink", "canonical backlink type drift")
    need(backlink.get("source_sha") == child.get("child_sha"), "backlink source SHA must equal child SHA")
    need(backlink.get("target_sha") == parent.get("anchor_sha"), "backlink target SHA must equal parent anchor")
    need(backlink.get("runtime_registry_state") == "ACTIVE", "observed child backlink must remain active")
    need(backlink.get("evidence_class") == "OIDC_AUTHENTICATED_HASH_CHAIN_RECORDED", "backlink evidence class drift")

    transport = child.get("transport", {})
    for key in ("oidc_bootstrap_observed", "child_heartbeat_observed", "parent_provisioning_message_ack_observed", "child_return_message_observed", "child_return_message_requires_parent_ack"):
        need(transport.get(key) is True, f"missing observed pre-cert transport evidence: {key}")
    need(transport.get("parent_forward_reference_state") == "PENDING_TRUSTED_AGENT_D_RECEIPT", "parent forward reference must remain pending trusted Agent D receipt")

    for key in ("operationally_enabled", "vote_eligible", "linked_governed", "public_activation_allowed", "algorithm_authority_enabled", "sync_agents_enabled"):
        need(child.get(key) is False, f"fail-closed child authority drift: {key}")

    later = data.get("later_frameworks", [])
    need(len(later) == 7, "later framework sequence size drift")
    need([x.get("order") for x in later] == list(range(2, 9)), "later framework order drift")
    for row in later:
        need(row.get("state") == "UNPROVISIONED", f"later framework provisioned early: {row.get('framework_id')}")
        need(row.get("implementation_unlocked") is False and row.get("vote_eligible") is False, "later framework authority drift")

    guards = data.get("authority_guards", {})
    for key in ("agent_d_mandatory", "d3_human_reserved", "transport_identity_non_voting", "repository_identity_non_voting", "sync_agents_only_governed_non_voting_d0_d2_transport"):
        need(guards.get(key) is True, f"authority guard missing: {key}")
    for key in ("child_self_certification", "child_self_activation", "binding_record_creates_sovereign_vote", "binding_record_certifies_child", "binding_record_marks_linked_governed", "agent_c_may_satisfy_parent_agent_d_receipt"):
        need(guards.get(key) is False, f"fail-closed authority guard drift: {key}")

    ip = data.get("ip_publication", {})
    for key in ("protected_calibration_included", "private_eval_corpora_included", "credentials_or_fingerprints_included", "private_evidence_payloads_included"):
        need(ip.get(key) is False, f"protected material may not enter public binding projection: {key}")

    commercial = data.get("commercial_state", {})
    for key in ("exact_price_authorized", "stripe_product_created_by_this_binding", "stripe_price_created_by_this_binding", "checkout_enabled", "certification_status_active", "customer_entitlement_active"):
        need(commercial.get(key) is False, f"commercial authority drift: {key}")

def self_test(data: dict[str, Any]) -> None:
    mutations = []
    a = copy.deepcopy(data); a["parent_anchor"]["anchor_sha"] = "0" * 39; mutations.append(("short_parent_sha", a))
    a = copy.deepcopy(data); a["children"][0]["child_contract_sha256"] = "f" * 63; mutations.append(("short_child_digest", a))
    a = copy.deepcopy(data); a["children"][0]["backlink"]["target_sha"] = "1" * 40; mutations.append(("backlink_target_mismatch", a))
    a = copy.deepcopy(data); a["children"][0]["operationally_enabled"] = True; mutations.append(("premature_operational", a))
    a = copy.deepcopy(data); a["children"][0]["vote_eligible"] = True; mutations.append(("premature_vote", a))
    a = copy.deepcopy(data); a["children"][0]["transport"]["parent_forward_reference_state"] = "ACTIVE"; mutations.append(("forged_parent_receipt", a))
    for name, candidate in mutations:
        try:
            validate(candidate)
        except ValidationError:
            continue
        raise ValidationError(f"negative case unexpectedly passed: {name}")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    path = args.root / "developers/manifests/framework-agent-transport-inventory.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    validate(data)
    if args.self_test:
        self_test(data)
    print("CIE pre-cert binding validation PASS: exact parent anchor + child digest + active child backlink; parent D receipt pending; non-operational/non-voting.")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        raise SystemExit(f"ERROR: {exc}")
