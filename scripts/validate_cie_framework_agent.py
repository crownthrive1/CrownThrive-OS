#!/usr/bin/env python3
"""Validate the Cultural Imprint Engine non-voting controlled-test contract."""
from __future__ import annotations
import json
from pathlib import Path
from cie_scan import DIMENSIONS,HARD_BLOCK_CODES,PASS_THRESHOLD,PUBLIC_CONTRACT_DIGEST,self_test as scan_self_test
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"developers/manifests/cie-framework-agent.v1.json"; ALGORITHMS=ROOT/"developers/manifests/framework-algorithm-registry.v1.json"; FEDERATION=ROOT/"developers/manifests/repository-federation.v1.json"
DOCS=[ROOT/"doctrine/cultural-imprint-engine.mdx",ROOT/"chlom/cie-cultural-governance-pallet.mdx",ROOT/"automation/cie-framework-agent.mdx",ROOT/"technology/repository-federation-control-plane.mdx"]
def fail(m:str)->None: raise SystemExit(f"ERROR: {m}")
def main()->int:
    data=json.loads(MANIFEST.read_text(encoding="utf-8")); agent=data.get("agent",{})
    if data.get("framework_id")!="ct.framework.cultural-imprint-engine" or data.get("status")!="controlled_test_non_voting": fail("CIE framework state drift")
    if agent.get("agent_id")!="ct.framework-agent.cie" or agent.get("operational_parent")!="ct.relay.agent-a": fail("CIE identity/parent drift")
    if agent.get("vote_eligible") is not False or agent.get("may_create_sovereign_vote") is not False or agent.get("sovereign_vote_state")!="not_accepted": fail("CIE must remain non-voting")
    if agent.get("may_self_approve_originating_material_change") is not False: fail("CIE self-approval prohibited")
    if any(x.get("vote_eligible") is not False for x in data.get("subagents",[])): fail("CIE subagents must remain non-voting")
    scoring=data.get("scoring",{}); dims=scoring.get("dimensions",{})
    if scoring.get("pass_threshold")!=PASS_THRESHOLD or set(dims)!=set(DIMENSIONS) or sum(int(v.get("max_points",0)) for v in dims.values())!=100: fail("CIE public scoring contract drift")
    if set(data.get("hard_blocks",[]))!=HARD_BLOCK_CODES or scoring.get("hard_blocks_override_score") is not True: fail("CIE hard-block drift")
    if scoring.get("calibration_state")!="restricted_private_runtime_registered" or scoring.get("public_repository_contains_calibration") is not False: fail("protected calibration boundary drift")
    if scoring.get("public_contract_digest")!=PUBLIC_CONTRACT_DIGEST: fail("public contract digest drift")
    ethics=data.get("ethics_and_boundaries",{})
    for key in ("artifact_not_person_scoring","sensitive_trait_inference_prohibited","race_ethnicity_religion_or_other_sensitive_profile_scoring_prohibited","community_authenticity_policing_of_people_prohibited","evidence_and_reason_required_for_every_material_finding","correction_and_appeal_path_required"):
        if ethics.get(key) is not True: fail(f"ethics invariant missing: {key}")
    sync=data.get("ecosystem_sync",{})
    if sync.get("retroactive_scan_required") is not True or sync.get("subagent_messages_create_votes") is not False or sync.get("sync_agents_creates_votes") is not False: fail("sync/vote boundary drift")
    commercial=data.get("commercialization",{})
    if commercial.get("offer_state")!="candidate" or commercial.get("checkout_enabled") is not False or commercial.get("exact_price_authorized") is not False: fail("commercialization boundary drift")
    repo=data.get("repository_custody",{})
    if repo.get("target_state")!="pending_provisioning" or repo.get("child_operational") is not False or repo.get("child_can_vote") is not False or repo.get("parent_certification_required") is not True: fail("child repository must remain pending/non-operational/non-voting")
    ready=data.get("implementation_readiness",{})
    if ready.get("score")!=92 or ready.get("verdict")!="PASS_PHASE_2_99_CONTROLLED_TEST": fail("CIE readiness state drift")
    algorithms=json.loads(ALGORITHMS.read_text(encoding="utf-8")); algo=algorithms.get("algorithms",[])[0]
    if algo.get("algorithm_id")!="ct.algorithm.cie.v1" or algo.get("public_contract_digest")!=PUBLIC_CONTRACT_DIGEST: fail("algorithm registry mismatch")
    if "vault_policy_ref" in algo or algo.get("private_runtime_reference_state")!="registered_not_public": fail("public algorithm registry must not expose private runtime locator")
    fed=json.loads(FEDERATION.read_text(encoding="utf-8")); child=next((x for x in fed.get("repositories",[]) if x.get("repo_id")=="ct.repo.cie"),None)
    if not child or child.get("operationally_enabled") is not False or child.get("can_vote") is not False or child.get("oidc_bootstrap_state")!="blocked_repo_not_provisioned": fail("federation child state drift")
    for p in DOCS:
        if not p.is_file(): fail(f"missing CIE documentation: {p.relative_to(ROOT)}")
    scan_self_test(); print("CIE validation PASS: 92/100 controlled-test readiness, non-voting parent/subagents, public scoring contract, protected private calibration, CHLOM pallet and pending child federation verified."); return 0
if __name__=="__main__": raise SystemExit(main())
