#!/usr/bin/env python3
"""Fail-closed validator for the non-canonical Founder Audit candidate manifest."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers" / "manifests" / "founder-audit-program.v1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FOUNDER_AUDIT_GUARD: {message}")


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(data.get("classification") == "FOUNDER_AUDIT_CANDIDATE", "classification must remain candidate")
    require(data.get("canonical") is False, "candidate must not claim canonical status")
    require(data.get("vote_required") is True, "governed vote must remain required")
    require(data.get("phase") == "2.99", "candidate must remain inside Phase 2.99")
    require(data.get("phase_3_authorized") is False, "candidate cannot authorize Phase 3")
    require(data.get("public_summary_only") is True, "public repository must contain summary only")
    agents = data.get("agents", [])
    require(agents, "at least one audit agent must be declared")
    for agent in agents:
        aid = agent.get("agent_id", "<missing>")
        require(agent.get("binding_state") == "probation_shadow", f"{aid} must begin in shadow probation")
        require(agent.get("authority_ceiling") == "D0", f"{aid} must begin at D0")
        for key in ("vote_eligible", "publish_enabled", "certify_enabled", "hold_activation_enabled"):
            require(agent.get(key) is False, f"{aid} must keep {key}=false")
        require(agent.get("secret_access") == "none", f"{aid} must have no secret access")
    require(data.get("probation", {}).get("automatic_voting_promotion") is False, "automatic voting promotion is prohibited")
    prohibited = set(data.get("prohibited_effects", []))
    for item in ("phase_3_promotion", "sovereign_vote_creation", "self_certification", "secret_retrieval"):
        require(item in prohibited, f"missing prohibited effect: {item}")
    print("FOUNDER_AUDIT_GUARD: PASS — candidate remains non-canonical, vote-gated, D0 and non-voting")


if __name__ == "__main__":
    main()
