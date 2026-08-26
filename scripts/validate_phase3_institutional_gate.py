#!/usr/bin/env python3
"""Validate the CrownThrive Phase 3 institutional gate without rewriting historical evidence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/phase3-institutional-gate.v1.json"
CURRENT = ROOT / "docs/phase3/CURRENT_STATE.md"
VERSIONS = ROOT / "docs/versioning/VERSION_REGISTRY.json"
RELEASE = ROOT / "releases/v3.0.0/MANIFEST.json"
AGENTS = ROOT / "AGENTS.md"
PR_TEMPLATE = ROOT / ".github/pull_request_template.md"
SECURITY = ROOT / "SECURITY.md"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing required Phase 3 gate file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(path: Path, fragment: str) -> None:
    if fragment not in read(path):
        fail(f"missing {fragment!r} in {path.relative_to(ROOT)}")


def main() -> int:
    gate = json.loads(read(MANIFEST))
    expected = {
        "schema_version": "1.0.0",
        "gate_id": "ct.gate.phase3.institutional.v1",
        "institutional_generation": "phase_3",
        "os_release_line": "3.x",
        "current_state_path": "docs/phase3/CURRENT_STATE.md",
        "version_registry_path": "docs/versioning/VERSION_REGISTRY.json",
        "release_manifest_path": "releases/v3.0.0/MANIFEST.json",
        "projection_product": "PentaDocs",
        "projection_vendor": "Mintlify",
        "projection_rule": "downstream_projection_cannot_override_os_state",
        "component_certification": "independent_subsystem_by_subsystem_evidence_by_evidence",
        "historical_phase_2_99_evidence": "preserved_noncurrent",
        "holds_preserved": True,
        "d3_human_reserved": True,
        "phase_label_is_blanket_certification": False,
        "provider_capability_is_write_authority": False,
        "source_acceptance_equals_live_deployment": False,
    }
    for key, value in expected.items():
        if gate.get(key) != value:
            fail(f"Phase 3 gate drift: {key}={gate.get(key)!r}, expected {value!r}")

    forbidden = set(gate.get("forbidden_promotions", []))
    required_forbidden = {
        "phase_3_to_blanket_component_certification",
        "hold_to_pass_without_required_evidence",
        "provider_capability_to_provider_wide_write_authority",
        "workflow_success_to_live_deployment_without_readback",
        "projection_state_to_os_authority",
        "historical_phase_2_99_block_to_current_institutional_state",
        "agent_or_quorum_to_d3_authority",
    }
    if not required_forbidden.issubset(forbidden):
        fail("Phase 3 forbidden-promotion set is incomplete")

    registry = json.loads(read(VERSIONS))
    if registry.get("institutional_generation") != "phase_3":
        fail("version registry is not on institutional generation phase_3")
    umbrella = str(registry.get("umbrella_release", ""))
    if not umbrella.startswith("3."):
        fail(f"version registry umbrella release must remain on the 3.x line for this gate; got {umbrella!r}")
    rules = registry.get("rules", {})
    for key in (
        "component_versions_are_independent",
        "silent_replacement_prohibited",
        "archive_superseded_material",
        "phase_label_does_not_imply_component_certification",
        "hold_never_promoted_by_version_only",
        "d3_human_reserved",
    ):
        if rules.get(key) is not True:
            fail(f"version registry Phase 3 rule must remain true: {key}")

    # v3.0.0 is the immutable Phase-3 entry manifest. Later 3.x umbrella
    # releases may advance independently without rewriting that historical
    # release identity or weakening the Phase-3 institutional boundary.
    release = json.loads(read(RELEASE))
    if release.get("version") != "3.0.0" or release.get("tag") != "v3.0.0":
        fail("Phase 3 entry release manifest identity drift")

    require(CURRENT, "**Institutional generation:** Phase 3 / CrownThrive OS 3.x")
    require(CURRENT, "CrownThrive is operating in **Phase 3**")
    require(CURRENT, "Phase 3 does **not** mean")
    require(CURRENT, "`HOLD`")
    require(CURRENT, "subsystem-by-subsystem and evidence-by-evidence")
    require(CURRENT, "PentaDocs")

    require(AGENTS, "institutional generation: `Phase 3`")
    require(AGENTS, "production/certification: subsystem-by-subsystem and evidence-by-evidence")
    require(AGENTS, "a Phase 3 umbrella does not force v1/v2 contracts to become v3")
    require(AGENTS, "`HOLD` never becomes `PASS`")
    require(PR_TEMPLATE, "Institutional generation: `Phase 3`")
    require(PR_TEMPLATE, "Phase 3 is not used as blanket production certification")
    require(PR_TEMPLATE, "Homepage control-state invariant passes")
    require(SECURITY, "Phase 3 does not imply every subsystem is production-certified")
    require(SECURITY, "Continuous Security Governance")

    # Historical Phase 2/2.99 records remain valid evidence. This gate deliberately
    # does not require rewriting their bodies; it only prevents those historical
    # labels from being treated as the current institution-wide state.
    current_text = read(CURRENT)
    if "Phase 3 remains `blocked_pending_phase_2_99_hard_exit`" in current_text:
        fail("historical Phase 2.99 blocked state leaked into canonical Phase 3 current state")

    print(json.dumps({
        "status": "PASS",
        "institutional_generation": "phase_3",
        "os_release_line": "3.x",
        "umbrella_release": umbrella,
        "component_certification": "independent",
        "holds_preserved": True,
        "d3_human_reserved": True,
        "projection_product": "PentaDocs",
        "historical_phase_2_99_evidence": "preserved_noncurrent",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
