#!/usr/bin/env python3
"""CT-ADR-GOV-012 merge-decision wrapper with foundational framework voters."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path

import governed_merge_decision as v1

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "developers/manifests/agent-sovereign-governance.v1.json"
OVERLAY = ROOT / "developers/manifests/agent-sovereign-governance.v2.json"


def load_effective_policy() -> dict:
    policy = copy.deepcopy(v1.load_json(BASE))
    overlay = v1.load_json(OVERLAY)
    additions = overlay.get("voter_pool_additions", [])
    existing = {x.get("agent_id") for x in policy.get("voter_pool", [])}
    for item in additions:
        if item.get("agent_id") in existing:
            raise ValueError("duplicate_foundational_framework_voter")
        policy["voter_pool"].append(item)
    q = overlay["quorum"]
    policy["quorum"].update({
        "approval_ratio": q["approval_ratio"],
        "rounding": q["rounding"],
        "current_eligible_voters": q["current_eligible_voters"],
        "current_minimum_approvals": q["current_minimum_approvals"],
        "deny_or_block_vote_prevents_automatic_merge": q["deny_or_block_vote_prevents_automatic_merge"],
        "abstention_counts_as_approval": q["abstention_counts_as_approval"],
        "missing_vote_counts_as_approval": q["missing_vote_counts_as_approval"],
        "quorum_cannot_override_d3": q["quorum_cannot_override_d3"],
    })
    policy["decision_id"] = overlay["decision_id"]
    policy["foundational_framework_voter_policy"] = overlay["foundational_framework_voter_policy"]
    policy["cie_integration"] = overlay["cie_integration"]
    # Make cultural-imprint material a deterministic specialist trigger domain.
    policy["changed_domain_contract"].setdefault("neutral_domains", []).append("cultural_imprint")
    return policy


def self_test(policy: dict) -> None:
    scores = {"evidence_quality": 100, "validation_strength": 100, "security_posture": 100, "reversibility": 100, "authority_fit": 100}
    five_yes = [
        {"agent_id": "ct.relay.agent-a", "vote": "approve"},
        {"agent_id": "ct.relay.agent-b", "vote": "approve"},
        {"agent_id": "ct.relay.agent-c", "vote": "approve"},
        {"agent_id": "ct.relay.agent-d", "vote": "approve"},
        {"agent_id": "ct.framework-agent.cie", "vote": "approve"},
    ]
    ok = v1.decide({"risk_class": "D0", "scores": scores, "votes": five_yes, "specialist_endorsements": [], "hard_blocks": []}, policy)
    assert ok["eligible_voters"] == 6
    assert ok["minimum_approvals"] == 5
    assert ok["agent_auto_merge_authorized"] is True

    four = v1.decide({"risk_class": "D0", "scores": scores, "votes": five_yes[:4], "specialist_endorsements": [], "hard_blocks": []}, policy)
    assert four["agent_auto_merge_authorized"] is False

    no_d = [x for x in five_yes if x["agent_id"] != "ct.relay.agent-d"] + [{"agent_id": "ct.relay.agent-s", "vote": "approve"}]
    result = v1.decide({"risk_class": "D0", "scores": scores, "votes": no_d, "specialist_endorsements": [], "hard_blocks": []}, policy)
    assert result["agent_auto_merge_authorized"] is False
    assert "independent_gatekeeper_approval_missing" in result["reasons"]

    subagent_vote = five_yes + [{"agent_id": "ct.subagent.cie.identity-fit", "vote": "approve"}]
    result = v1.decide({"risk_class": "D0", "scores": scores, "votes": subagent_vote, "specialist_endorsements": [], "hard_blocks": []}, policy)
    assert result["agent_auto_merge_authorized"] is False
    assert "ct.subagent.cie.identity-fit" in result["reasons"][0]

    d3 = v1.decide({"risk_class": "D3", "scores": scores, "votes": five_yes, "specialist_endorsements": [], "hard_blocks": [], "human_authorized": False}, policy)
    assert d3["agent_auto_merge_authorized"] is False
    assert "d3_human_authorization_required" in d3["reasons"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--verify-git-diff", action="store_true")
    parser.add_argument("--git-base")
    parser.add_argument("--git-head")
    args = parser.parse_args()
    policy = load_effective_policy()

    if args.self_test:
        self_test(policy)
        print("CT-ADR-GOV-012 self-test PASS: 6 permanent voters, 5-of-6 quorum, Agent D mandatory, CIE sovereign vote independent, CIE subagents non-voting, D3 human-reserved.")
        return 0

    trusted = None
    if args.git_base or args.git_head or args.verify_git_diff:
        if not args.git_base or not args.git_head:
            parser.error("--git-base and --git-head are both required")
        trusted = v1.trusted_changed_files_from_git(args.git_base, args.git_head)
    if args.verify_git_diff:
        print(json.dumps({"trusted_changed_files_count": len(trusted or set()), "trusted_changed_files_digest": v1.changed_file_digest(trusted or set()), "trusted_changed_files_redacted": True}, indent=2, sort_keys=True))
        if not args.packet:
            return 0
    if not args.packet:
        parser.error("--packet required unless --self-test or --verify-git-diff")
    result = v1.decide(v1.load_json(args.packet), policy, trusted)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
