#!/usr/bin/env python3
"""Deterministic validator and inventory emitter for the CrownThrive agent suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "governance/agent-suite-v1/agent-registry.json"
COMMITTEES = ROOT / "governance/agent-suite-v1/committee-registry.json"
SCHEDULES = ROOT / "governance/agent-suite-v1/schedule-registry.json"
SKILLS = ROOT / "developers/manifests/agent-skill-catalog.v1.json"
CUSTODY = ROOT / "developers/manifests/custody-policy.v1.json"
QUARANTINE = ROOT / "developers/manifests/source-generation-quarantine.v1.json"
PRICING = ROOT / "developers/manifests/pricing-policy-candidates.v1.json"
FRAMEWORK_CANDIDATE = ROOT / "framework-candidates/thrivealumni-committee-support.v1.json"

KNOWN_BASELINE_AGENTS = {
    "ct.chlom.agent.accessibility-consumer",
    "ct.chlom.agent.continuity",
    "ct.chlom.agent.cultural-governance",
    "ct.chlom.agent.docs",
    "ct.chlom.agent.finance-tax",
    "ct.chlom.agent.identity",
    "ct.chlom.agent.orchestrator",
}


class SuiteValidationError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise SuiteValidationError(f"{path}: top-level value must be an object")
    return value


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    registry = load_json(REGISTRY)
    committees = load_json(COMMITTEES)
    schedules = load_json(SCHEDULES)
    skills = load_json(SKILLS)
    custody = load_json(CUSTODY)
    quarantine = load_json(QUARANTINE)
    pricing = load_json(PRICING)
    framework = load_json(FRAMEWORK_CANDIDATE)

    agents = registry.get("agents", [])
    if len(agents) != 26:
        errors.append(f"expected 26 scoped subagents, found {len(agents)}")
    ids = [agent.get("agent_id") for agent in agents]
    if len(ids) != len(set(ids)):
        errors.append("agent IDs are not unique")
    names = [agent.get("canonical_name") for agent in agents]
    if len(names) != len(set(names)):
        errors.append("agent canonical names are not unique")

    modes = {"rigid": 0, "fluid": 0, "hybrid": 0}
    for agent in agents:
        agent_id = agent.get("agent_id", "<missing>")
        mode = agent.get("mode")
        if mode not in modes:
            errors.append(f"{agent_id}: invalid operating mode {mode!r}")
        else:
            modes[mode] += 1
        if agent.get("authority_ceiling") == "D3":
            errors.append(f"{agent_id}: D3 must remain human-reserved")
        if agent.get("autonomy_class") not in {"A0", "A1", "A2"}:
            errors.append(f"{agent_id}: autonomy above A2 is not allowed in controlled test")
        forbidden = set(agent.get("forbidden", []))
        if "self_approve" not in forbidden:
            errors.append(f"{agent_id}: self approval prohibition missing")
        if not agent.get("allowed"):
            errors.append(f"{agent_id}: empty allowed capability set")
    if any(count == 0 for count in modes.values()):
        errors.append("rigid, fluid and hybrid modes must all be represented")

    contract = registry.get("operating_contract", {})
    required_true = {
        "human_authority_reserved",
        "self_approval_forbidden",
        "silent_delete_forbidden",
        "append_only_correction_history",
    }
    for key in required_true:
        if contract.get(key) is not True:
            errors.append(f"operating_contract.{key} must be true")
    for key in {"vote_eligible", "quorum_eligible", "privilege_inheritance"}:
        if contract.get(key) is not False:
            errors.append(f"operating_contract.{key} must be false")

    known_agents = set(ids) | KNOWN_BASELINE_AGENTS
    committee_rows = committees.get("committees", [])
    if len(committee_rows) != 14:
        errors.append(f"expected 14 public ThriveAlumni surfaces, found {len(committee_rows)}")
    for committee in committee_rows:
        for agent_id in committee.get("support_agents", []):
            if agent_id not in known_agents:
                errors.append(f"{committee.get('committee_id')}: unknown agent {agent_id}")
        if committee.get("drift_state") == "PASS":
            errors.append(f"{committee.get('committee_id')}: unresolved public drift cannot be PASS")

    schedule_rows = schedules.get("schedules", [])
    if len(schedule_rows) > 15:
        errors.append("schedule count exceeds current task limit")
    if len(schedule_rows) != 8:
        errors.append(f"expected 8 consolidated schedules, found {len(schedule_rows)}")
    schedule_ids = [row.get("schedule_id") for row in schedule_rows]
    if len(schedule_ids) != len(set(schedule_ids)):
        errors.append("schedule IDs are not unique")
    for row in schedule_rows:
        if not row.get("skill", "").startswith("$crownthrive-"):
            errors.append(f"{row.get('schedule_id')}: schedule must invoke an installed suite skill")
        for agent_id in row.get("agents", []):
            if agent_id not in known_agents:
                errors.append(f"{row.get('schedule_id')}: unknown scheduled agent {agent_id}")

    master_skills = skills.get("master_skills", [])
    covered_agents = {
        agent_id
        for skill in master_skills
        for agent_id in skill.get("agent_registry_filter", [])
    }
    uncovered = set(ids) - covered_agents
    if uncovered:
        errors.append("agents missing from master skills: " + ", ".join(sorted(uncovered)))
    if skills.get("commercial_state") != "HOLD":
        errors.append("skill catalog must remain commercial HOLD")
    if skills.get("checkout_enabled") is not False or skills.get("entitlements_active") is not False:
        errors.append("skill checkout and entitlements must remain disabled")

    destinations = {row.get("system") for row in custody.get("destinations", []) if row.get("required")}
    if destinations != {"google_drive", "supabase"}:
        errors.append("custody policy must require both Google Drive and Supabase")
    if "Vault stores only secret" not in json.dumps(custody, ensure_ascii=False):
        errors.append("custody policy must distinguish Vault secrets from Storage artifacts")

    if quarantine.get("state") != "HOLD_NEED_TO_DO":
        errors.append("detached v2 evidence must remain quarantined")
    if quarantine.get("v1_observed", {}).get("help_center_records") != 795:
        errors.append("v1 recovery canon must preserve 795 records")
    if quarantine.get("detached_v2_claims", {}).get("expected_recovery_pages") != 794:
        errors.append("detached v2 mismatch must remain explicit")

    if pricing.get("state") != "GOVERNED_HOLD":
        errors.append("pricing must remain governed HOLD")
    if pricing.get("checkout_enabled") is not False or pricing.get("stripe_objects_created") is not False:
        errors.append("pricing catalog cannot enable checkout or claim Stripe objects")
    if pricing.get("minimum_credit_transaction") != 400:
        errors.append("credit minimum drifted from governing baseline")

    if framework.get("candidate_type") != "capability_pack":
        errors.append("ThriveAlumni candidate must be a capability pack, not a ninth framework")
    if framework.get("framework_count_delta") != 0:
        errors.append("capability suite must not change the eight-framework factory count")
    if any(framework.get(key) is not False for key in ("activation_allowed", "public_claim_allowed", "commercialization_allowed")):
        errors.append("candidate activation, public claim and commercialization must remain disabled")

    if errors:
        raise SuiteValidationError("\n".join(errors))

    return {
        "status": "PASS",
        "scope": "manifest_and_invariant_validation_only",
        "release_state": registry.get("release_state"),
        "agent_count": len(agents),
        "committee_surface_count": len(committee_rows),
        "schedule_count": len(schedule_rows),
        "mode_counts": modes,
        "master_skill_count": len(master_skills),
        "per_agent_skill_candidate_count": len(agents),
        "manifest_sha256": canonical_sha256(registry),
        "warnings": warnings,
        "not_proven": [
            "runtime execution",
            "human governance approval",
            "dual-custody restore",
            "MCP publication",
            "commercial activation",
            "detached v2 corpus validity",
        ],
    }


def inventory() -> dict[str, Any]:
    registry = load_json(REGISTRY)
    return {
        "suite_id": registry["suite_id"],
        "release_state": registry["release_state"],
        "agents": [
            {
                "agent_id": row["agent_id"],
                "name": row["canonical_name"],
                "family": row["family"],
                "mode": row["mode"],
                "autonomy": row["autonomy_class"],
                "authority": row["authority_ceiling"],
            }
            for row in registry["agents"]
        ],
    }


def skill_candidates() -> dict[str, Any]:
    registry = load_json(REGISTRY)
    return {
        "catalog_state": "CANDIDATE_HOLD",
        "packages": [
            {
                "skill_id": f"ct.skill.agent.{row['agent_id'].split('.')[-1]}.v1",
                "agent_id": row["agent_id"],
                "version": "1.0.0",
                "mcp_state": "DISABLED",
                "commercial_state": "HOLD",
                "price_credits": None,
                "manifest_sha256": canonical_sha256(row),
            }
            for row in registry["agents"]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", action="store_true")
    group.add_argument("--inventory", action="store_true")
    group.add_argument("--skill-candidates", action="store_true")
    args = parser.parse_args()
    try:
        if args.validate:
            value = validate()
        elif args.inventory:
            value = inventory()
        else:
            value = skill_candidates()
    except (OSError, json.JSONDecodeError, SuiteValidationError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
