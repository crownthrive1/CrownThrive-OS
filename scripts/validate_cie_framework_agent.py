#!/usr/bin/env python3
"""Validate the Cultural Imprint Engine framework-agent contract."""
from __future__ import annotations
import json
from pathlib import Path
from cie_scan import DIMENSIONS, HARD_BLOCK_CODES, PASS_THRESHOLD, self_test as scan_self_test

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/cie-framework-agent.v1.json"
DOCTRINE = ROOT / "doctrine/cultural-imprint-engine.mdx"
PALLET = ROOT / "chlom/cie-cultural-governance-pallet.mdx"
AGENT_DOC = ROOT / "automation/cie-framework-agent.mdx"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("framework_id") != "ct.framework.cultural-imprint-engine": fail("framework id drift")
    agent = data.get("agent", {})
    if agent.get("agent_id") != "ct.framework-agent.cie" or agent.get("permanent") is not True: fail("CIE permanent agent identity drift")
    if agent.get("operational_parent") != "ct.relay.agent-a": fail("CIE operational parent must remain Agent A")
    if agent.get("vote_eligible") is not True or agent.get("vote_independence_required") is not True: fail("CIE sovereign voter independence required")
    if agent.get("may_self_approve_originating_material_change") is not False: fail("CIE cannot self-approve originating material")

    subagents = data.get("subagents", [])
    ids = {item.get("agent_id") for item in subagents}
    expected = {
        "ct.subagent.cie.identity-fit", "ct.subagent.cie.community-value",
        "ct.subagent.cie.story-alignment", "ct.subagent.cie.brand-safety",
        "ct.subagent.cie.legacy-impact", "ct.subagent.cie.remediation-escalation",
    }
    if ids != expected: fail("CIE subagent topology drift")
    if any(item.get("vote_eligible") is not False for item in subagents): fail("CIE subagents must remain non-voting")

    scoring = data.get("scoring", {})
    if scoring.get("pass_threshold") != PASS_THRESHOLD: fail("CIE pass threshold drift")
    dims = scoring.get("dimensions", {})
    if set(dims) != set(DIMENSIONS): fail("CIE canonical five dimensions drift")
    if sum(int(v.get("max_points", 0)) for v in dims.values()) != 100: fail("CIE scoring must total 100")
    if set(data.get("hard_blocks", [])) != HARD_BLOCK_CODES: fail("CIE hard-block set drift")
    if scoring.get("hard_blocks_override_score") is not True: fail("CIE hard blocks must override score")

    ethics = data.get("ethics_and_boundaries", {})
    for key in (
        "artifact_not_person_scoring", "sensitive_trait_inference_prohibited",
        "race_ethnicity_religion_or_other_sensitive_profile_scoring_prohibited",
        "community_authenticity_policing_of_people_prohibited",
        "evidence_and_reason_required_for_every_material_finding",
        "correction_and_appeal_path_required",
    ):
        if ethics.get(key) is not True: fail(f"CIE ethics invariant missing: {key}")

    sync = data.get("ecosystem_sync", {})
    if sync.get("applies_to_all_registered_agents") is not True or sync.get("retroactive_scan_required") is not True: fail("CIE ecosystem sync/retroactive scan required")

    chlom = data.get("chlom", {})
    if chlom.get("pallet_id") != "ct.chlom.pallet.cie-cultural-governance": fail("CIE CHLOM pallet id drift")

    commercial = data.get("commercialization", {})
    if commercial.get("offer_state") != "candidate" or commercial.get("checkout_enabled") is not False or commercial.get("exact_price_authorized") is not False: fail("CIE commercialization must remain candidate/no checkout/no exact price")

    repo = data.get("repository_custody", {})
    if repo.get("target_repository") != "crownthrive1/CrownThrive-CIE": fail("CIE target repo drift")
    if repo.get("target_state") != "target_not_connected_not_provisioned": fail("CIE target repo must remain explicit until provisioned")

    ml = data.get("ml_and_ai", {})
    if ml.get("ml_training_state") != "not_started" or ml.get("ml_may_not_determine_personal_cultural_authenticity") is not True: fail("CIE ML boundary drift")

    readiness = data.get("implementation_readiness", {})
    if readiness.get("score") != 92 or readiness.get("pass_threshold") != 85 or readiness.get("verdict") != "PASS_PHASE_2_99_INSTITUTIONALIZATION": fail("CIE readiness score/state drift")
    if sum(int(v) for v in readiness.get("dimensions", {}).values()) != 92: fail("CIE readiness dimension arithmetic drift")

    for path in (DOCTRINE, PALLET, AGENT_DOC):
        if not path.is_file(): fail(f"missing CIE documentation: {path.relative_to(ROOT)}")
    scan_self_test()
    print("CIE framework-agent validation PASS: 92/100 institutionalization score, six-agent topology, five canonical scoring dimensions, ethics boundaries, CHLOM pallet and deterministic scanner verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
