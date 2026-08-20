#!/usr/bin/env python3
"""CrownThrive Framework Factory deterministic planner and validator.

The factory prepares the next bounded framework packet. It does not create
sovereign authority, create repositories, bypass parent certification, or infer
missing evidence. Provider writes remain separate governed actions.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"developers/manifests/framework-factory.v1.json"
FEDERATION=ROOT/"developers/manifests/repository-federation.v1.json"
AGENT_BINDINGS=ROOT/"developers/manifests/agent-federation-bindings.v1.json"
FRAMEWORK_REGISTRY=ROOT/"doctrine/framework-engine-registry.mdx"
LIFECYCLE=["SOURCE_DISCOVERY","IDENTITY_RECONCILIATION","DOCTRINE_NORMALIZATION","AGENT_SCAFFOLD","ALGORITHM_CONTRACT","ETHICS_BOUNDARY","CHLOM_MAPPING","EVALS_TEVV","REPOSITORY_PLAN","FEDERATION_BOOTSTRAP","CONTROLLED_TEST","SOVEREIGN_SPECIALIST_REVIEW","GOVERNED_FRAMEWORK_ACCEPTANCE","CHILD_CERTIFICATION","RETROACTIVE_SCAN","PRODUCTION_LIMITED","MAINTAINED"]


def fail(message:str)->None: raise SystemExit(f"ERROR: {message}")
def load(path:Path)->dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): fail(f"{path.name}: object required")
    return value


def quorum_required(voters:int,ratio:float=0.75)->int:
    if voters<1: fail("eligible voter count must be positive")
    return math.ceil(voters*ratio)


def participation_contract()->dict[str,Any]:
    bindings=load(AGENT_BINDINGS)
    rules=bindings.get("rules",{})
    if rules.get("framework_factory_participation_required") is not True: fail("all-agent Framework Factory participation contract missing")
    if rules.get("sync_agents_callers_must_be_non_voting") is not True: fail("sync_agents caller non-voting invariant missing")
    sync_callers=set(rules.get("non_voting_inventory_sync_agents",[]))
    sovereign={x.get("agent_id") for x in bindings.get("parent_sovereign_bindings",[])}
    if sync_callers!={"ct.subagent.governance-marshal"} or sync_callers & sovereign: fail("sync_agents must be owned only by governed non-voting D0-D2 transport")
    contract=bindings.get("factory_participation_contract",{})
    if contract.get("framework_identity_default_vote_state")!="non_voting": fail("framework default vote state drift")
    if contract.get("delegated_builder_children")!="non_voting_and_cannot_independently_verify_c_originated_work": fail("builder-child verification boundary drift")
    return contract


def validate_manifest(data:dict[str,Any])->None:
    if data.get("manifest_id")!="ct.manifest.framework-factory.v1": fail("framework factory manifest identity drift")
    if data.get("program_authority_issue")!=148: fail("founder program authority must remain issue #148")
    if data.get("canonical_parent_repository")!="crownthrive1/CrownThrive-Support": fail("canonical parent repository drift")
    inv=data.get("constitutional_invariants",{})
    if inv.get("current_sovereign_voters")!=5 or inv.get("current_minimum_approvals")!=4: fail("current constitution must remain five voters / four approvals")
    for key in ("agent_d_mandatory","deny_or_block_prevents_automatic_merge","missing_or_abstain_never_approves","d3_human_reserved","framework_identity_acceptance_does_not_create_vote","framework_sovereign_vote_requires_separate_constitutional_acceptance","framework_subagents_non_voting","transport_messages_non_voting","repository_identity_non_voting","child_self_activation_prohibited","child_self_certification_prohibited","factory_cannot_change_approval_ratio","factory_cannot_remove_agent_d","factory_cannot_self_authorize_unenumerated_constitutional_framework"):
        if inv.get(key) is not True: fail(f"constitutional invariant missing: {key}")
    repo=data.get("repository_baseline",{})
    for key in ("parent_certification_required","bidirectional_reference_required","message_ack_lifecycle_required","heartbeat_required","hash_chained_events_required","inherited_governance_required","inherited_security_required","restricted_algorithm_material_in_public_repo_prohibited","approved_private_runtime_required_for_proprietary_calibration"):
        if repo.get(key) is not True: fail(f"repository baseline missing: {key}")
    if repo.get("child_operational_before_linked_governed") is not False or repo.get("child_vote_before_separate_acceptance_and_certification") is not False: fail("child operational/vote state must remain fail-closed")
    baseline=data.get("framework_agent_baseline",{})
    if baseline.get("minimum_institutionalization_score")!=85 or baseline.get("algorithm_public_contract_private_calibration_split") is not True or baseline.get("framework_override_is_permission_escalation") is not False: fail("framework baseline drift")
    sequence=data.get("authorized_framework_sequence",[])
    if len(sequence)!=8: fail("authorized framework sequence must contain eight frameworks")
    seen=set()
    for idx,item in enumerate(sequence,1):
        if item.get("order")!=idx: fail(f"framework order drift at {idx}")
        fid=item.get("framework_id")
        if not str(fid).startswith("ct.framework.") or fid in seen: fail("invalid/duplicate framework identity")
        seen.add(fid)
        if item.get("current_vote_state")!="non_voting": fail(f"framework must remain non-voting in factory packet: {fid}")
    if sequence[0].get("framework_id")!="ct.framework.cultural-imprint-engine" or sequence[1].get("framework_id")!="ct.framework.convergent-ecosystem": fail("framework sequence drift")
    if not FEDERATION.is_file() or not FRAMEWORK_REGISTRY.is_file() or not AGENT_BINDINGS.is_file(): fail("repository federation, agent bindings or framework registry missing")
    text=FRAMEWORK_REGISTRY.read_text(encoding="utf-8")
    for fid in seen:
        if fid not in text: fail(f"framework not present in registry: {fid}")
    participation_contract()


def implementation_backed_research_candidates()->list[dict[str,Any]]:
    rows=participation_contract().get("implementation_backed_research_candidates",[])
    if not isinstance(rows,list): fail("implementation-backed research candidates must be a list")
    for row in rows:
        if not isinstance(row,dict) or row.get("candidate_state")!="RESEARCH_CANDIDATE" or row.get("vote_state")!="non_voting" or row.get("framework_implementation_allowed_now") is not False:
            fail("research candidate promotion boundary drift")
    return rows


def next_candidate(data:dict[str,Any])->dict[str,Any]:
    sequence=data["authorized_framework_sequence"]; first=sequence[0]
    research=implementation_backed_research_candidates()
    if first.get("physical_child_repository_state")!="linked_governed":
        return {
            "framework_id":first["framework_id"],
            "next_safe_packet":"complete_CIE_governed_framework_acceptance_then_provision_backlink_oidc_and_parent_certify_child",
            "activation_allowed":False,
            "parallel_research_allowed_for_next":True,
            "parallel_research_framework_id":sequence[1]["framework_id"],
            "implementation_backed_research_candidates":[x["framework_id"] for x in research],
            "implementation_of_next_allowed":False,
            "blocking_reason":"CIE child repository is not linked_governed"
        }
    return {
        "framework_id":sequence[1]["framework_id"],
        "next_safe_packet":"build_convergent_ecosystem_source_and_doctrine_reconciliation_packet",
        "activation_allowed":False,
        "implementation_backed_research_candidates":[x["framework_id"] for x in research],
        "implementation_of_next_allowed":True,
        "blocking_reason":"candidate must progress through factory lifecycle and governed acceptance"
    }


def plan_for(data:dict[str,Any],framework_id:str)->dict[str,Any]:
    item=next((x for x in data["authorized_framework_sequence"] if x["framework_id"]==framework_id),None)
    if item is not None:
        return {"framework_id":item["framework_id"],"canonical_name":item["canonical_name"],"framework_agent_id":item["framework_agent_id"],"child_repo_candidate":item["child_repo_candidate"],"current_state":item["current_state"],"current_vote_state":"non_voting","sovereign_vote_activation":"separate_constitutional_packet_required","agent_d_mandatory":True,"d3_human_reserved":True,"child_self_activation":False,"required_artifacts":data["framework_agent_baseline"]["required_artifacts"],"lifecycle":LIFECYCLE,"promotion_semantics":"framework_acceptance_and_child_certification_do_not_by_themselves_create_sovereign_vote"}
    research=next((x for x in implementation_backed_research_candidates() if x.get("framework_id")==framework_id),None)
    if research is None: fail("framework is not in authorized sequence or implementation-backed research candidates")
    return {
        "framework_id":framework_id,
        "current_state":research["candidate_state"],
        "evidence_maturity":research["evidence_maturity"],
        "existing_agent_id":research["existing_agent_id"],
        "current_vote_state":"non_voting",
        "research_preparation_allowed_now":True,
        "framework_implementation_allowed_now":False,
        "implementation_gate":research["implementation_gate"],
        "sovereign_vote_activation":"separate_constitutional_packet_required",
        "agent_d_mandatory":True,
        "d3_human_reserved":True
    }


def self_test(data:dict[str,Any])->None:
    validate_manifest(data); assert quorum_required(5)==4
    nxt=next_candidate(data); assert nxt["framework_id"]=="ct.framework.cultural-imprint-engine" and nxt["implementation_of_next_allowed"] is False
    plan=plan_for(data,"ct.framework.convergent-ecosystem"); assert plan["current_vote_state"]=="non_voting" and plan["child_self_activation"] is False
    cii=plan_for(data,"ct.framework.cii-thrivefund"); assert cii["current_state"]=="RESEARCH_CANDIDATE" and cii["evidence_maturity"]=="implementation_backed" and cii["framework_implementation_allowed_now"] is False


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--validate",action="store_true"); ap.add_argument("--self-test",action="store_true"); ap.add_argument("--next",action="store_true"); ap.add_argument("--plan"); args=ap.parse_args(); data=load(MANIFEST)
    if args.self_test:
        self_test(data); print("Framework Factory self-test PASS: eight sequential implementation candidates; A/B/C/D/S constitution preserved; all-agent participation bound; sync_agents non-voting transport only; CII implementation-backed research preparation allowed without leapfrog."); return 0
    validate_manifest(data)
    if args.next: print(json.dumps(next_candidate(data),indent=2,sort_keys=True)); return 0
    if args.plan: print(json.dumps(plan_for(data,args.plan),indent=2,sort_keys=True)); return 0
    print("Framework Factory manifest validation PASS")
    return 0
if __name__=="__main__": raise SystemExit(main())
