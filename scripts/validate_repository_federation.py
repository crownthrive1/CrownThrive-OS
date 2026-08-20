#!/usr/bin/env python3
"""Validate CrownThrive repository federation, non-voting bindings and protected algorithm boundary."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
FED=ROOT/"developers/manifests/repository-federation.v1.json"; BIND=ROOT/"developers/manifests/agent-federation-bindings.v1.json"; ALG=ROOT/"developers/manifests/framework-algorithm-registry.v1.json"; FACTORY=ROOT/"developers/manifests/framework-factory.v1.json"; TEMPLATE=ROOT/"developers/templates/framework-child-federation-contract.v1.json"
EXPECTED_PARENT={"ct.relay.agent-a","ct.relay.agent-b","ct.relay.agent-c","ct.relay.agent-d","ct.relay.agent-s"}
EXPECTED_CIE={"ct.framework-agent.cie","ct.subagent.cie.identity-fit","ct.subagent.cie.community-value","ct.subagent.cie.story-alignment","ct.subagent.cie.brand-safety","ct.subagent.cie.legacy-impact","ct.subagent.cie.remediation-escalation"}
EXPECTED_SYNC_CALLERS={"ct.subagent.governance-marshal"}
DIGEST="e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"
def fail(m:str)->None: raise SystemExit(f"ERROR: {m}")
def load(p:Path)->dict[str,Any]:
    if not p.is_file(): fail(f"missing {p.relative_to(ROOT)}")
    return json.loads(p.read_text(encoding="utf-8"))
def digest(c:dict[str,Any])->str: return hashlib.sha256(json.dumps(c,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def main()->int:
    fed=load(FED); bindings=load(BIND); alg=load(ALG); factory=load(FACTORY); load(TEMPLATE)
    auth=fed.get("authority",{}); runtime=fed.get("runtime",{})
    if auth.get("canonical_parent_repository")!="crownthrive1/CrownThrive-Support" or auth.get("governance_decision_current")!="CT-ADR-GOV-011": fail("canonical authority drift")
    if auth.get("child_repository_self_activation") is not False or auth.get("parent_certification_required") is not True or auth.get("d3_human_reserved") is not True: fail("child/D3 boundary drift")
    if auth.get("framework_transport_identity_is_non_voting_until_separate_acceptance") is not True: fail("framework transport vote boundary missing")
    if runtime.get("constitutional_vote_activation_guard")!="blocked_current_constitution_five_voters": fail("constitutional vote activation guard missing")
    if not str(runtime.get("canonical_parent_ref_integrity","")).startswith("blocked_"): fail("canonical parent ref integrity must remain blocked until independently bound")
    oidc=runtime.get("auth",{})
    if oidc.get("scheme")!="github_actions_oidc" or oidc.get("long_lived_shared_secret_required") is not False: fail("OIDC boundary drift")
    rules=bindings.get("rules",{})
    for key in ("repository_oidc_identity_required","agent_repository_binding_required","transport_identity_does_not_create_vote","non_voting_sync_may_not_create_vote","sync_agents_callers_must_be_non_voting","framework_subagents_non_voting","framework_parent_agent_non_voting_until_separate_constitutional_acceptance","child_transport_disabled_until_parent_certification","framework_factory_participation_required"):
        if rules.get(key) is not True: fail(f"binding rule missing: {key}")
    parents=bindings.get("parent_sovereign_bindings",[])
    if {x.get("agent_id") for x in parents}!=EXPECTED_PARENT or len(parents)!=5 or any(x.get("vote_eligible") is not True for x in parents): fail("parent sovereign bindings must remain A/B/C/D/S")
    if {x.get("agent_id") for x in parents if x.get("certify_child") is True}!={"ct.relay.agent-d"}: fail("Agent D must be sole child certifier")
    sync_callers=set(rules.get("non_voting_inventory_sync_agents",[]))
    if sync_callers!=EXPECTED_SYNC_CALLERS or sync_callers & EXPECTED_PARENT: fail("sync_agents caller must be governed non-voting transport only")
    nonvoting_ids={x.get("agent_id") for x in bindings.get("parent_non_voting_transport_bindings",[])}
    if not sync_callers <= nonvoting_ids: fail("sync_agents caller missing from non-voting transport inventory")
    participation=bindings.get("factory_participation_contract",{})
    if participation.get("framework_identity_default_vote_state")!="non_voting" or participation.get("d3")!="human_reserved": fail("factory participation authority drift")
    cii=participation.get("implementation_backed_research_candidates",[])
    if len(cii)!=1 or cii[0].get("framework_id")!="ct.framework.cii-thrivefund" or cii[0].get("existing_agent_id")!="ct.agent.impact-allocation" or cii[0].get("candidate_state")!="RESEARCH_CANDIDATE" or cii[0].get("research_preparation_allowed_now") is not True or cii[0].get("framework_implementation_allowed_now") is not False: fail("CII implementation-backed research-candidate boundary drift")
    cie=bindings.get("prospective_cie_child_bindings",[])
    if {x.get("agent_id") for x in cie}!=EXPECTED_CIE: fail("CIE binding topology drift")
    if any(x.get("vote_eligible") is not False for x in cie): fail("CIE parent/subagent bindings must remain non-voting")
    parent_cie=next(x for x in cie if x.get("agent_id")=="ct.framework-agent.cie")
    if parent_cie.get("bootstrap_enabled") is not False or parent_cie.get("binding_state")!="prospective": fail("CIE transport must remain disabled before physical child certification")
    sync=bindings.get("future_sync_contract",{})
    if sync.get("operation")!="repository_federation.sync_agents" or sync.get("calling_identity_must_be_non_voting") is not True or set(sync.get("allowed_calling_agents",[]))!=EXPECTED_SYNC_CALLERS or sync.get("sync_can_create_sovereign_vote") is not False or set(sync.get("allowed_authority_ceiling",[]))!={"D0","D1","D2"}: fail("sync_agents authority drift")
    repos={x.get("repo_id"):x for x in fed.get("repositories",[])}; child=repos.get("ct.repo.cie")
    if set(repos)!={"ct.repo.crownthrive-support","ct.repo.cie"} or not child: fail("repository set drift")
    if child.get("governance_state")!="pending_provisioning" or child.get("operationally_enabled") is not False or child.get("can_vote") is not False: fail("CIE child must remain pending/non-operational/non-voting")
    for key in ("backlink_state","oidc_bootstrap_state","parent_certification_state"):
        if child.get(key)!="blocked_repo_not_provisioned": fail(f"CIE child {key} must remain blocked")
    policy=fed.get("framework_child_policy",{})
    for key in ("may_override_parent_lock_keys","may_change_quorum","may_self_add_vote","may_self_certify","may_create_d3_authority","transport_messages_create_votes","framework_subagents_create_votes"):
        if policy.get(key) is not False: fail(f"child non-negotiable drift: {key}")
    mcp=fed.get("mcp",{})
    if mcp.get("enabled_child_tools")!=0 or mcp.get("child_tool_activation_requires_linked_governed") is not True: fail("child MCP must remain disabled")
    rows=alg.get("algorithms",[])
    if len(rows)!=1: fail("expected one CIE algorithm")
    row=rows[0]
    if row.get("algorithm_id")!="ct.algorithm.cie.v1" or row.get("classification")!="RESTRICTED_INSTITUTIONAL" or row.get("public_contract_digest")!=DIGEST or digest(row.get("public_contract",{}))!=DIGEST: fail("CIE algorithm public/restricted boundary drift")
    if "vault_policy_ref" in row or row.get("private_runtime_reference_state")!="registered_not_public": fail("private runtime locator must not be public")
    if row.get("mcp_enabled") is not False: fail("CIE MCP must remain disabled")
    if factory.get("constitutional_invariants",{}).get("current_sovereign_voters")!=5 or factory.get("constitutional_invariants",{}).get("framework_identity_acceptance_does_not_create_vote") is not True: fail("factory/current constitution mismatch")
    print("Repository federation validation PASS: A/B/C/D/S constitution preserved; sync_agents caller restricted to non-voting D0-D2 Governance Marshal; CII research preparation implementation-backed/non-voting; CIE child pending/non-operational/non-voting; protected calibration private.")
    return 0
if __name__=="__main__": raise SystemExit(main())
