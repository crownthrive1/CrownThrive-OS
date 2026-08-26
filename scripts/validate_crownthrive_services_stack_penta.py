#!/usr/bin/env python3
"""Validate the Phase-3 CrownThrive Services Stack compatibility substrate."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "developers/manifests/crownthrive-services-stack.v2.json"
PRECOMPILE = ROOT / "developers/manifests/pentafactory-parallel-precompile.v2.json"
DOC = ROOT / "frameworks/crownthrive-services-stack.mdx"
PRECOMPILE_DOC = ROOT / "frameworks/pentafactory-parallel-precompile.mdx"
SKILL = ROOT / "skills/crownthrive-services-stack/SKILL.md"

EXPECTED = {
    "ct.css.service.identity",
    "ct.css.service.authentication",
    "ct.css.service.authorization",
    "ct.css.service.billing",
    "ct.css.service.licensing",
    "ct.css.service.analytics",
    "ct.css.service.notifications",
    "ct.css.service.crm",
    "ct.css.service.ticketing",
    "ct.css.service.search",
    "ct.css.service.commerce",
    "ct.css.service.routing",
    "ct.css.service.rewards",
    "ct.css.service.documentation",
}


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    for path in (CSS, PRECOMPILE, DOC, PRECOMPILE_DOC, SKILL):
        require(path.is_file(), f"missing artifact: {path.relative_to(ROOT)}")

    css = json.loads(CSS.read_text(encoding="utf-8"))
    pre = json.loads(PRECOMPILE.read_text(encoding="utf-8"))
    doc = DOC.read_text(encoding="utf-8")
    skill = SKILL.read_text(encoding="utf-8")

    require(css["schema"] == "ct.manifest.crownthrive-services-stack.v2", "CSS schema drift")
    require(css["classification"] == "shared_services_compatibility_substrate", "CSS must remain substrate")
    require(css["phase"] == "3", "Phase 3 binding required")
    require(set(css["service_ids"]) == EXPECTED and css["service_count"] == 14, "stable service inventory drift")
    authority = css["authority"]
    require(authority["orchestration_owner"] == "PentaFabric", "PentaFabric ownership required")
    require(authority["credential_owner"] == "PentaCredentials", "PentaCredentials ownership required")
    require(authority["certification_owner"] == "PentaCertify", "PentaCertify ownership required")
    require(authority["standalone_governance_authority"] is False, "CSS cannot become authority")
    legacy = css["legacy_runtime"]
    require(legacy["is_current_runtime_claim"] is False, "historical runtime cannot become current claim")
    require(legacy["current_runtime_state"] == "READBACK_REQUIRED", "current runtime must be readback-gated")
    require(legacy["legacy_edge_source_promotable"] is False, "unsafe legacy Edge source cannot promote")
    require("hardcoded_privileged_identity_allowlist" in legacy["legacy_edge_source_reasons"], "legacy identity risk must remain explicit")
    require("direct_service_role_token_identity_shortcut" in legacy["legacy_edge_source_reasons"], "service-role shortcut risk must remain explicit")
    require(all(value is False for value in css["hard_boundaries"].values()), "CSS hard boundary widened")

    require(pre["schema"] == "ct.manifest.pentafactory-parallel-precompile.v2", "precompile schema drift")
    inv = pre["invariants"]
    require(inv["parallel_preparation_allowed"] is True, "parallel preparation must remain allowed")
    require(inv["promotion_is_serialized_by_current_dependency_graph"] is True, "promotion serialization required")
    require(inv["fixed_legacy_predecessor_chain_authoritative"] is False, "legacy activation chain must not become current authority")
    require(inv["self_approval"] is False and inv["vote_created"] is False, "precompile cannot self-approve or vote")
    require(inv["provider_write"] is False and inv["money_movement"] is False and inv["rights_grant"] is False, "precompile side-effect boundary widened")

    require("hard-coded privileged identity" in doc, "legacy Edge security disposition missing")
    require("PentaCredentials" in skill and "PentaCertify" in skill, "current execution binding missing")
    require("Parallelize preparation" in PRECOMPILE_DOC.read_text(encoding="utf-8"), "precompile invariant missing")
    print("CrownThrive Services Stack Phase-3 Penta compatibility: PASS")


if __name__ == "__main__":
    main()
