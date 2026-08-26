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
PHASE_MODEL = ROOT / "docs/phase-model/PENTA_PHASE_MODEL.md"
RETIREMENT = ROOT / "docs/archive/PENTA_PHASE_RETIREMENT_MANIFEST.json"
CURRENT_PROJECTION = ROOT / "start-here/current-operational-state.mdx"
DOCS_CONFIG = ROOT / "docs.json"
HOMEPAGE_PROJECTION = ROOT / "developers/manifests/homepage-projection.v2.json"
HISTORICAL_NAMESPACE = ROOT / "developers/manifests/institutional-phase-namespace.v2.json"
ACTIVE_PHASE3_CONTROLS = (
    ROOT / "developers/manifests/agent-sovereign-governance.v1.json",
    ROOT / "developers/manifests/cpanel-hosting-control.v1.json",
    ROOT / "developers/manifests/github-main-enforcement-target.v1.json",
    ROOT / "developers/manifests/pm-notification-routing.v1.json",
    ROOT / "developers/manifests/repository-governance-enforcement-state.v1.json",
    ROOT / "developers/manifests/s103-s100-engine-domain-edges.v1.json",
    ROOT / "developers/manifests/security-self-healing-policy.v1.json",
    ROOT / "developers/manifests/github-actions-runtime-policy.v1.json",
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing required Phase 3 gate file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(path: Path, fragment: str) -> None:
    if fragment not in read(path):
        fail(f"missing {fragment!r} in {path.relative_to(ROOT)}")


def iter_navigation_contexts(node: object, context: tuple[str, ...] = ()):
    if isinstance(node, str):
        yield node, context
        return
    if isinstance(node, list):
        for item in node:
            yield from iter_navigation_contexts(item, context)
        return
    if not isinstance(node, dict):
        return
    label = node.get("group") or node.get("tab")
    next_context = context + ((str(label),) if label else ())
    for key in ("pages", "groups", "tabs", "dropdowns", "products", "versions", "languages"):
        if key in node:
            yield from iter_navigation_contexts(node[key], next_context)


def main() -> int:
    gate = json.loads(read(MANIFEST))
    expected = {
        "schema_version": "1.0.0",
        "gate_id": "ct.gate.phase3.institutional.v1",
        "institutional_generation": "phase_3",
        "os_release_line": "3.x",
        "current_state_path": "docs/phase3/CURRENT_STATE.md",
        "public_current_state_projection_path": "start-here/current-operational-state.mdx",
        "phase_model_path": "docs/phase-model/PENTA_PHASE_MODEL.md",
        "phase_retirement_manifest_path": "docs/archive/PENTA_PHASE_RETIREMENT_MANIFEST.json",
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
    umbrella_release = str(registry.get("umbrella_release", ""))
    if not umbrella_release.startswith("3."):
        fail("version registry umbrella release must remain on the 3.x line for this gate")
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

    release = json.loads(read(RELEASE))
    if release.get("version") != "3.0.0" or release.get("tag") != "v3.0.0":
        fail("Phase 3 release manifest identity drift")

    retirement = json.loads(read(RETIREMENT))
    if retirement.get("schema_version") != "1.1.0":
        fail("PENTA phase retirement manifest must use exact-record overlay schema 1.1.0")
    if retirement.get("current_phase") != 3 or retirement.get("current_phase_name") != "Phase 3 — Execute":
        fail("PENTA phase retirement manifest current phase drifted")
    retired_records = retirement.get("retired_records", [])
    retired_by_path = {item.get("path"): item for item in retired_records if isinstance(item, dict)}
    required_retired = {
        "developers/manifests/institutional-phase-namespace.v2.json": "not_public_navigation",
        "technology/phase-3-readiness-gate.mdx": "historical_group_only",
        "changelog/phase-2-99-plan.mdx": "historical_group_only",
        "standards/phases-3-4-5-charter.mdx": "historical_group_only",
        "standards/ten-phase-institutional-program-charter.mdx": "historical_group_only",
        "standards/twenty-phase-horizon-reconciliation.mdx": "historical_group_only",
        "changelog/adr-ten-phase-institutional-roadmap-migration.mdx": "historical_group_only",
        "changelog/adr-twenty-phase-impact-horizon-reconciliation.mdx": "historical_group_only",
    }
    for path, disposition in required_retired.items():
        item = retired_by_path.get(path)
        if not item:
            fail(f"Phase retirement manifest lacks exact supersession overlay for {path}")
        if item.get("navigation_disposition") != disposition:
            fail(f"Historical navigation disposition drifted for {path}")
        if item.get("archive_state") not in {"SUPERSEDED", "RETIRED_TIMELINE_ALIAS"}:
            fail(f"Historical archive state is not fail-closed for {path}")
        if not (ROOT / path).is_file():
            fail(f"Retirement overlay target is missing: {path}")

    historical_namespace = json.loads(read(HISTORICAL_NAMESPACE))
    historical_overlay = {
        "state": "historical_superseded_snapshot",
        "record_state": "historical_evidence",
        "historical_origin_phase": "2.99",
        "current_institutional_phase": 3,
        "current_institutional_phase_name": "Phase 3 — Execute",
        "current_successor": "docs/phase-model/PENTA_PHASE_MODEL.md",
        "current_phase": 2,
        "current_subphase": "2.99",
        "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
    }
    for key, value in historical_overlay.items():
        if historical_namespace.get(key) != value:
            fail(f"Historical namespace overlay drifted: {key}")

    for control_path in ACTIVE_PHASE3_CONTROLS:
        control = json.loads(read(control_path))
        if control.get("phase") != "3":
            fail(f"Active control manifest remains on a retired institutional phase: {control_path.relative_to(ROOT)}")
        if control_path.name != "github-actions-runtime-policy.v1.json" and control.get("historical_origin_phase") != "2.99":
            fail(f"Active migrated control lacks explicit historical origin: {control_path.relative_to(ROOT)}")
        if "phase_3_entry" in control or "phase_3_entry_effect" in control:
            fail(f"Active Phase 3 control still exposes a pre-entry field: {control_path.relative_to(ROOT)}")

    docs = json.loads(read(DOCS_CONFIG))
    contexts: dict[str, list[tuple[str, ...]]] = {}
    for page, context in iter_navigation_contexts(docs.get("navigation", {})):
        contexts.setdefault(page, []).append(context)
    current_contexts = contexts.get("start-here/current-operational-state", [])
    if not current_contexts or not all("Start Here" in context for context in current_contexts):
        fail("Current operational-state projection must remain in Start Here navigation")
    for path, disposition in required_retired.items():
        if disposition != "historical_group_only":
            continue
        page = path.rsplit(".", 1)[0]
        page_contexts = contexts.get(page, [])
        if not page_contexts:
            fail(f"Governed historical public record is absent from historical navigation: {page}")
        if not all("Historical Roadmaps & Phase Records" in context for context in page_contexts):
            fail(f"Superseded roadmap record escaped historical-only navigation: {page}")
        historical_text = read(ROOT / path)
        for marker in ("deprecated: true", "noindex: true", "Historical"):
            if marker not in historical_text:
                fail(f"Historical public record lacks {marker!r}: {path}")

    homepage_projection = json.loads(read(HOMEPAGE_PROJECTION))
    homepage_expected = {
        "current_state_projection_path": "start-here/current-operational-state.mdx",
        "canonical_current_state_path": "docs/phase3/CURRENT_STATE.md",
        "historical_phase_gate_path": "technology/phase-3-readiness-gate.mdx",
    }
    for key, value in homepage_expected.items():
        if homepage_projection.get(key) != value:
            fail(f"Homepage current/history projection mapping drifted: {key}")

    require(CURRENT, "**Institutional generation:** Phase 3 / CrownThrive OS 3.x")
    require(CURRENT, "CrownThrive is operating in **Phase 3**")
    require(CURRENT, "Phase 3 does **not** mean")
    require(CURRENT, "`HOLD`")
    require(CURRENT, "subsystem-by-subsystem and evidence-by-evidence")
    require(CURRENT, "PentaDocs")
    require(PHASE_MODEL, "**Current institutional phase:** **Phase 3 — Execute**")
    require(PHASE_MODEL, "Discover → Govern → Execute → Verify → Preserve")
    require(CURRENT_PROJECTION, "**Institutional phase:** Phase 3 — Execute")
    require(CURRENT_PROJECTION, f"**OS release:** CrownThrive OS `{umbrella_release}`")
    require(CURRENT_PROJECTION, "no blanket production promotion")
    require(CURRENT_PROJECTION, "Self-hosted runner production use remains held")

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
    if "blocked_pending_phase_2_99_hard_exit" in read(CURRENT_PROJECTION):
        fail("historical Phase 2.99 block leaked into public current-state projection")

    print(json.dumps({
        "status": "PASS",
        "institutional_generation": "phase_3",
        "os_release_line": "3.x",
        "component_certification": "independent",
        "holds_preserved": True,
        "d3_human_reserved": True,
        "projection_product": "PentaDocs",
        "historical_phase_2_99_evidence": "preserved_noncurrent",
        "historical_navigation": "isolated_and_machine_governed",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
