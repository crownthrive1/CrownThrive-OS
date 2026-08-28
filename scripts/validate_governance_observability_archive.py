#!/usr/bin/env python3
"""Validate Phase-3 governance observability and archive-continuity boundaries."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/governance-observability-archive-continuity.v2.json"
CLASSIFIER = ROOT / "scripts/classify_governance_run.py"
READBACK = ROOT / "scripts/upsert_pr_governance_state.py"
OBS_WORKFLOW = ROOT / ".github/workflows/governance-observability.yml"
MERGE_WORKFLOW = ROOT / ".github/workflows/governed-merge-gate.yml"
STANDARD = ROOT / "standards/governance-observability-and-archive-continuity.mdx"
PENTA_BINDING = ROOT / "automation/governance-observability-penta-capability.mdx"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    for path in (MANIFEST, CLASSIFIER, READBACK, OBS_WORKFLOW, MERGE_WORKFLOW, STANDARD, PENTA_BINDING):
        require(path.is_file(), f"required artifact missing: {path.relative_to(ROOT)}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    classifier = CLASSIFIER.read_text(encoding="utf-8")
    readback = READBACK.read_text(encoding="utf-8")
    obs = OBS_WORKFLOW.read_text(encoding="utf-8")
    merge = MERGE_WORKFLOW.read_text(encoding="utf-8")
    standard = STANDARD.read_text(encoding="utf-8")
    penta = PENTA_BINDING.read_text(encoding="utf-8")

    require(manifest["schema"] == "ct.manifest.governance-observability-archive-continuity.v2", "manifest schema drift")
    require(manifest["phase"] == "3", "Phase 3 binding required")
    ownership = manifest["ownership"]
    require(set(ownership["primary"]) == {"PentaNurture", "PentaStatus"}, "Penta ownership drift")
    require(ownership["standalone_agent_authority"] is False, "standalone authority prohibited")
    require(ownership["vote_eligible"] is False and ownership["self_approval"] is False, "observability cannot vote/self-approve")

    gov = manifest["governance_observability"]
    expected_classes = {
        "PASS", "POLICY_HOLD", "POLICY_DENY", "CI_EVIDENCE_HYDRATION_FAILURE",
        "STALE_EXACT_HEAD", "CONTRACT_ASSERTION_FAILURE", "SUPPLY_CHAIN_DENY", "RUNTIME_UNAVAILABLE",
    }
    require(set(gov["classifications"]) == expected_classes, "classification taxonomy drift")
    require(gov["ci_failure_implies_policy_hold"] is False, "CI failure must not imply HOLD")
    require(gov["ci_failure_implies_policy_deny"] is False, "CI failure must not imply DENY")
    require(gov["explicit_policy_marker_required"] is True, "explicit policy marker required")
    require(gov["exact_git_object_hydration_required"] is True, "exact git hydration required")
    require(gov["human_pr_body_mutated"] is False, "machine readback must not rewrite PR body")

    archive = manifest["archive_continuity"]
    require(archive["archive_format"] == "ct-chlom-encrypted-archive-v2", "archive format drift")
    require(archive["current_runtime_state"] == "READBACK_REQUIRED", "runtime truth must remain readback-gated")
    require(archive["runtime_activation_claimed_by_this_source"] is False, "source must not claim runtime activation")
    require(archive["new_top_level_scheduler_slot"] is False, "new scheduler slot prohibited")
    require(archive["plaintext_persisted"] is False, "archive plaintext persistence prohibited")
    require(archive["ciphertext_checkpointed"] is True, "ciphertext checkpoints required")
    require(archive["database_restart_behavior"] == "RESUME_FROM_LAST_COMMITTED_CHUNK", "restart semantics drift")
    require(archive["caught_error_behavior"] == "HOLD_NO_AUTOMATIC_RETRY", "caught-error semantics drift")
    dated = archive["dated_v21_evidence"]
    require(dated["observed_on"] == "2026-08-23", "historical evidence date missing")
    require(dated["is_current_progress_claim"] is False, "historical archive progress cannot be current-state claim")

    require("POLICY_MARKER" in classifier and "policy_disposition_inferred" in classifier, "classifier policy firewall missing")
    require("CI_EVIDENCE_HYDRATION_FAILURE" in classifier and "STALE_EXACT_HEAD" in classifier, "classifier source classes missing")
    require("dict(os.environ)" not in classifier, "classifier must not ingest the full environment")
    require("print(payload)" not in classifier, "classification payload must not be logged")
    require("raw workflow logs were not emitted" in classifier, "sensitive-log firewall acknowledgement missing")

    require("ct-governance-observability-v2" in readback, "machine comment marker missing")
    legacy_firewall = "Institutional disposition: `NOT_DERIVED_FROM_CI`" in readback
    phase35_firewall = all(
        marker in readback
        for marker in (
            "Evidence disposition:",
            "CHLOM/D3 disposition created by this readback: `NONE`",
            '"institutional_state": "HOLD_EVIDENCE"',
            '"authority_created": "NONE"',
        )
    )
    require(
        legacy_firewall or phase35_firewall,
        "interpretation firewall missing: CI/provider state must not manufacture institutional authority",
    )
    require("PentaNurture / PentaStatus" in readback, "current Penta ownership missing")
    require("pull_request_target:" in obs and "workflow_run:" in obs, "observability triggers incomplete")
    require("ref: ${{ github.event.repository.default_branch }}" in obs, "privileged event must execute canonical code")
    require("persist-credentials: false" in obs, "observability checkout must not persist credentials")

    require("CT_GIT_HEAD_SHA" in merge and "CT_GIT_BASE_SHA" in merge, "current merge gate must bind immutable SHAs")
    require("git cat-file -e" in merge, "current merge gate exact-object verification missing")
    require("github.event.pull_request.head.ref" not in merge, "mutable contributor head ref forbidden")
    require("persist-credentials: false" in merge, "merge-gate checkout must not persist credentials")
    require("governed_current_pr_preflight.py" in merge, "current PR preflight missing")

    require("A red CI job is not automatically" in standard, "institutional doctrine firewall missing")
    require("PentaNurture" in standard and "PentaStatus" in standard, "Phase 3 ownership doctrine missing")
    require("does not manufacture authority" in penta, "Penta capability authority firewall missing")
    require(all(value is False for value in manifest["hard_boundaries"].values()), "authority boundary widened")
    print("Phase-3 governance observability and archive continuity contract: PASS")


if __name__ == "__main__":
    main()
