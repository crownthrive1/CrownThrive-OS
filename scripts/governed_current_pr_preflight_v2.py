#!/usr/bin/env python3
"""Current-PR CIE/framework preflight under the accepted CT-ADR-GOV-011 constitution.

This is CI-only evidence. CIE is deliberately non-voting in this packet and a
permanent hard block prevents the preflight from creating sovereign authority.
"""
from __future__ import annotations
import argparse, json
from typing import Any
from governed_merge_decision import changed_file_digest, decide, normalize_domain, required_specialists_for, trusted_changed_files_from_git
from governed_merge_decision_v2 import load_effective_policy
from governed_current_pr_preflight import classifications_for

def scores()->dict[str,int]: return {"evidence_quality":100,"validation_strength":100,"security_posture":100,"reversibility":100,"authority_fit":100}
def votes()->list[dict[str,str]]: return [{"agent_id":"ct.relay.agent-a","vote":"approve"},{"agent_id":"ct.relay.agent-b","vote":"approve"},{"agent_id":"ct.relay.agent-c","vote":"approve"},{"agent_id":"ct.relay.agent-d","vote":"approve"}]
def packet(files:set[str],classes:list[dict[str,Any]],domains:set[str],specialists:set[str])->dict[str,Any]: return {"risk_class":"D2","scores":scores(),"votes":votes(),"changed_files":sorted(files),"domain_classifications":classes,"changed_domains":sorted(domains),"specialist_endorsements":sorted(specialists),"hard_blocks":["ci_operational_preflight_non_sovereign_authority"]}
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--git-base",required=True); ap.add_argument("--git-head",required=True); args=ap.parse_args(); policy=load_effective_policy(); trusted=trusted_changed_files_from_git(args.git_base,args.git_head); classes,domains=classifications_for(trusted,policy); specialists=required_specialists_for(domains,policy); p=packet(trusted,classes,domains,specialists); r=decide(p,policy,trusted)
    if r.get("eligible_voters")!=5 or r.get("minimum_approvals")!=4: raise SystemExit("ERROR: accepted five-voter constitution not applied")
    if r.get("trusted_changed_files_bound") is not True or r.get("domain_classification_errors") or r.get("specialist_endorsement_errors") or r.get("missing_specialists"): raise SystemExit("ERROR: diff/specialist preflight failed")
    if r.get("agent_auto_merge_authorized") is not False or "ci_operational_preflight_non_sovereign_authority" not in r.get("hard_blocks",[]): raise SystemExit("ERROR: CI preflight must remain non-sovereign")
    # CIE vote must be rejected under the current constitution.
    p2=json.loads(json.dumps(p)); p2["votes"].append({"agent_id":"ct.framework-agent.cie","vote":"approve"}); r2=decide(p2,policy,trusted)
    if not any("ct.framework-agent.cie" in x for x in r2.get("reasons",[])): raise SystemExit("ERROR: CIE vote was not rejected")
    # Agent D remains mandatory.
    p3=json.loads(json.dumps(p)); p3["votes"]=[{"agent_id":"ct.relay.agent-a","vote":"approve"},{"agent_id":"ct.relay.agent-b","vote":"approve"},{"agent_id":"ct.relay.agent-c","vote":"approve"},{"agent_id":"ct.relay.agent-s","vote":"approve"}]; r3=decide(p3,policy,trusted)
    if "independent_gatekeeper_approval_missing" not in r3.get("reasons",[]): raise SystemExit("ERROR: Agent D negative failed")
    # Each specialist remains fail closed.
    for s in sorted(specialists):
        px=json.loads(json.dumps(p)); px["specialist_endorsements"]=sorted(specialists-{s}); rx=decide(px,policy,trusted)
        if s not in rx.get("missing_specialists",[]): raise SystemExit(f"ERROR: missing specialist negative failed: {s}")
    # Omitting a trusted file must fail binding.
    if trusted:
        omitted=sorted(trusted)[0]; px=json.loads(json.dumps(p)); px["changed_files"]=[x for x in px["changed_files"] if x!=omitted]; px["domain_classifications"]=[x for x in px["domain_classifications"] if x.get("path")!=omitted]; reduced=set()
        for item in px["domain_classifications"]: reduced.update(normalize_domain(x) for x in item.get("domains",[]))
        px["changed_domains"]=sorted(reduced); px["specialist_endorsements"]=sorted(required_specialists_for(reduced,policy)); rx=decide(px,policy,trusted)
        if not any(x.startswith("changed_files_trusted_diff_mismatch") for x in rx.get("domain_classification_errors",[])): raise SystemExit("ERROR: omitted-file negative failed")
    print(json.dumps({"state":"PASS_NON_SOVEREIGN_PREFLIGHT","trusted_changed_files_count":len(trusted),"trusted_changed_files_digest":changed_file_digest(trusted),"eligible_voters":5,"minimum_approvals":4,"agent_d_mandatory":True,"cie_vote_state":"non_voting","required_specialists":sorted(specialists),"derived_changed_domains":sorted(domains)},indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
