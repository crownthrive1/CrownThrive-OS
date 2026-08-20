#!/usr/bin/env python3
"""Current-PR preflight for CT-ADR-GOV-012 with CIE as sixth voter.

This is CI-only evidence. A permanent hard block prevents this preflight from
creating sovereign merge authority.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any

from governed_merge_decision import changed_file_digest, decide, normalize_domain, required_specialists_for, trusted_changed_files_from_git
from governed_merge_decision_v2 import load_effective_policy
from governed_current_pr_preflight import classifications_for


def fixture_scores() -> dict[str, int]:
    return {"evidence_quality":100,"validation_strength":100,"security_posture":100,"reversibility":100,"authority_fit":100}


def fixture_votes() -> list[dict[str,str]]:
    return [
        {"agent_id":"ct.relay.agent-a","vote":"approve"},
        {"agent_id":"ct.relay.agent-b","vote":"approve"},
        {"agent_id":"ct.relay.agent-c","vote":"approve"},
        {"agent_id":"ct.framework-agent.cie","vote":"approve"},
        {"agent_id":"ct.relay.agent-d","vote":"approve"},
    ]


def build_packet(files:set[str], classes:list[dict[str,Any]], domains:set[str], specialists:set[str])->dict[str,Any]:
    return {
        "risk_class":"D2",
        "scores":fixture_scores(),
        "votes":fixture_votes(),
        "changed_files":sorted(files),
        "domain_classifications":classes,
        "changed_domains":sorted(domains),
        "specialist_endorsements":sorted(specialists),
        "hard_blocks":["ci_operational_preflight_non_sovereign_authority"],
    }


def assert_positive(result:dict[str,Any])->None:
    if result.get("eligible_voters") != 6 or result.get("minimum_approvals") != 5:
        raise SystemExit("ERROR: v2 preflight did not use six-voter/five-approval constitution")
    if result.get("trusted_changed_files_bound") is not True:
        raise SystemExit("ERROR: trusted diff not bound")
    if result.get("domain_classification_errors") or result.get("specialist_endorsement_errors") or result.get("missing_specialists"):
        raise SystemExit("ERROR: preflight classification/specialist failure: "+json.dumps(result,sort_keys=True))
    if result.get("agent_auto_merge_authorized") is not False:
        raise SystemExit("ERROR: CI preflight must never authorize sovereign merge")
    if "ci_operational_preflight_non_sovereign_authority" not in result.get("hard_blocks",[]):
        raise SystemExit("ERROR: permanent CI hard block missing")


def negative_tests(packet:dict[str,Any], trusted:set[str], policy:dict[str,Any], required:set[str])->None:
    # Four approvals cannot meet six-voter quorum.
    p=json.loads(json.dumps(packet)); p["votes"]=fixture_votes()[:4]
    r=decide(p,policy,trusted)
    if r.get("agent_auto_merge_authorized") is not False or r.get("minimum_approvals") != 5:
        raise SystemExit("ERROR: four-vote negative failed")
    # Agent D remains mandatory even with five other approvals.
    p=json.loads(json.dumps(packet)); p["votes"]=[
        {"agent_id":"ct.relay.agent-a","vote":"approve"},
        {"agent_id":"ct.relay.agent-b","vote":"approve"},
        {"agent_id":"ct.relay.agent-c","vote":"approve"},
        {"agent_id":"ct.framework-agent.cie","vote":"approve"},
        {"agent_id":"ct.relay.agent-s","vote":"approve"},
    ]
    r=decide(p,policy,trusted)
    if "independent_gatekeeper_approval_missing" not in r.get("reasons",[]):
        raise SystemExit("ERROR: Agent D negative failed")
    # CIE subagent can never substitute for CIE parent vote.
    p=json.loads(json.dumps(packet)); p["votes"]=fixture_votes()+[{"agent_id":"ct.subagent.cie.identity-fit","vote":"approve"}]
    r=decide(p,policy,trusted)
    if not any("ct.subagent.cie.identity-fit" in x for x in r.get("reasons",[])):
        raise SystemExit("ERROR: CIE subagent vote was not rejected")
    # Each required specialist remains fail-closed.
    for specialist in sorted(required):
        p=json.loads(json.dumps(packet)); p["specialist_endorsements"]=sorted(required-{specialist})
        r=decide(p,policy,trusted)
        if specialist not in r.get("missing_specialists",[]):
            raise SystemExit(f"ERROR: missing specialist negative failed: {specialist}")
    # Omitting any trusted changed file must fail binding.
    if trusted:
        omitted=sorted(trusted)[0]
        p=json.loads(json.dumps(packet)); p["changed_files"]=[x for x in p["changed_files"] if x!=omitted]; p["domain_classifications"]=[x for x in p["domain_classifications"] if x.get("path")!=omitted]
        reduced=set()
        for item in p["domain_classifications"]:
            reduced.update(normalize_domain(x) for x in item.get("domains",[]))
        p["changed_domains"]=sorted(reduced); p["specialist_endorsements"]=sorted(required_specialists_for(reduced,policy))
        r=decide(p,policy,trusted)
        if not any(x.startswith("changed_files_trusted_diff_mismatch") for x in r.get("domain_classification_errors",[])):
            raise SystemExit("ERROR: omitted-file negative failed")


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--git-base",required=True); ap.add_argument("--git-head",required=True); args=ap.parse_args()
    policy=load_effective_policy(); trusted=trusted_changed_files_from_git(args.git_base,args.git_head)
    classes,domains=classifications_for(trusted,policy)
    # CIE itself is required for cultural-imprint domain material, while normal specialist sets remain cumulative.
    specialists=required_specialists_for(domains,policy)
    packet=build_packet(trusted,classes,domains,specialists)
    result=decide(packet,policy,trusted); assert_positive(result); negative_tests(packet,trusted,policy,specialists)
    print(json.dumps({
        "state":"PASS_NON_SOVEREIGN_PREFLIGHT",
        "trusted_changed_files_count":len(trusted),
        "trusted_changed_files_digest":changed_file_digest(trusted),
        "eligible_voters":6,
        "minimum_approvals":5,
        "agent_d_mandatory":True,
        "cie_framework_voter":"ct.framework-agent.cie",
        "required_specialists":sorted(specialists),
        "derived_changed_domains":sorted(domains),
    },indent=2,sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
