#!/usr/bin/env python3
"""Compute CrownThrive's agent-sovereign merge decision.

GitHub is evidence, CI, scanning and transport. It is not the sovereign merge
authority. This decision engine is deliberately fail-closed and does not perform
the merge itself.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/agent-sovereign-governance.v1.json"
VALID_VOTES = {"approve", "deny", "block", "abstain"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_domain(value: Any) -> str:
    text = str(value).strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def required_specialists_for(changed_domains: set[str], policy: dict[str, Any]) -> set[str]:
    normalized_domains = {normalize_domain(value) for value in changed_domains if normalize_domain(value)}
    required: set[str] = set()
    registry = policy.get("specialist_activation", {})
    if not isinstance(registry, dict):
        return required

    for specialist_key, config in registry.items():
        if not isinstance(config, dict):
            continue
        endorsement_id = normalize_domain(config.get("endorsement_id", specialist_key))
        patterns = {
            normalize_domain(value)
            for value in config.get("required_patterns", [])
            if normalize_domain(value)
        }
        patterns.add(normalize_domain(specialist_key))
        patterns.add(endorsement_id)
        if normalized_domains & patterns:
            required.add(endorsement_id)
    return required


def decide(packet: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    pool = {
        item["agent_id"]: item
        for item in policy["voter_pool"]
        if item.get("vote_eligible") is True
    }
    q = policy["quorum"]
    required = math.ceil(len(pool) * float(q["approval_ratio"]))

    votes_by_agent: dict[str, str] = {}
    invalid_votes: list[str] = []
    for item in packet.get("votes", []):
        agent_id = str(item.get("agent_id", ""))
        vote = str(item.get("vote", "")).lower()
        if agent_id not in pool or vote not in VALID_VOTES:
            invalid_votes.append(agent_id or "<missing>")
            continue
        if agent_id in votes_by_agent:
            invalid_votes.append(f"duplicate:{agent_id}")
            continue
        votes_by_agent[agent_id] = vote

    approvals = sum(v == "approve" for v in votes_by_agent.values())
    denials = sorted(a for a, v in votes_by_agent.items() if v in {"deny", "block"})
    abstentions = sorted(a for a, v in votes_by_agent.items() if v == "abstain")
    missing = sorted(set(pool) - set(votes_by_agent))

    weights = policy["risk_rating"]["dimensions"]
    scores = packet.get("scores", {})
    score_errors: list[str] = []
    composite = 0.0
    for name, weight in weights.items():
        value = scores.get(name)
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 100:
            score_errors.append(name)
            continue
        composite += float(value) * float(weight)
    composite = round(composite, 2)

    risk_class = str(packet.get("risk_class", "")).upper()
    d3 = risk_class == "D3"
    hard_blocks = [str(x) for x in packet.get("hard_blocks", []) if str(x).strip()]
    endorsements = {normalize_domain(value) for value in packet.get("specialist_endorsements", [])}
    changed_domains = {str(value) for value in packet.get("changed_domains", [])}
    required_specialists = required_specialists_for(changed_domains, policy)

    missing_endorsements = sorted(required_specialists - endorsements)
    gatekeeper_ok = votes_by_agent.get("ct.relay.agent-d") == "approve"
    score_ok = (
        not score_errors
        and composite >= float(policy["risk_rating"]["minimum_automatic_merge_score"])
    )
    quorum_ok = approvals >= required and not denials
    human_ok = (not d3) or packet.get("human_authorized") is True

    reasons: list[str] = []
    if invalid_votes:
        reasons.append(f"invalid_votes:{','.join(invalid_votes)}")
    if denials:
        reasons.append(f"deny_or_block:{','.join(denials)}")
    if approvals < required:
        reasons.append(f"quorum_not_met:{approvals}/{required}")
    if missing:
        reasons.append(f"missing_votes:{','.join(missing)}")
    if abstentions:
        reasons.append(f"abstentions:{','.join(abstentions)}")
    if not gatekeeper_ok:
        reasons.append("independent_gatekeeper_approval_missing")
    if score_errors:
        reasons.append(f"invalid_scores:{','.join(score_errors)}")
    if not score_ok and not score_errors:
        reasons.append(
            f"risk_score_below_threshold:{composite}/"
            f"{policy['risk_rating']['minimum_automatic_merge_score']}"
        )
    if missing_endorsements:
        reasons.append(f"missing_specialists:{','.join(missing_endorsements)}")
    if hard_blocks:
        reasons.append(f"hard_blocks:{','.join(hard_blocks)}")
    if d3 and not human_ok:
        reasons.append("d3_human_authorization_required")
    if d3:
        reasons.append("d3_quorum_is_advisory_not_substitute_for_human_authority")

    auto_merge_authorized = bool(
        risk_class in {"D0", "D1", "D2"}
        and quorum_ok
        and gatekeeper_ok
        and score_ok
        and not hard_blocks
        and not missing_endorsements
        and not invalid_votes
    )

    decision = "approve_agent_merge" if auto_merge_authorized else "deny_or_escalate"
    if d3 and human_ok and quorum_ok and gatekeeper_ok and score_ok and not hard_blocks and not missing_endorsements:
        decision = "human_authorized_execution_may_proceed_under_separate_d3_controls"

    return {
        "decision": decision,
        "agent_auto_merge_authorized": auto_merge_authorized,
        "risk_class": risk_class,
        "eligible_voters": len(pool),
        "quorum_ratio": q["approval_ratio"],
        "minimum_approvals": required,
        "approvals": approvals,
        "denials_or_blocks": denials,
        "abstentions": abstentions,
        "missing_votes": missing,
        "composite_risk_score": composite,
        "minimum_score": policy["risk_rating"]["minimum_automatic_merge_score"],
        "required_specialists": sorted(required_specialists),
        "missing_specialists": missing_endorsements,
        "hard_blocks": hard_blocks,
        "human_authorized": packet.get("human_authorized") is True,
        "reasons": reasons,
    }


def self_test(policy: dict[str, Any]) -> None:
    common_scores = {
        "evidence_quality": 100,
        "validation_strength": 100,
        "security_posture": 100,
        "reversibility": 100,
        "authority_fit": 100,
    }
    four_yes = [
        {"agent_id": "ct.relay.agent-a", "vote": "approve"},
        {"agent_id": "ct.relay.agent-b", "vote": "approve"},
        {"agent_id": "ct.relay.agent-c", "vote": "approve"},
        {"agent_id": "ct.relay.agent-d", "vote": "approve"},
    ]
    ok = decide({
        "risk_class": "D1", "scores": common_scores, "votes": four_yes,
        "changed_domains": [], "specialist_endorsements": [], "hard_blocks": []
    }, policy)
    assert ok["agent_auto_merge_authorized"] is True
    assert ok["minimum_approvals"] == 4

    three_yes = decide({
        "risk_class": "D1", "scores": common_scores, "votes": four_yes[:3],
        "changed_domains": [], "specialist_endorsements": [], "hard_blocks": []
    }, policy)
    assert three_yes["agent_auto_merge_authorized"] is False

    security_without_specialist = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_domains": ["security"], "specialist_endorsements": [], "hard_blocks": []
    }, policy)
    assert security_without_specialist["agent_auto_merge_authorized"] is False
    assert "security" in security_without_specialist["missing_specialists"]

    blockchain_partial = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_domains": ["blockchain"], "specialist_endorsements": ["security"], "hard_blocks": []
    }, policy)
    assert blockchain_partial["agent_auto_merge_authorized"] is False
    assert "blockchain_protocol" in blockchain_partial["missing_specialists"]

    blockchain_full = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_domains": ["blockchain"],
        "specialist_endorsements": ["security", "blockchain_protocol"], "hard_blocks": []
    }, policy)
    assert blockchain_full["agent_auto_merge_authorized"] is True

    ip_partial = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_domains": ["rights"], "specialist_endorsements": ["legal_regulatory"], "hard_blocks": []
    }, policy)
    assert ip_partial["agent_auto_merge_authorized"] is False
    assert "ip_rights_licensing" in ip_partial["missing_specialists"]

    finance_without_specialist = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_domains": ["tax"], "specialist_endorsements": [], "hard_blocks": []
    }, policy)
    assert finance_without_specialist["agent_auto_merge_authorized"] is False
    assert "finance_tax_treasury" in finance_without_specialist["missing_specialists"]

    consumer_without_specialist = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_domains": ["accessibility"], "specialist_endorsements": [], "hard_blocks": []
    }, policy)
    assert consumer_without_specialist["agent_auto_merge_authorized"] is False
    assert "accessibility_consumer_protection" in consumer_without_specialist["missing_specialists"]

    regional_without_specialist = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_domains": ["localization"], "specialist_endorsements": [], "hard_blocks": []
    }, policy)
    assert regional_without_specialist["agent_auto_merge_authorized"] is False
    assert "regional_global_localization" in regional_without_specialist["missing_specialists"]

    d3 = decide({
        "risk_class": "D3", "scores": common_scores, "votes": four_yes,
        "changed_domains": ["legal"], "specialist_endorsements": ["legal_regulatory"],
        "hard_blocks": [], "human_authorized": False
    }, policy)
    assert d3["agent_auto_merge_authorized"] is False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    policy = load_json(MANIFEST)
    if args.self_test:
        self_test(policy)
        print("Agent-sovereign merge-decision self-test passed: 75% quorum is 4/5; all registered specialist gates enforce; D3 cannot auto-merge.")
        return 0
    if not args.packet:
        parser.error("--packet is required unless --self-test is used")
    print(json.dumps(decide(load_json(args.packet), policy), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
