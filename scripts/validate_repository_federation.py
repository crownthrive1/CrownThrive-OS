#!/usr/bin/env python3
"""Validate CrownThrive transport federation, framework packages and protected algorithms."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FED = ROOT / "developers/manifests/repository-federation.v1.json"
BIND = ROOT / "developers/manifests/agent-federation-bindings.v1.json"
ALG = ROOT / "developers/manifests/framework-algorithm-registry.v1.json"
FACTORY = ROOT / "developers/manifests/framework-factory.v1.json"
FLEET = ROOT / "developers/manifests/framework-child-fleet.v1.json"
TEMPLATE = ROOT / "developers/templates/framework-child-federation-contract.v1.json"
EXPECTED_PARENT = {"ct.relay.agent-a", "ct.relay.agent-b", "ct.relay.agent-c", "ct.relay.agent-d", "ct.relay.agent-s"}
EXPECTED_CIE = {
    "ct.framework-agent.cie",
    "ct.subagent.cie.identity-fit",
    "ct.subagent.cie.community-value",
    "ct.subagent.cie.story-alignment",
    "ct.subagent.cie.brand-safety",
    "ct.subagent.cie.legacy-impact",
    "ct.subagent.cie.remediation-escalation",
}
EXPECTED_SYNC_CALLERS = {"ct.subagent.governance-marshal"}
DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path.name}: object required")
    return value


def digest(contract: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    fed = load(FED)
    bindings = load(BIND)
    alg = load(ALG)
    factory = load(FACTORY)
    fleet = load(FLEET)
    load(TEMPLATE)

    auth = fed.get("authority", {})
    runtime = fed.get("runtime", {})
    if fed.get("manifest_version") != "2.0.0":
        fail("repository federation package model v2 required")
    if auth.get("canonical_parent_repository") != "crownthrive1/CrownThrive-Support" or auth.get("governance_decision_current") != "CT-ADR-GOV-011":
        fail("canonical authority drift")
    if auth.get("physical_child_repository_required") is not False:
        fail("physical child repository must not be a framework-package existence requirement")
    if auth.get("linked_governed_physical_child_repository_required") is not True:
        fail("linked_governed must require physical child repository")
    if auth.get("framework_package_self_activation") is not False or auth.get("parent_certification_required") is not True or auth.get("parent_certification_agent") != "ct.relay.agent-d" or auth.get("d3_human_reserved") is not True:
        fail("package/Agent-D/D3 authority boundary drift")
    if auth.get("framework_transport_identity_is_non_voting_until_separate_acceptance") is not True:
        fail("framework transport vote boundary missing")

    oidc = runtime.get("auth", {})
    if oidc.get("scheme") != "github_actions_oidc" or oidc.get("long_lived_shared_secret_required") is not False:
        fail("OIDC boundary drift")
    if oidc.get("pull_request_validation_oidc") is not False or oidc.get("trusted_runtime_oidc_only") is not True:
        fail("OIDC must be isolated from pull request validation")
    if oidc.get("workflow_ref_environment_agent_capability_binding_required") is not True:
        fail("exact workflow/ref/environment agent-capability binding requirement missing")
    if runtime.get("constitutional_vote_activation_guard") != "pass_current_machine_nonvoting_guard":
        fail("constitutional non-voting runtime guard missing")
    if runtime.get("precert_child_transport") != "bounded_provisioned_unlinked_heartbeat_pull_ack_reference_publish_to_parent_only":
        fail("pre-cert child transport contract missing")
    if not str(runtime.get("workflow_agent_authority_binding", "")).startswith("blocked_"):
        fail("broader workflow-agent authority binding must remain blocked until enforced")

    rules = bindings.get("rules", {})
    for key in (
        "repository_oidc_identity_required",
        "agent_repository_binding_required",
        "transport_identity_does_not_create_vote",
        "non_voting_sync_may_not_create_vote",
        "sync_agents_callers_must_be_non_voting",
        "framework_subagents_non_voting",
        "framework_parent_agent_non_voting_until_separate_constitutional_acceptance",
        "framework_factory_participation_required",
    ):
        if rules.get(key) is not True:
            fail(f"binding rule missing: {key}")

    parents = bindings.get("parent_sovereign_bindings", [])
    if {x.get("agent_id") for x in parents} != EXPECTED_PARENT or len(parents) != 5 or any(x.get("vote_eligible") is not True for x in parents):
        fail("parent sovereign bindings must remain A/B/C/D/S")
    if {x.get("agent_id") for x in parents if x.get("certify_child") is True} != {"ct.relay.agent-d"}:
        fail("Agent D must be sole parent certifier")

    sync_callers = set(rules.get("non_voting_inventory_sync_agents", []))
    if sync_callers != EXPECTED_SYNC_CALLERS or sync_callers & EXPECTED_PARENT:
        fail("sync_agents caller must remain governed non-voting transport only")
    nonvoting_ids = {x.get("agent_id") for x in bindings.get("parent_non_voting_transport_bindings", [])}
    if not sync_callers <= nonvoting_ids:
        fail("sync_agents caller missing from non-voting transport inventory")

    participation = bindings.get("factory_participation_contract", {})
    if participation.get("framework_identity_default_vote_state") != "non_voting" or participation.get("d3") != "human_reserved":
        fail("factory participation authority drift")
    cii = participation.get("implementation_backed_research_candidates", [])
    if len(cii) != 1 or cii[0].get("framework_id") != "ct.framework.cii-thrivefund" or cii[0].get("existing_agent_id") != "ct.agent.impact-allocation" or cii[0].get("candidate_state") != "RESEARCH_CANDIDATE" or cii[0].get("framework_implementation_allowed_now") is not False:
        fail("CII research-candidate boundary drift")

    cie_bindings = bindings.get("prospective_cie_child_bindings", [])
    if {x.get("agent_id") for x in cie_bindings} != EXPECTED_CIE:
        fail("CIE binding topology drift")
    if any(x.get("vote_eligible") is not False for x in cie_bindings):
        fail("CIE package parent/subagent bindings must remain non-voting")

    sync = bindings.get("future_sync_contract", {})
    if sync.get("operation") != "repository_federation.sync_agents" or sync.get("calling_identity_must_be_non_voting") is not True or set(sync.get("allowed_calling_agents", [])) != EXPECTED_SYNC_CALLERS or sync.get("sync_can_create_sovereign_vote") is not False or set(sync.get("allowed_authority_ceiling", [])) != {"D0", "D1", "D2"}:
        fail("sync_agents authority drift")

    repos = {x.get("repo_id"): x for x in fed.get("repositories", [])}
    parent = repos.get("ct.repo.crownthrive-support")
    child = repos.get("ct.repo.cie")
    if not parent or parent.get("role") != "canonical_parent" or not child:
        fail("transport repository inventory drift")
    if child.get("role") != "framework_child":
        fail("CIE physical repository role drift")
    if child.get("github_repository_id") != 1341314455:
        fail("CIE immutable GitHub repository ID drift")
    if child.get("governance_state") != "provisioned_unlinked" or child.get("projection_state") != "physical_provisioned_pre_cert":
        fail("CIE pre-cert repository state drift")
    if child.get("physical_repository_required") is not False or child.get("linked_governed_physical_repository_required") is not True:
        fail("package-vs-linked-governed physical repository semantics drift")
    if child.get("operationally_enabled") is not False or child.get("can_vote") is not False or child.get("parent_certification_state") != "pending":
        fail("CIE child must remain non-operational/non-voting/uncertified")
    if child.get("precert_transport_enabled") is not True:
        fail("CIE bounded pre-cert transport must be enabled")
    allowed = set(child.get("precert_transport_capabilities", []))
    if allowed != {"heartbeat", "pull", "ack", "reference", "publish_to_parent_only"}:
        fail("CIE pre-cert capability allowlist drift")

    packages = {x.get("package_id"): x for x in fed.get("framework_packages", [])}
    cie_package = packages.get("ct.framework-package.cie")
    if not cie_package:
        fail("CIE framework package missing")
    if cie_package.get("framework_id") != "ct.framework.cultural-imprint-engine" or cie_package.get("canonical_host_repo_id") != "ct.repo.crownthrive-support":
        fail("CIE package host/identity drift")
    for key in ("operationally_enabled", "public_activation_allowed", "can_vote"):
        if cie_package.get(key) is not False:
            fail(f"CIE package fail-closed state drift: {key}")
    if cie_package.get("package_state") != "controlled_test" or cie_package.get("parent_certification_state") != "pending":
        fail("CIE package certification state drift")
    if cie_package.get("linked_governed_child_repository_state") != "PROVISIONED_UNLINKED":
        fail("CIE linked-governed repository state drift")

    certification = fed.get("linked_governed_certification", {})
    for key in (
        "physical_repository_exists",
        "immutable_github_repository_id_observed",
        "child_backlink_required",
        "oidc_bootstrap_required",
        "exact_parent_child_contract_digests_required",
        "inherited_governance_security_required",
        "passing_ci_evals_required",
        "framework_agent_binding_required",
        "bidirectional_message_ack_reference_heartbeat_required",
        "rollback_recovery_required",
        "governed_framework_acceptance_required",
        "agent_d_parent_certification_required",
    ):
        if certification.get(key) is not True:
            fail(f"linked_governed certification predicate missing: {key}")
    if certification.get("current_state") != "PENDING_PRECERT_EVIDENCE_AND_GOVERNED_ACCEPTANCE":
        fail("linked_governed current state drift")

    policy = fed.get("framework_child_policy", {})
    if policy.get("child_definition") != "independently_executable_framework_package" or policy.get("physical_repository_required") is not False or policy.get("canonical_monorepo_host_allowed") is not True or policy.get("linked_governed_requires_physical_repository") is not True:
        fail("framework package/linked-governed policy drift")
    for key in (
        "may_override_parent_lock_keys",
        "may_change_quorum",
        "may_self_add_vote",
        "may_self_certify",
        "may_create_d3_authority",
        "transport_messages_create_votes",
        "framework_subagents_create_votes",
        "package_identity_creates_vote",
        "repository_identity_creates_vote",
    ):
        if policy.get(key) is not False:
            fail(f"framework package non-negotiable drift: {key}")

    mcp = fed.get("mcp", {})
    if mcp.get("enabled_framework_tools") != 0:
        fail("framework MCP must remain disabled pending bounded promotion")

    rows = alg.get("algorithms", [])
    if len(rows) != 1:
        fail("expected one CIE algorithm")
    row = rows[0]
    if row.get("algorithm_id") != "ct.algorithm.cie.v1" or row.get("implementation_package_id") != "ct.framework-package.cie" or row.get("classification") != "RESTRICTED_INSTITUTIONAL" or row.get("public_contract_digest") != DIGEST or digest(row.get("public_contract", {})) != DIGEST:
        fail("CIE algorithm public/restricted boundary drift")
    if row.get("physical_repository_required") is not False:
        fail("CIE algorithm package cannot require standalone repository")
    if "vault_policy_ref" in row or row.get("private_runtime_reference_state") != "registered_not_public":
        fail("private runtime locator must not be public")
    if row.get("mcp_enabled") is not False:
        fail("CIE MCP must remain disabled")
    if fed.get("algorithms", {}).get("parent_repository_direct_invocation_of_child_bound_algorithm_before_linked_governed") != "DENIED_EXPECTED":
        fail("pre-cert parent algorithm denial control missing")

    if factory.get("manifest_version") != "2.0.0" or factory.get("constitutional_invariants", {}).get("current_sovereign_voters") != 5 or factory.get("constitutional_invariants", {}).get("framework_package_acceptance_does_not_create_vote") is not True:
        fail("factory/current constitution package model mismatch")
    if fleet.get("child_definition") != "independently_executable_framework_package_not_physical_repository":
        fail("fleet/federation package-existence semantics mismatch")

    print(
        "Repository federation validation PASS: A/B/C/D/S preserved; Agent D mandatory; "
        "physical CIE child 1341314455 provisioned_unlinked; bounded pre-cert transport only; "
        "standalone repo optional for package existence but mandatory for linked_governed; "
        "CIE non-operational/non-voting; parent direct child-bound algorithm denial expected; protected calibration private."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
