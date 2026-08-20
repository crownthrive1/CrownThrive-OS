#!/usr/bin/env python3
"""Candidate framework-governance guard layered on current CT-ADR-GOV-011.

This module deliberately keeps the effective sovereign voter pool at A/B/C/D/S.
The CIE framework agent remains non-voting unless a later, separate constitutional
acceptance packet becomes canonical and the child repository is linked-governed.
"""
from __future__ import annotations
import argparse, copy, json
from pathlib import Path
import governed_merge_decision as v1

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"developers/manifests/agent-sovereign-governance.v1.json"
OVERLAY=ROOT/"developers/manifests/agent-sovereign-governance.v2.json"
CIE_PATH_RULES=[
 {"path":"developers/manifests/cie-framework-agent.v1.json","required_domains":["cultural_imprint","agent"]},
 {"path":"developers/manifests/agent-sovereign-governance.v2.json","required_domains":["cultural_imprint","agent","security"]},
 {"path":"scripts/cie_scan.py","required_domains":["cultural_imprint","agent","llm"]},
 {"path":"scripts/validate_cie_framework_agent.py","required_domains":["cultural_imprint","agent","llm"]},
 {"path":"scripts/governed_merge_decision_v2.py","required_domains":["cultural_imprint","agent","security"]},
 {"path":"scripts/validate_agent_sovereign_governance_v2.py","required_domains":["cultural_imprint","agent","security"]},
 {"path":"scripts/governed_current_pr_preflight_v2.py","required_domains":["cultural_imprint","agent","security"]},
 {"path":"doctrine/cultural-imprint-engine.mdx","required_domains":["cultural_imprint","documentation"]},
 {"path":"automation/cie-framework-agent.mdx","required_domains":["cultural_imprint","documentation","agent"]},
 {"path":"automation/framework-agent-registry.mdx","required_domains":["cultural_imprint","documentation","agent"]},
 {"path":"automation/institutional-agent-relay-v2.mdx","required_domains":["cultural_imprint","documentation","agent"]},
 {"path":"automation/permissions-and-approval-gates.mdx","required_domains":["cultural_imprint","documentation","agent","security"]},
 {"path":"chlom/cie-cultural-governance-pallet.mdx","required_domains":["cultural_imprint","documentation","rights"]},
]

def load_effective_policy()->dict:
    policy=copy.deepcopy(v1.load_json(BASE)); overlay=v1.load_json(OVERLAY)
    if overlay.get("proposal_state")!="candidate_not_accepted" or overlay.get("effective_by_this_packet") is not False:
        raise ValueError("candidate_constitution_must_remain_dormant")
    if overlay.get("current_constitution")!="CT-ADR-GOV-011": raise ValueError("current_constitution_drift")
    additions=overlay.get("candidate_voter_pool_additions",[])
    if any(x.get("vote_eligible") is not False for x in additions): raise ValueError("candidate_framework_vote_must_remain_disabled")
    contract=policy["changed_domain_contract"]
    if "cultural_imprint" not in contract.setdefault("neutral_domains",[]): contract["neutral_domains"].append("cultural_imprint")
    contract.setdefault("path_domain_rules",[]).extend(CIE_PATH_RULES)
    policy["framework_candidate_guard"]=overlay
    return policy

def self_test(policy:dict)->None:
    scores={"evidence_quality":100,"validation_strength":100,"security_posture":100,"reversibility":100,"authority_fit":100}
    four_yes=[{"agent_id":"ct.relay.agent-a","vote":"approve"},{"agent_id":"ct.relay.agent-b","vote":"approve"},{"agent_id":"ct.relay.agent-c","vote":"approve"},{"agent_id":"ct.relay.agent-d","vote":"approve"}]
    ok=v1.decide({"risk_class":"D0","scores":scores,"votes":four_yes,"specialist_endorsements":[],"hard_blocks":[]},policy)
    assert ok["eligible_voters"]==5 and ok["minimum_approvals"]==4 and ok["agent_auto_merge_authorized"] is True
    cie_vote=four_yes+[{"agent_id":"ct.framework-agent.cie","vote":"approve"}]
    r=v1.decide({"risk_class":"D0","scores":scores,"votes":cie_vote,"specialist_endorsements":[],"hard_blocks":[]},policy)
    assert r["agent_auto_merge_authorized"] is False and any("ct.framework-agent.cie" in x for x in r.get("reasons",[]))
    no_d=[{"agent_id":"ct.relay.agent-a","vote":"approve"},{"agent_id":"ct.relay.agent-b","vote":"approve"},{"agent_id":"ct.relay.agent-c","vote":"approve"},{"agent_id":"ct.relay.agent-s","vote":"approve"}]
    r=v1.decide({"risk_class":"D0","scores":scores,"votes":no_d,"specialist_endorsements":[],"hard_blocks":[]},policy)
    assert "independent_gatekeeper_approval_missing" in r.get("reasons",[])
    d3=v1.decide({"risk_class":"D3","scores":scores,"votes":four_yes,"specialist_endorsements":[],"hard_blocks":[],"human_authorized":False},policy)
    assert d3["agent_auto_merge_authorized"] is False and "d3_human_authorization_required" in d3.get("reasons",[])
    required=v1.required_specialists_for({"cultural_imprint","rights"},policy)
    assert {"legal_regulatory","ip_rights_licensing"}.issubset(required)

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--packet",type=Path); ap.add_argument("--self-test",action="store_true"); ap.add_argument("--verify-git-diff",action="store_true"); ap.add_argument("--git-base"); ap.add_argument("--git-head"); args=ap.parse_args(); policy=load_effective_policy()
    if args.self_test:
        self_test(policy); print("Framework-governance guard PASS: current A/B/C/D/S 4-of-5 + Agent D preserved; CIE vote rejected; D3 human-reserved; CIE paths classified."); return 0
    trusted=None
    if args.git_base or args.git_head or args.verify_git_diff:
        if not args.git_base or not args.git_head: ap.error("--git-base and --git-head are both required")
        trusted=v1.trusted_changed_files_from_git(args.git_base,args.git_head)
    if args.verify_git_diff:
        print(json.dumps({"trusted_changed_files_count":len(trusted or set()),"trusted_changed_files_digest":v1.changed_file_digest(trusted or set()),"trusted_changed_files_redacted":True},indent=2,sort_keys=True))
        if not args.packet: return 0
    if not args.packet: ap.error("--packet required unless --self-test or --verify-git-diff")
    result=v1.decide(v1.load_json(args.packet),policy,trusted); print(json.dumps(result,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
