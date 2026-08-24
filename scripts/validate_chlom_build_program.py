#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "developers/manifests/chlom-build-cells.v1.json"
UPSTREAM = ROOT / "developers/manifests/chlom-upstream-components.v1.json"
UPSTREAM_FIXTURE = ROOT / "reference/chlom_runtime/fixtures/upstream_compatibility.v1.json"
GENERATOR = ROOT / "scripts/generate_chlom_living_status.py"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def require_nonempty(row: dict, fields: list[str], component_id: str) -> None:
    for field in fields:
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            fail(f"{component_id} missing non-empty intake field: {field}")


def main() -> int:
    cells = json.loads(CELLS.read_text(encoding="utf-8"))
    upstream = json.loads(UPSTREAM.read_text(encoding="utf-8"))
    fixture = json.loads(UPSTREAM_FIXTURE.read_text(encoding="utf-8"))

    if cells.get("phase") != "2.99" or cells.get("state") != "prototype_build_active_phase3_activation_blocked":
        fail("CHLOM build state must remain Phase 2.99 prototype / Phase 3 activation blocked")
    records = cells.get("cells", [])
    if len(records) != 10:
        fail(f"Expected exactly 10 CHLOM build cells, found {len(records)}")
    ids = [row.get("cell_id") for row in records]
    if len(ids) != len(set(ids)):
        fail("CHLOM cell IDs must be unique")
    if cells.get("rules", {}).get("cells_are_quorum_voters") is not False:
        fail("CHLOM subcells must not create extra sovereign votes")
    if cells.get("rules", {}).get("production_activation_before_phase3") is not False:
        fail("Phase 2.99 CHLOM packet cannot activate production")
    for excluded in cells.get("active_packet_exclusions", []):
        if any(excluded in path for row in records for path in row.get("scope", [])):
            fail(f"Cell scope collides with active governance packet path: {excluded}")

    expected_upstream = {
        "ct.upstream.opa": {
            "repository": "open-policy-agent/opa",
            "release": "v1.17.0",
            "commit": "64a3625d33bc6ad8e7c40df03b76ce2fb3ab4d21",
            "license": "Apache-2.0",
        },
        "ct.upstream.openfga": {
            "repository": "openfga/openfga",
            "release": "v1.18.1",
            "commit": "69efbd95b3d44afb2e2567d485dcc792c7d79e3f",
            "license": "Apache-2.0",
        },
        "ct.upstream.cedar": {
            "repository": "cedar-policy/cedar",
            "release": "v4.12.0",
            "commit": "fdcbaed32bdb8c8d13e4eaf2b58db5555e9fb8c5",
            "license": "Apache-2.0",
        },
        "ct.upstream.temporal": {
            "repository": "temporalio/temporal",
            "release": "v1.31.2",
            "commit": "19a774302c613da9adc4436ab14278ccdca8e0a5",
            "license": "MIT",
        },
    }
    candidates = upstream.get("candidates", [])
    by_id = {row.get("component_id"): row for row in candidates}
    if set(by_id) != set(expected_upstream):
        fail(f"Upstream candidate set drifted: {sorted(by_id)}")

    required_intake_fields = [
        "defined_need",
        "license_evidence",
        "notice_evidence",
        "patent_trademark_caveat",
        "maintenance_security_evidence",
        "sbom_dependency_posture",
        "privacy_data_posture",
        "compatibility_plan",
        "exit_fork_strategy",
        "upstream_contribution_strategy",
        "adoption_state",
    ]
    for component_id, expected in expected_upstream.items():
        row = by_id[component_id]
        for key, value in expected.items():
            if row.get(key) != value:
                fail(f"{component_id} {key} drifted: expected {value!r}, found {row.get(key)!r}")
        if row.get("release_commit_verified") is not True:
            fail(f"{component_id} exact release/commit verification must remain true")
        if row.get("chlom_authority") is not False:
            fail(f"{component_id} cannot become CHLOM institutional authority by manifest inference")
        if row.get("source_copied") is not False:
            fail(f"{component_id} source_copied must remain false until governed adoption")
        if "not_adopted" not in str(row.get("adoption_state", "")):
            fail(f"{component_id} must remain explicitly not adopted in this Phase 2.99 intake")
        require_nonempty(row, required_intake_fields, component_id)

    policy = upstream.get("policy", {})
    required_policy_true = [
        "defined_need_required_before_intake",
        "prefer_adapter_over_vendor_lock_in",
        "preserve_upstream_license_and_notice",
        "pin_release_or_commit_before_use",
        "security_review_before_runtime_adoption",
        "sbom_required_on_adoption",
        "privacy_data_review_required",
        "compatibility_fixture_required",
        "exit_and_fork_strategy_required",
        "contribute_generic_fixes_upstream_when_practical",
        "fork_only_when_needed_for_governed_divergence",
        "fork_does_not_transfer_upstream_trademark_or_authority",
        "no_copy_without_license_verification",
        "no_upstream_source_copied_by_this_intake",
        "provider_security_alert_unavailable_is_not_pass",
    ]
    for key in required_policy_true:
        if policy.get(key) is not True:
            fail(f"OSS intake policy invariant drifted: {key}")
    if set(policy.get("specialists", [])) != {"legal_regulatory", "security", "ip_rights_licensing"}:
        fail("OSS intake must retain Legal/Regulatory + Security + IP/Rights/Licensing specialist gates")

    decision = upstream.get("adoption_decision", {})
    if decision.get("state") != "hold_evaluation_only":
        fail("Upstream adoption decision must remain hold_evaluation_only in this tranche")

    if fixture.get("fixture_id") != "ct.fixture.chlom.upstream-compatibility.v1":
        fail("Upstream compatibility fixture identity drifted")
    if fixture.get("phase") != "2.99" or fixture.get("state") != "fixture_defined_not_executed_against_upstream":
        fail("Compatibility fixture must remain Phase 2.99 defined/not-executed until adoption gates pass")
    fixture_rules = fixture.get("rules", {})
    for key in (
        "no_upstream_source_or_package_required_to_validate_fixture",
        "provider_output_never_becomes_institutional_authority",
        "unknown_or_unavailable_provider_state_fails_closed",
        "restricted_evidence_body_must_not_be_required",
        "stable_crownthrive_ids_survive_provider_replacement",
        "execution_requires_separate_adoption_gate",
    ):
        if fixture_rules.get(key) is not True:
            fail(f"Compatibility fixture governance invariant drifted: {key}")

    fixture_rows = fixture.get("candidates", [])
    fixture_by_id = {row.get("component_id"): row for row in fixture_rows}
    if set(fixture_by_id) != set(expected_upstream):
        fail("Compatibility fixture candidate IDs must exactly match the governed intake manifest")
    for component_id, row in fixture_by_id.items():
        if row.get("execution_state") != "not_executed":
            fail(f"{component_id} compatibility execution cannot be promoted before isolated adoption testing")
        cases = row.get("required_cases", [])
        if not isinstance(cases, list) or len(cases) < 5 or len(cases) != len(set(cases)):
            fail(f"{component_id} must define at least five unique compatibility cases")
        require_nonempty(row, ["adapter_role", "acceptance"], component_id)

    promotion = fixture.get("promotion_gate", {})
    if promotion.get("current_decision") != "hold_evaluation_only":
        fail("Compatibility fixture promotion gate must remain hold_evaluation_only")
    required_before_execution = {
        "exact_candidate_version_or_commit_still_matches_intake",
        "legal_regulatory_endorsement",
        "security_endorsement",
        "ip_rights_licensing_endorsement",
        "dependency_sbom_and_vulnerability_review",
        "privacy_data_flow_review",
        "isolated_test_environment",
        "no_restricted_evidence_body_in_fixture_inputs",
    }
    if set(promotion.get("before_execution", [])) != required_before_execution:
        fail("Compatibility fixture pre-execution gates drifted")

    required_files = [
        ROOT / "reference/chlom_runtime/model.py",
        ROOT / "reference/chlom_runtime/policy.py",
        ROOT / "reference/chlom_runtime/dail.py",
        ROOT / "reference/chlom_runtime/docs_impact.py",
        ROOT / "reference/chlom_runtime/engine.py",
        ROOT / "reference/chlom_runtime/policies/core.v0.json",
        ROOT / "reference/chlom_runtime/tests/test_runtime.py",
        UPSTREAM_FIXTURE,
    ]
    for path in required_files:
        if not path.is_file():
            fail(f"Missing reference-runtime file: {path.relative_to(ROOT)}")

    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "reference.chlom_runtime.tests.test_runtime"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if tests.returncode != 0:
        sys.stderr.write(tests.stdout + tests.stderr)
        fail("CHLOM reference-runtime unit tests failed")

    with tempfile.TemporaryDirectory() as temp:
        output = Path(temp) / "status.md"
        generated = subprocess.run([sys.executable, str(GENERATOR), "--output", str(output)], cwd=ROOT)
        if generated.returncode != 0 or not output.is_file():
            fail("CHLOM living-status generation failed")
        text = output.read_text(encoding="utf-8")
        if "CHLOM Executable Build Status" not in text or "No upstream candidate is CHLOM authority" not in text:
            fail("Generated living status is missing governance invariants")

    print("CHLOM executable build-program validation: PASS")
    print("- 10 non-voting builder cells with bounded ownership")
    print("- reference kernel/policy/DAIL/docs-impact runtime tests: PASS")
    print("- OSS intake pins exact release/commit/license and preserves no-copy/no-authority state")
    print("- upstream compatibility contract fixture defined and held unexecuted pending adoption gates")
    print("- production activation remains blocked until Phase 3 hard entry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
