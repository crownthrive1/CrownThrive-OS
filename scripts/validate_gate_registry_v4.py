#!/usr/bin/env python3
"""Validate the CrownThrive Phase-4 gate contract while preserving Phase-3 execution authority.

The single required merge context is applicability-driven. Legacy/global audits may remain
available as advisory or program-level controls, but they must not become unconditional
vetoes for an unrelated exact PR diff.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "developers/manifests/phase4-gate-contract.v4.json"
DOCS_WORKFLOW = ROOT / ".github/workflows/docs-governance.yml"
MERGE_WORKFLOW = ROOT / ".github/workflows/governed-merge-gate.yml"
APPLICABILITY_POLICY = ROOT / "config/penta_pr_gate_applicability.json"
APPLICABILITY_RESOLVER = ROOT / "scripts/resolve_pr_gate_applicability.py"

ALLOWED_SOURCE_GENERATIONS = {
    "unversioned_legacy_name",
    "legacy_v2_name",
    "legacy_v3_name",
    "legacy_phase_2_99_name",
    "phase_3_name",
}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing required Phase-4 preparation artifact: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(text: str, fragment: str, message: str) -> None:
    if fragment not in text:
        fail(message)


def main() -> int:
    registry = json.loads(read(REGISTRY))
    expected = {
        "schema": "ct.governance.gate-registry.v4",
        "registry_version": "4.0.0",
        "current_institutional_phase": 3,
        "target_phase": 4,
        "phase4_state": "PREPARATION",
        "canonical_required_status_context": "CrownThrive governed merge gate",
    }
    for key, value in expected.items():
        if registry.get(key) != value:
            fail(f"V4 gate registry drift: {key}={registry.get(key)!r}, expected {value!r}")

    compatibility = registry.get("compatibility", {})
    if compatibility.get("accepted_contract_generations") != [1, 2, 3, 4]:
        fail("V4 compatibility generations must remain exactly [1, 2, 3, 4]")
    for key in (
        "legacy_workflow_names_preserved",
        "legacy_status_context_preserved",
        "phase3_execution_authority_preserved_during_preparation",
        "phase3_validator_remains_binding",
        "v4_envelope_may_not_promote_hold_to_pass",
        "v4_envelope_may_not_manufacture_provider_authority",
        "v4_envelope_may_not_manufacture_d3_authority",
    ):
        if compatibility.get(key) is not True:
            fail(f"V4 compatibility invariant must remain true: {key}")

    rules = registry.get("rules", {})
    for key in (
        "all_registered_workflows_must_exist",
        "gate_ids_unique",
        "workflow_paths_unique",
        "exactly_one_required_merge_perimeter",
        "phase4_preparation_is_not_phase4_activation",
        "legacy_contracts_are_adapted_not_silently_rewritten",
        "backward_compatibility_is_fail_closed",
    ):
        if rules.get(key) is not True:
            fail(f"V4 gate rule must remain true: {key}")

    gates = registry.get("gates")
    if not isinstance(gates, list) or not gates:
        fail("V4 gate registry must contain registered gates")

    ids: set[str] = set()
    paths: set[str] = set()
    required: list[dict[str, object]] = []
    legacy_v2 = 0
    legacy_v3 = 0
    phase3_named = 0

    for gate in gates:
        if not isinstance(gate, dict):
            fail("V4 gate registry contains a non-object gate")
        gate_id = str(gate.get("gate_id", ""))
        workflow = str(gate.get("workflow", ""))
        source_generation = gate.get("source_generation")
        if not gate_id.endswith(".v4"):
            fail(f"Gate ID is not V4-canonical: {gate_id}")
        if gate_id in ids:
            fail(f"Duplicate gate ID: {gate_id}")
        if workflow in paths:
            fail(f"Duplicate workflow registration: {workflow}")
        ids.add(gate_id)
        paths.add(workflow)

        if gate.get("contract_version") != "4.0.0":
            fail(f"Gate is not on V4 contract: {gate_id}")
        if gate.get("phase4_state") != "PREPARED_COMPAT":
            fail(f"Gate is not Phase-4-prepared compatibility state: {gate_id}")
        if gate.get("legacy_workflow_path_preserved") is not True:
            fail(f"Legacy workflow identity must be preserved: {gate_id}")
        if source_generation not in ALLOWED_SOURCE_GENERATIONS:
            fail(f"Unknown source generation for {gate_id}: {source_generation!r}")

        path = ROOT / workflow
        if not path.is_file():
            fail(f"Registered gate workflow is missing: {workflow}")

        filename = path.name
        v2_named = bool(re.search(r"(?:^|[-_])v2(?:[-_.]|$)", filename) or "-002" in filename)
        phase3_named_workflow = "phase3" in filename
        if v2_named:
            legacy_v2 += 1
            if source_generation not in {"legacy_v2_name", "phase_3_name"}:
                fail(f"V2-named compatibility workflow lacks a compatible generation marker: {workflow}")
        if "-003" in filename:
            legacy_v3 += 1
            if source_generation != "legacy_v3_name":
                fail(f"V3-named compatibility workflow is not marked legacy_v3_name: {workflow}")
        if phase3_named_workflow:
            phase3_named += 1
            if source_generation != "phase_3_name":
                fail(f"Phase-3-named compatibility workflow is not marked phase_3_name: {workflow}")

        if gate.get("required_for_merge") is True:
            required.append(gate)

    if len(required) != 1:
        fail(f"Exactly one registered gate must own the required merge perimeter; found {len(required)}")
    if required[0].get("workflow") != ".github/workflows/governed-merge-gate.yml":
        fail("Required merge perimeter moved away from governed-merge-gate.yml")

    docs = read(DOCS_WORKFLOW)
    merge = read(MERGE_WORKFLOW)
    applicability = json.loads(read(APPLICABILITY_POLICY))
    resolver = read(APPLICABILITY_RESOLVER)

    # Documentation Governance remains a broad advisory/program audit and keeps the
    # compatibility validators. The provider-required merge context is narrower.
    for validator in ("scripts/validate_gate_registry_v4.py", "scripts/validate_phase3_institutional_gate.py"):
        if validator not in docs:
            fail(f"Documentation Governance dropped compatibility validator: {validator}")

    require(merge, "name: CrownThrive governed merge gate", "Stable required GitHub status context was renamed")
    require(merge, "scripts/resolve_pr_gate_applicability.py", "Governed Merge Gate lacks exact-diff applicability resolution")
    require(merge, "scripts/validate_gate_registry_v4.py", "Governed Merge Gate dropped V4 registry validation")
    require(merge, "if: steps.scope.outputs.phase_control == 'true'", "V4 phase-control validation is not applicability-scoped")
    require(merge, "scripts/validate_phase3_institutional_gate.py", "Governed Merge Gate dropped Phase-3 compatibility validation")
    require(merge, "if: steps.scope.outputs.phase3_state == 'true'", "Phase-3 compatibility validation is not exact-state scoped")
    if "scripts/run_phase4_preparation_audit.py" in merge:
        fail("Global Phase-4 preparation mega-audit must not be an unconditional required-merge veto")

    if applicability.get("schema") != "ct.penta.pr-gate-applicability.v1":
        fail("PR gate applicability policy schema drifted")
    groups = applicability.get("groups", {})
    for group_name in ("phase_control", "phase3_state", "security", "workflow_policy"):
        if group_name not in groups:
            fail(f"Applicability policy lacks required governance group: {group_name}")
    if "phase3_state" not in resolver or "NOT_APPLICABLE" not in resolver:
        fail("Applicability resolver does not preserve scoped Phase-3/NOT_APPLICABLE semantics")

    receipt = {
        "status": "PASS",
        "schema": "ct.governance.gate-registry.v4",
        "registry_version": "4.0.0",
        "current_phase": 3,
        "target_phase": 4,
        "phase4_state": "PREPARATION",
        "registered_gates": len(gates),
        "legacy_v2_named_workflows": legacy_v2,
        "legacy_v3_named_workflows": legacy_v3,
        "phase3_named_workflows": phase3_named,
        "backward_compatible_generations": [1, 2, 3, 4],
        "stable_required_status_context": "CrownThrive governed merge gate",
        "required_merge_applicability": "exact_diff_scoped",
        "phase3_state_gate": "conditional_on_affected_state_artifacts",
        "global_phase4_audit_in_required_perimeter": False,
        "phase3_execution_authority_preserved": True,
        "hold_promotion_forbidden": True,
        "authority_manufacture_forbidden": True,
    }
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
