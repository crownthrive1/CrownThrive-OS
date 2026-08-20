#!/usr/bin/env python3
"""Validate CT-ADR-GOV-012 foundational framework voter expansion."""
from __future__ import annotations
import json
import math
from pathlib import Path
from governed_merge_decision_v2 import load_effective_policy, self_test as decision_self_test

ROOT=Path(__file__).resolve().parents[1]
OVERLAY=ROOT/"developers/manifests/agent-sovereign-governance.v2.json"
CIE=ROOT/"developers/manifests/cie-framework-agent.v1.json"
PERMISSIONS=ROOT/"automation/permissions-and-approval-gates.mdx"
CIE_DOC=ROOT/"automation/cie-framework-agent.mdx"


def fail(message:str)->None: raise SystemExit(f"ERROR: {message}")

def main()->int:
    overlay=json.loads(OVERLAY.read_text(encoding="utf-8"))
    cie=json.loads(CIE.read_text(encoding="utf-8"))
    policy=load_effective_policy()
    if overlay.get("decision_id")!="CT-ADR-GOV-012": fail("decision id drift")
    if overlay.get("supersedes_on_acceptance")!="CT-ADR-GOV-011": fail("predecessor drift")
    if overlay.get("effective_only_after_governed_merge") is not True: fail("v2 cannot self-activate before merge")
    voters=[v for v in policy.get("voter_pool",[]) if v.get("vote_eligible") is True]
    if len(voters)!=6: fail(f"expected 6 voters, found {len(voters)}")
    ids={v.get("agent_id") for v in voters}
    expected={"ct.relay.agent-a","ct.relay.agent-b","ct.relay.agent-c","ct.relay.agent-d","ct.relay.agent-s","ct.framework-agent.cie"}
    if ids!=expected: fail("voter identities drift")
    q=policy.get("quorum",{})
    if q.get("approval_ratio")!=0.75 or q.get("rounding")!="ceil": fail("quorum ratio drift")
    if math.ceil(len(voters)*0.75)!=5 or q.get("current_minimum_approvals")!=5: fail("six-voter quorum must require five approvals")
    if q.get("quorum_cannot_override_d3") is not True: fail("D3 boundary drift")
    framework=overlay.get("foundational_framework_voter_policy",{})
    for key in ("new_framework_agent_requires_explicit_founder_authorization","new_framework_agent_requires_machine_contract","new_framework_agent_requires_independent_eval_suite","new_framework_agent_requires_parent_assignment","new_framework_agent_becomes_permanent_voter_only_after_governed_acceptance","framework_subagents_are_non_voting","agent_d_remains_mandatory","d3_remains_human_reserved","vote_multiplication_by_subagent_prohibited"):
        if framework.get(key) is not True: fail(f"framework-voter invariant missing: {key}")
    if cie.get("agent",{}).get("vote_eligible") is not True: fail("CIE voter missing")
    if any(x.get("vote_eligible") is not False for x in cie.get("subagents",[])): fail("CIE subagents must be non-voting")
    text=PERMISSIONS.read_text(encoding="utf-8")
    for fragment in ("six eligible voters", "five affirmative approvals", "ct.framework-agent.cie", "foundational framework agent"):
        if fragment not in text: fail(f"permissions doc missing {fragment!r}")
    if not CIE_DOC.is_file(): fail("CIE agent doc missing")
    decision_self_test(policy)
    print("CT-ADR-GOV-012 validation PASS: CIE is sixth permanent voter; 5-of-6 + Agent D; subagents non-voting; D3 human-reserved.")
    return 0

if __name__=="__main__": raise SystemExit(main())
