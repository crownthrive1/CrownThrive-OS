#!/usr/bin/env python3
"""Validate the CrownThrive governance-observability and archive-continuity contract."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/governance-observability-archive-continuity.v1.json"
CLASSIFIER = ROOT / "scripts/classify_governance_run.py"
READBACK = ROOT / "scripts/upsert_pr_governance_state.py"
OBS_WORKFLOW = ROOT / ".github/workflows/governance-observability.yml"
MERGE_WORKFLOW = ROOT / ".github/workflows/governed-merge-gate.yml"
STANDARD = ROOT / "standards/governance-observability-and-archive-continuity.mdx"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    for path in (MANIFEST, CLASSIFIER, READBACK, OBS_WORKFLOW, MERGE_WORKFLOW, STANDARD):
        require(path.is_file(), f"required artifact missing: {path.relative_to(ROOT)}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    classifier = CLASSIFIER.read_text(encoding="utf-8")
    readback = READBACK.read_text(encoding="utf-8")
    obs = OBS_WORKFLOW.read_text(encoding="utf-8")
    merge = MERGE_WORKFLOW.read_text(encoding="utf-8")
    standard = STANDARD.read_text(encoding="utf-8")

    require(manifest["schema"] == "ct.manifest.governance-observability-archive-continuity.v1", "manifest schema drift")
    require(manifest["state"] == "CONTROLLED_TEST_ACTIVE", "manifest must remain controlled-test")

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
    require(archive["active_controlled_test_version"] == 21, "active archive version drift")
    require(archive["prior_monolithic_automatic_retry"] is False, "monolithic retry must remain retired")
    require(25 <= archive["chunk_size"] <= 1000, "chunk size out of bounded range")
    require(1 <= archive["max_chunks_per_existing_css_hourly_cycle"] <= 8, "per-cycle chunk bound violated")
    require(archive["plaintext_persisted"] is False, "archive plaintext persistence prohibited")
    require(archive["ciphertext_checkpointed"] is True, "ciphertext checkpoints required")
    require(archive["new_top_level_scheduler_slot"] is False, "new scheduler slot prohibited")
    require(archive["database_restart_behavior"] == "RESUME_FROM_LAST_COMMITTED_CHUNK", "restart semantics drift")
    require(archive["caught_error_behavior"] == "HOLD_NO_AUTOMATIC_RETRY", "caught-error semantics drift")
    require(archive["expected_chunks"] > archive["canary_chunks_completed"] > 0, "archive canary evidence invalid")
    require(archive["canary_max_plaintext_chunk_bytes"] < 2_000_000, "canary chunk exceeds bounded evidence ceiling")

    require("POLICY_MARKER" in classifier and "policy_disposition_inferred" in classifier, "classifier policy firewall missing")
    require("CI_EVIDENCE_HYDRATION_FAILURE" in classifier and "STALE_EXACT_HEAD" in classifier, "classifier source-identity classes missing")
    require("ct-governance-observability-v1" in readback, "machine comment marker missing")
    require("Institutional disposition: `NOT_DERIVED_FROM_CI`" in readback, "PR interpretation firewall missing")
    require("pull_request_target:" in obs and "workflow_run:" in obs, "observability triggers incomplete")
    require("ref: ${{ github.event.repository.default_branch }}" in obs, "pull_request_target must execute canonical code")
    require("persist-credentials: false" in obs, "observability checkout must not persist credentials")
    require("Hydrate exact PR source identity" in merge, "merge-gate hydration step missing")
    require("git cat-file -e" in merge, "exact git object verification missing")
    require("classify_governance_run.py" in merge, "merge-gate classification missing")
    require("A red CI job is not automatically" in standard, "institutional doctrine firewall missing")

    require(all(value is False for value in manifest["hard_boundaries"].values()), "authority boundary widened")
    print("Governance observability and archive continuity contract: PASS")


if __name__ == "__main__":
    main()
