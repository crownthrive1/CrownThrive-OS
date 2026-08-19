#!/usr/bin/env python3
"""Compute CrownThrive's agent-sovereign merge decision.

GitHub is evidence, CI, scanning and transport. It is not the sovereign merge
authority. This engine is fail-closed: normal promotion requires unanimity;
a narrowly-scoped, time-boxed deadlock override may use a 2/3 special vote
(rounded up) only when all higher-order safety and authority gates remain intact.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
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


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def decide(packet: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    pool = {
        item["agent_id"]: item
        for item in policy["voter_pool"]
        if item.get("vote_eligible") is True
    }
    q = policy["quorum"]
    normal_required = len(pool)
    override_cfg = q["deadlock_override"]
    override_required = math.ceil(len(pool) * float(override_cfg["special_vote_ratio"]))

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
    security_required = "security" in required_specialists
    security_sentinel_ok = (not security_required) or votes_by_agent.get("ct.relay.agent-s") == "approve"
    score_ok = (
        not score_errors
        and composite >= float(policy["risk_rating"]["minimum_automatic_merge_score"])
    )
    human_ok = (not d3) or packet.get("human_authorized") is True

    normal_unanimity_ok = bool(
        approvals == normal_required
        and not denials
        and not abstentions
        and not missing
    )

    override = packet.get("deadlock_override", {})
    override_requested = isinstance(override, dict) and override.get("requested") is True
    first_vote_at = parse_time(override.get("first_vote_at") if isinstance(override, dict) else None)
    decision_at = parse_time(override.get("decision_at") if isinstance(override, dict) else None)
    elapsed_hours = None
    if first_vote_at and decision_at and decision_at >= first_vote_at:
        elapsed_hours = round((decision_at - first_vote_at).total_seconds() / 3600.0, 3)
    reconciliation_attempts = int(override.get("reconciliation_attempts", 0)) if isinstance(override, dict) else 0
    override_reason = str(override.get("reason", "")).strip() if isinstance(override, dict) else ""
    override_initiator = str(override.get("initiator_agent_id", "")).strip() if isinstance(override, dict) else ""
    all_votes_cast = not missing and not abstentions and len(votes_by_agent) == len(pool)
    elapsed_ok = elapsed_hours is not None and elapsed_hours >= float(override_cfg["minimum_elapsed_hours"])
    reconciliation_ok = reconciliation_attempts >= int(override_cfg["minimum_reconciliation_attempts"])
    override_initiator_ok = override_initiator == str(override_cfg["initiator_agent_id"])
    override_vote_ok = approvals >= override_required and all_votes_cast
    override_mode_ok = bool(
        override_requested
        and override_vote_ok
        and elapsed_ok
        and reconciliation_ok
        and bool(override_reason)
        and override_initiator_ok
        and gatekeeper_ok
        and security_sentinel_ok
        and score_ok
        and risk_class in {"D0", "D1", "D2"}
        and not hard_blocks
        and not missing_endorsements
        and not invalid_votes
    )

    reasons: list[str] = []
    if invalid_votes:
        reasons.append(f"invalid_votes:{','.join(invalid_votes)}")
    if not normal_unanimity_ok:
        reasons.append(f"normal_unanimity_not_met:{approvals}/{normal_required}")
    if denials:
        reasons.append(f"deny_or_block:{','.join(denials)}")
    if missing:
        reasons.append(f"missing_votes:{','.join(missing)}")
    if abstentions:
        reasons.append(f"abstentions:{','.join(abstentions)}")
    if not gatekeeper_ok:
        reasons.append("independent_gatekeeper_approval_missing")
    if security_required and not security_sentinel_ok:
        reasons.append("security_sentinel_approval_missing_for_security_domain")
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
        reasons.append("d3_sovereign_vote_is_advisory_not_substitute_for_human_authority")
    if override_requested and not override_mode_ok:
        if not all_votes_cast:
            reasons.append("deadlock_override_requires_all_sovereign_votes_cast")
        if not elapsed_ok:
            reasons.append("deadlock_override_wait_window_not_met")
        if not reconciliation_ok:
            reasons.append("deadlock_override_reconciliation_attempts_not_met")
        if not override_reason:
            reasons.append("deadlock_override_reason_missing")
        if not override_initiator_ok:
            reasons.append("deadlock_override_initiator_invalid")
        if approvals < override_required:
            reasons.append(f"deadlock_override_special_vote_not_met:{approvals}/{override_required}")

    auto_merge_authorized = bool(
        risk_class in {"D0", "D1", "D2"}
        and (normal_unanimity_ok or override_mode_ok)
        and gatekeeper_ok
        and security_sentinel_ok
        and score_ok
        and not hard_blocks
        and not missing_endorsements
        and not invalid_votes
    )

    if auto_merge_authorized and override_mode_ok and not normal_unanimity_ok:
        decision = "approve_agent_merge_via_deadlock_override"
        decision_mode = "deadlock_override"
    elif auto_merge_authorized:
        decision = "approve_agent_merge_unanimous"
        decision_mode = "unanimous"
    else:
        decision = "deny_or_escalate"
        decision_mode = "blocked"

    if d3 and human_ok and normal_unanimity_ok and gatekeeper_ok and score_ok and not hard_blocks and not missing_endorsements:
        decision = "human_authorized_execution_may_proceed_under_separate_d3_controls"
        decision_mode = "d3_human_authorized"

    return {
        "decision": decision,
        "decision_mode": decision_mode,
        "agent_auto_merge_authorized": auto_merge_authorized,
        "risk_class": risk_class,
        "eligible_voters": len(pool),
        "normal_minimum_approvals": normal_required,
        "deadlock_override_minimum_approvals": override_required,
        "approvals": approvals,
        "denials_or_blocks": denials,
        "abstentions": abstentions,
        "missing_votes": missing,
        "composite_risk_score": composite,
        "minimum_score": policy["risk_rating"]["minimum_automatic_merge_score"],
        "required_specialists": sorted(required_specialists),
        "missing_specialists": missing_endorsements,
        "hard_blocks": hard_blocks,
        "deadlock_override_requested": override_requested,
        "deadlock_elapsed_hours": elapsed_hours,
        "deadlock_reconciliation_attempts": reconciliation_attempts,
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
    five_yes = [
        {"agent_id": "ct.relay.agent-a", "vote": "approve"},
        {"agent_id": "ct.relay.agent-b", "vote": "approve"},
        {"agent_id": "ct.relay.agent-c", "vote": "approve"},
        {"agent_id": "ct.relay.agent-d", "vote": "approve"},
        {"agent_id": "ct.relay.agent-s", "vote": "approve"},
    ]

    def packet(changed_domains: list[str], endorsements: list[str], risk_class: str = "D2") -> dict[str, Any]:
        return {
            "risk_class": risk_class,
            "scores": common_scores,
            "votes": five_yes,
            "changed_domains": changed_domains,
            "specialist_endorsements": endorsements,
            "hard_blocks": [],
        }

    unanimous = decide(packet([], [], "D1"), policy)
    assert unanimous["agent_auto_merge_authorized"] is True
    assert unanimous["decision_mode"] == "unanimous"
    assert unanimous["normal_minimum_approvals"] == 5
    assert unanimous["deadlock_override_minimum_approvals"] == 4

    four_yes_one_block = [*five_yes[:2], {"agent_id": "ct.relay.agent-c", "vote": "block"}, *five_yes[3:]]
    blocked = decide({**packet([], [], "D1"), "votes": four_yes_one_block}, policy)
    assert blocked["agent_auto_merge_authorized"] is False

    override = decide({
        **packet([], [], "D1"),
        "votes": four_yes_one_block,
        "deadlock_override": {
            "requested": True,
            "first_vote_at": "2026-08-19T00:00:00Z",
            "decision_at": "2026-08-19T06:00:00Z",
            "reconciliation_attempts": 2,
            "reason": "One non-hard dissent remains after evidence reconciliation.",
            "initiator_agent_id": "ct.subagent.governance-marshal",
        },
    }, policy)
    assert override["agent_auto_merge_authorized"] is True
    assert override["decision_mode"] == "deadlock_override"

    too_early = decide({
        **packet([], [], "D1"),
        "votes": four_yes_one_block,
        "deadlock_override": {
            "requested": True,
            "first_vote_at": "2026-08-19T00:00:00Z",
            "decision_at": "2026-08-19T05:59:00Z",
            "reconciliation_attempts": 2,
            "reason": "Still inside the reconciliation window.",
            "initiator_agent_id": "ct.subagent.governance-marshal",
        },
    }, policy)
    assert too_early["agent_auto_merge_authorized"] is False

    hard_blocked = decide({
        **packet([], [], "D1"),
        "votes": four_yes_one_block,
        "hard_blocks": ["critical_security_finding"],
        "deadlock_override": {
            "requested": True,
            "first_vote_at": "2026-08-19T00:00:00Z",
            "decision_at": "2026-08-19T07:00:00Z",
            "reconciliation_attempts": 3,
            "reason": "Must not override a hard block.",
            "initiator_agent_id": "ct.subagent.governance-marshal",
        },
    }, policy)
    assert hard_blocked["agent_auto_merge_authorized"] is False

    registry = policy.get("specialist_activation", {})
    assert isinstance(registry, dict) and len(registry) == 9
    for specialist_key, config in registry.items():
        endorsement_id = normalize_domain(config["endorsement_id"])
        missing = decide(packet([specialist_key], []), policy)
        assert missing["agent_auto_merge_authorized"] is False
        assert endorsement_id in missing["missing_specialists"], specialist_key
        endorsed = decide(packet([specialist_key], [endorsement_id]), policy)
        assert endorsed["agent_auto_merge_authorized"] is True, specialist_key

    security_override_without_s = decide({
        **packet(["security"], ["security"]),
        "votes": [
            {"agent_id": "ct.relay.agent-a", "vote": "approve"},
            {"agent_id": "ct.relay.agent-b", "vote": "approve"},
            {"agent_id": "ct.relay.agent-c", "vote": "approve"},
            {"agent_id": "ct.relay.agent-d", "vote": "approve"},
            {"agent_id": "ct.relay.agent-s", "vote": "block"},
        ],
        "deadlock_override": {
            "requested": True,
            "first_vote_at": "2026-08-19T00:00:00Z",
            "decision_at": "2026-08-19T07:00:00Z",
            "reconciliation_attempts": 3,
            "reason": "Security dissent cannot be overridden on a security packet.",
            "initiator_agent_id": "ct.subagent.governance-marshal",
        },
    }, policy)
    assert security_override_without_s["agent_auto_merge_authorized"] is False

    d3 = decide({**packet(["legal"], ["legal_regulatory"], "D3"), "human_authorized": False}, policy)
    assert d3["agent_auto_merge_authorized"] is False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    policy = load_json(MANIFEST)
    if args.self_test:
        self_test(policy)
        print("Agent-sovereign merge-decision self-test passed: normal mode requires 5/5 unanimity; after a 6-hour evidence-reconciliation window a disciplined 2/3 special vote rounds to 4/5, requires all votes cast, Agent D approval, Security Sentinel approval for security domains, specialists, score, rollback-compatible authority, and zero hard blocks; D3 cannot auto-merge.")
        return 0
    if not args.packet:
        parser.error("--packet is required unless --self-test is used")
    print(json.dumps(decide(load_json(args.packet), policy), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
