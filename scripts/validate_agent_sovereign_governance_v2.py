#!/usr/bin/env python3
"""Validate the dormant CT-ADR-GOV-012 framework-vote proposal against current CT-ADR-GOV-011."""
from __future__ import annotations
import json, math
from pathlib import Path
from governed_merge_decision_v2 import load_effective_policy, self_test as decision_self_test

ROOT=Path(__file__).resolve().parents[1]
OVERLAY=ROOT/"developers/manifests/agent-sovereign-governance.v2.json"
CIE=ROOT/"developers/manifests/cie-framework-agent.v1.json"
CIE_DOC=ROOT/"automation/cie-framework-agent.mdx"

def fail(message:str)->None: raise SystemExit(f"ERROR: {message}")
def main()->int:
    overlay=json.loads(OVERLAY.read_text(encoding="utf-8")); cie=json.loads(CIE.read_text(encoding="utf-8")); policy=load_effective_policy()
    if overlay.get("decision_id")!="CT-ADR-GOV-012" or overlay.get("proposal_state")!="candidate_not_accepted": fail("candidate constitution state drift")
    if overlay.get("current_constitution")!="CT-ADR-GOV-011" or overlay.get("effective_by_this_packet") is not False: fail("current constitution must remain CT-ADR-GOV-011")
    voters=[v for v in policy.get("voter_pool",[]) if v.get("vote_eligible") is True]
    expected={"ct.relay.agent-a","ct.relay.agent-b","ct.relay.agent-c","ct.relay.agent-d","ct.relay.agent-s"}
    if len(voters)!=5 or {v.get("agent_id") for v in voters}!=expected: fail("effective voter pool must remain A/B/C/D/S")
    q=overlay.get("quorum",{})
    if q.get("current_eligible_voters")!=5 or q.get("current_minimum_approvals")!=4 or math.ceil(5*0.75)!=4: fail("current quorum drift")
    if q.get("prospective_eligible_voters_if_separately_accepted")!=6 or q.get("prospective_minimum_approvals_if_separately_accepted")!=5: fail("prospective planning arithmetic drift")
    candidate=overlay.get("candidate_voter_pool_additions",[])
    if len(candidate)!=1 or candidate[0].get("agent_id")!="ct.framework-agent.cie" or candidate[0].get("vote_eligible") is not False: fail("CIE must remain non-voting in this packet")
    if cie.get("agent",{}).get("vote_eligible") is not False or cie.get("agent",{}).get("may_create_sovereign_vote") is not False: fail("CIE framework contract must remain non-voting")
    if any(x.get("vote_eligible") is not False for x in cie.get("subagents",[])): fail("CIE subagents must remain non-voting")
    if not CIE_DOC.is_file(): fail("CIE agent doc missing")
    decision_self_test(policy)
    print("Framework governance candidate validation PASS: current A/B/C/D/S 4-of-5 + Agent D preserved; CIE and subagents non-voting; any future vote requires separate acceptance and child certification.")
    return 0
if __name__=="__main__": raise SystemExit(main())
