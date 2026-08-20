#!/usr/bin/env python3
"""Validate CrownThrive parent-child repository federation, agent binding and IP boundaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FEDERATION = ROOT / "developers/manifests/repository-federation.v1.json"
AGENT_BINDINGS = ROOT / "developers/manifests/agent-federation-bindings.v1.json"
ALGORITHMS = ROOT / "developers/manifests/framework-algorithm-registry.v1.json"
FRAMEWORK_FACTORY = ROOT / "developers/manifests/framework-factory.v1.json"
CHILD_TEMPLATE = ROOT / "developers/templates/framework-child-federation-contract.v1.json"
FEDERATION_CLIENT = ROOT / "scripts/repository_federation_sync.py"
CIE_CLIENT = ROOT / "scripts/cie_scan.py"
FEDERATION_DOC = ROOT / "technology/repository-federation-control-plane.mdx"
FRAMEWORK_REPO_DOC = ROOT / "automation/framework-repository-governance-standard.mdx"
FEDERATION_WORKFLOW = ROOT / ".github/workflows/repository-federation-governance.yml"

REQUIRED_PARENT_LOCKS = {
    "constitutional_governance", "d3_human_authority", "security_privacy",
    "rights_legal", "money_movement", "repository_federation",
    "vault_secret_policy", "phase_hard_gates",
}
SEALED_PUBLIC_FORBIDDEN = {
    "severity_deductions", "confidence_multipliers", "recurrence_multipliers",
    "calibration_weights", "private_eval_corpora", "proprietary_detection_rules",
}
EXPECTED_CIE_CONTRACT_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"
EXPECTED_PARENT_VOTERS = {
    "ct.relay.agent-a", "ct.relay.agent-b", "ct.relay.agent-c",
    "ct.relay.agent-d", "ct.relay.agent-s",
}
EXPECTED_CIE_CHILD_AGENTS = {
    "ct.framework-agent.cie",
    "ct.subagent.cie.identity-fit", "ct.subagent.cie.community-value",
    "ct.subagent.cie.story-alignment", "ct.subagent.cie.brand-safety",
    "ct.subagent.cie.legacy-impact", "ct.subagent.cie.remediation-escalation",
}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load(path: Path) -> Any:
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key)); keys.update(walk_keys(item))
    elif isinstance(value, list):
        for item in value: keys.update(walk_keys(item))
    return keys


def public_contract_digest(contract: dict[str, Any]) -> str:
    rendered = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def main() -> int:
    fed = load(FEDERATION)
    bindings = load(AGENT_BINDINGS)
    alg = load(ALGORITHMS)
    factory = load(FRAMEWORK_FACTORY)
    load(CHILD_TEMPLATE)

    if fed.get("manifest_id") != "ct.manifest.repository-federation.v1": fail("federation manifest identity drift")
    authority = fed.get("authority", {})
    if authority.get("canonical_parent_repository") != "crownthrive1/CrownThrive-Support": fail("canonical parent repository drift")
    if authority.get("framework_factory_program_authority_issue") != 148: fail("Framework Factory founder authority issue drift")
    if authority.get("framework_factory_manifest") != "developers/manifests/framework-factory.v1.json": fail("Framework Factory manifest linkage drift")
    if authority.get("child_repository_self_activation") is not False or authority.get("parent_certification_required") is not True: fail("child self-activation must remain prohibited and parent certification mandatory")
    if authority.get("d3_human_reserved") is not True: fail("repository federation cannot create D3 authority")
    if factory.get("program_authority_issue") != 148: fail("federation/factory authority mismatch")

    runtime = fed.get("runtime", {})
    auth = runtime.get("auth", {})
    if runtime.get("edge_function_version") != 3: fail("repository federation Edge Function must remain v3 for agent-bound contract")
    if auth.get("scheme") != "github_actions_oidc": fail("federation must use GitHub Actions OIDC")
    if auth.get("issuer") != "https://token.actions.githubusercontent.com": fail("GitHub OIDC issuer drift")
    if auth.get("audience") != "crownthrive-repository-federation": fail("GitHub OIDC audience drift")
    if auth.get("long_lived_shared_secret_required") is not False: fail("repository federation cannot require a long-lived shared repository secret")

    agent_identity = fed.get("agent_identity", {})
    if agent_identity.get("binding_manifest") != "developers/manifests/agent-federation-bindings.v1.json": fail("agent binding manifest drift")
    if agent_identity.get("private_binding_registry") != "institutional_federation.repository_agent_bindings": fail("private agent binding registry drift")
    for key in ("repository_oidc_plus_agent_binding_required", "agent_claim_by_string_prefix_only_prohibited", "pull_is_agent_scoped", "non_voting_sync_can_create_vote"):
        expected = False if key == "non_voting_sync_can_create_vote" else True
        if agent_identity.get(key) is not expected: fail(f"agent identity invariant drift: {key}")
    if agent_identity.get("child_certification_agent") != "ct.relay.agent-d": fail("child certification must remain Agent-D-only")
    if set(agent_identity.get("future_agent_sync_authority", [])) != {"ct.relay.agent-a", "ct.subagent.governance-marshal"}: fail("future non-voting agent sync authority drift")

    if bindings.get("manifest_id") != "ct.manifest.agent-federation-bindings.v1": fail("agent federation binding manifest identity drift")
    rules = bindings.get("rules", {})
    for key in ("repository_oidc_identity_required", "agent_repository_binding_required", "transport_identity_does_not_create_vote", "non_voting_sync_may_not_create_vote", "framework_subagents_non_voting", "child_framework_agents_prospective_until_certified", "child_transport_disabled_until_parent_certification"):
        if rules.get(key) is not True: fail(f"binding rule missing: {key}")
    if rules.get("child_certification_agent") != "ct.relay.agent-d": fail("binding inventory child certifier drift")
    if set(rules.get("non_voting_inventory_sync_agents", [])) != {"ct.relay.agent-a", "ct.subagent.governance-marshal"}: fail("binding inventory sync authority drift")

    parent_voters = bindings.get("parent_sovereign_bindings", [])
    voter_ids = {item.get("agent_id") for item in parent_voters}
    if voter_ids != EXPECTED_PARENT_VOTERS or len(parent_voters) != 5: fail("parent sovereign binding set drift")
    if any(item.get("vote_eligible") is not True for item in parent_voters): fail("all parent sovereign bindings must be vote eligible")
    certifiers = {item.get("agent_id") for item in parent_voters if item.get("certify_child") is True}
    if certifiers != {"ct.relay.agent-d"}: fail("Agent D must be the sole child certifier")

    non_voting = bindings.get("parent_non_voting_transport_bindings", [])
    non_voting_ids = [item.get("agent_id") for item in non_voting]
    if len(non_voting_ids) != len(set(non_voting_ids)) or not non_voting_ids: fail("non-voting transport binding set invalid")
    if any(item.get("vote_eligible") is True for item in non_voting): fail("non-voting transport sync cannot create votes")
    if "ct.agent.framework-factory" not in set(non_voting_ids): fail("Framework Factory orchestrator transport binding missing")
    for legacy in {"ct.agent.rights-governance", "ct.agent.publishing", "ct.agent.commerce", "ct.agent.website-release", "ct.agent.growth-analytics", "ct.agent.support", "ct.agent.qa-security"}:
        if legacy not in set(non_voting_ids): fail(f"legacy role federation identity missing: {legacy}")

    prospective = bindings.get("prospective_cie_child_bindings", [])
    prospective_ids = {item.get("agent_id") for item in prospective}
    if prospective_ids != EXPECTED_CIE_CHILD_AGENTS: fail("prospective CIE child binding set drift")
    parent_cie = next(item for item in prospective if item.get("agent_id") == "ct.framework-agent.cie")
    if parent_cie.get("vote_eligible") is not True or parent_cie.get("binding_state") != "prospective" or parent_cie.get("bootstrap_enabled") is not True: fail("prospective CIE parent binding drift")
    if any(item.get("vote_eligible") is not False for item in prospective if item.get("agent_id") != "ct.framework-agent.cie"): fail("CIE subagents must remain non-voting")

    sync = bindings.get("future_sync_contract", {})
    if sync.get("operation") != "repository_federation.sync_agents" or sync.get("sync_can_create_sovereign_vote") is not False: fail("non-voting sync contract drift")
    if set(sync.get("allowed_authority_ceiling", [])) != {"D0", "D1", "D2"}: fail("agent sync D3 prohibition drift")

    if set(fed.get("parent_lock_keys", [])) != REQUIRED_PARENT_LOCKS: fail("parent lock-key set drift")
    child_policy = fed.get("framework_child_policy", {})
    for key in ("may_override_parent_lock_keys", "may_change_quorum", "may_self_add_vote", "may_self_certify", "may_create_d3_authority", "transport_messages_create_votes", "framework_subagents_create_votes"):
        if child_policy.get(key) is not False: fail(f"framework-child non-negotiable drift: {key}")
    if child_policy.get("all_governed_agents_transport_access") != "only_when_explicitly_bound_to_repository_and_capability": fail("agent transport must be explicit-binding based")
    if child_policy.get("bidirectional_reference_required") is not True: fail("bidirectional repository references required")
    if child_policy.get("child_backlink_file") != ".crownthrive/federation.json": fail("child backlink path drift")

    repos = {item.get("repo_id"): item for item in fed.get("repositories", [])}
    if set(repos) != {"ct.repo.crownthrive-support", "ct.repo.cie"}: fail("unexpected current federation repository set")
    parent = repos["ct.repo.crownthrive-support"]; child = repos["ct.repo.cie"]
    if parent.get("role") != "canonical_parent" or parent.get("github_repository_id") != 1336348391 or parent.get("operationally_enabled") is not True: fail("canonical parent identity/state drift")
    if child.get("repo_full_name") != "crownthrive1/CrownThrive-CIE" or child.get("parent_repo_id") != parent.get("repo_id"): fail("CIE parent-child identity drift")
    if child.get("github_repository_id") is None:
        if child.get("governance_state") != "pending_provisioning" or child.get("operationally_enabled") is not False: fail("unprovisioned CIE child must remain pending and disabled")
        if child.get("backlink_state") != "blocked_repo_not_provisioned": fail("missing CIE repository must expose backlink block")
    elif child.get("governance_state") != "linked_governed" and child.get("operationally_enabled") is not False:
        fail("non-certified child cannot be operational")

    if fed.get("cross_chain", {}).get("per_repository_previous_hash_link") is not True: fail("cross-repository event hash chain required")
    if fed.get("cross_chain", {}).get("public_repository_stores_private_event_payloads") is not False: fail("private federation event payloads cannot be projected public")

    mcp_tools = set(fed.get("mcp", {}).get("tools", []))
    for tool in {"repository_federation.heartbeat", "repository_federation.publish", "repository_federation.pull", "repository_federation.ack", "repository_federation.reference", "repository_federation.sync_agents", "cie.score"}:
        if tool not in mcp_tools: fail(f"federation MCP contract missing: {tool}")

    algorithm_rows = alg.get("algorithms", [])
    if len(algorithm_rows) != 1: fail("expected one current framework algorithm")
    cie = algorithm_rows[0]
    if cie.get("algorithm_id") != "ct.algorithm.cie.v1" or cie.get("framework_id") != "ct.framework.cultural-imprint-engine": fail("CIE algorithm identity drift")
    contract = cie.get("public_contract", {})
    if public_contract_digest(contract) != EXPECTED_CIE_CONTRACT_DIGEST: fail("CIE public contract digest drift")
    if cie.get("public_contract_digest") != EXPECTED_CIE_CONTRACT_DIGEST: fail("CIE registered public contract digest drift")
    if cie.get("classification") != "RESTRICTED_INSTITUTIONAL": fail("CIE algorithm implementation must remain restricted")
    if cie.get("vault_policy_ref") != "vault:ct.algorithm.cie.v1.policy_bundle": fail("CIE Vault runtime reference drift")
    if set(cie.get("sealed_fields_not_public", [])) != SEALED_PUBLIC_FORBIDDEN: fail("sealed CIE field list drift")
    if walk_keys(alg) & SEALED_PUBLIC_FORBIDDEN: fail("sealed CIE calibration appeared as public manifest keys")
    if fed.get("algorithms", {}).get("eligible_algorithm_invocation_requires_agent_binding") is not True: fail("algorithm invocation must require agent binding")

    client_text = FEDERATION_CLIENT.read_text(encoding="utf-8"); cie_text = CIE_CLIENT.read_text(encoding="utf-8")
    forbidden_static = "SUPABASE_" + "SERVICE_ROLE_KEY"
    if forbidden_static in client_text or forbidden_static in cie_text: fail("public federation/CIE client contains a service-role secret reference")
    if '"sync-agents"' not in client_text or '"agent_id": agent_id, "limit"' not in client_text: fail("public federation client missing agent-scoped pull/non-voting sync")
    for token in ("SEVERITY_DEDUCTIONS", "confidence_multipliers", "recurrence_multipliers"):
        if token in cie_text: fail(f"public CIE client exposes protected calibration: {token}")

    live_controls = fed.get("live_negative_controls", {})
    for key in ("unbound_agent_heartbeat", "agent_a_child_certification", "agent_d_child_certification_without_physical_child", "prospective_cie_bootstrap_capability", "prospective_cie_publish_capability"):
        if not live_controls.get(key): fail(f"live negative-control disposition missing: {key}")

    for path in (FEDERATION_DOC, FRAMEWORK_REPO_DOC, FEDERATION_WORKFLOW):
        if not path.is_file(): fail(f"missing federation institutional surface: {path.relative_to(ROOT)}")

    readiness = 92
    verdict = "AGENT_BOUND_CONTROL_PLANE_PASS_CHILD_LINK_BLOCKED"
    if child.get("github_repository_id") is not None and child.get("governance_state") == "linked_governed" and child.get("backlink_state") == "verified":
        readiness = 100; verdict = "FEDERATION_LINK_PASS"
    print(f"Repository federation validation PASS: readiness={readiness}/100; verdict={verdict}; OIDC + repository-agent capability binding; Agent-D-only child certification; Vault algorithm boundary; child self-activation prohibited.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
