#!/usr/bin/env python3
"""Validate S103/S100 engine-domain identity edge tranche 2.

This validator protects referential integrity, shared-provider semantics,
projection boundaries, child-capability blocking and anti-promotion rules. It
validates dated source relationships only; it does not perform network calls or
claim current provider, deployment, entitlement, DNS, TLS or runtime state.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/s103-s100-engine-domain-edges.v1.json"
S103 = ROOT / "knowledge/phase-2-99-workstream-3a-phase-2-7-74-platform-framework-source-seed.mdx"
PORT = ROOT / "knowledge/phase-2-99-workstream-3a-holdings-68-source-row-identity-seed.mdx"
ENG = ROOT / "knowledge/phase-2-99-workstream-3a-holdings-85-engine-service-source-seed.mdx"
DOM = ROOT / "knowledge/phase-2-99-workstream-3a-holdings-82-domain-source-seed.mdx"
EDGE_DOC = ROOT / "knowledge/phase-2-99-workstream-3a-engine-domain-identity-edge-register.mdx"
CHANGELOG = ROOT / "changelog/phase-2-99-workstream-3a-engine-domain-identity-edge-tranche-2.mdx"
PLAN = ROOT / "changelog/phase-2-99-plan.mdx"
GATE = ROOT / "technology/phase-3-readiness-gate.mdx"
CHARTER = ROOT / "standards/ten-phase-institutional-program-charter.mdx"

EXPECTED_IDS = [
    "ct.platform.crownapps-thriveapps",
    "ct.platform.melanated-voices",
    "ct.platform.melanated-voices-platform",
    "ct.platform.melanated-voices-tv",
    "ct.platform.melanated-tv",
    "ct.platform.locticians-tv",
    "ct.platform.melanated-vault",
    "ct.platform.melanated-stock",
    "ct.platform.tame-gallery",
    "ct.asset.artful-mane-gallery",
    "ct.platform.thrivetools",
    "ct.platform.thriverelay",
    "ct.platform.the-mane-experience",
    "ct.platform.thrivemaps",
    "ct.platform.collab-portal",
    "ct.platform.thrivesupport",
    "ct.platform.CrownThrive-OS",
    "ct.platform.locticians",
    "ct.platform.thriveseat",
    "ct.platform.crownlytics",
    "ct.platform.crownpulse",
    "ct.platform.thrivepush",
    "ct.platform.crownfluence",
    "ct.platform.crown-affiliates",
    "ct.platform.crown-ambassadors",
]

EXPECTED = {
    "ct.platform.crownapps-thriveapps": ({"S103-PF-071"}, {"S100-PORT-020"}, {"S100-ENG-046", "S100-ENG-079"}, set()),
    "ct.platform.melanated-voices": (set(), {"S100-PORT-025"}, {f"S100-ENG-{i:03d}" for i in range(8, 16)}, {"S100-DOM-062"}),
    "ct.platform.melanated-voices-platform": ({"S103-PF-025"}, {"S100-PORT-027"}, set(), {"S100-DOM-024"}),
    "ct.platform.melanated-voices-tv": ({"S103-PF-026"}, {"S100-PORT-028"}, {"S100-ENG-025"}, {"S100-DOM-026"}),
    "ct.platform.melanated-tv": ({"S103-PF-027"}, {"S100-PORT-026"}, {"S100-ENG-025", "S100-ENG-026", "S100-ENG-027"}, {"S100-DOM-025"}),
    "ct.platform.locticians-tv": ({"S103-PF-029"}, {"S100-PORT-029"}, {"S100-ENG-025"}, set()),
    "ct.platform.melanated-vault": ({"S103-PF-032"}, {"S100-PORT-034"}, {"S100-ENG-036"}, {"S100-DOM-021"}),
    "ct.platform.melanated-stock": ({"S103-PF-033"}, {"S100-PORT-035"}, {"S100-ENG-053"}, {"S100-DOM-022"}),
    "ct.platform.tame-gallery": ({"S103-PF-034"}, {"S100-PORT-031"}, {"S100-ENG-059"}, {"S100-DOM-042", "S100-DOM-043"}),
    "ct.asset.artful-mane-gallery": ({"S103-PF-035"}, {"S100-PORT-036"}, set(), {"S100-DOM-076"}),
    "ct.platform.thrivetools": ({"S103-PF-009"}, {"S100-PORT-017"}, {"S100-ENG-006"}, {"S100-DOM-057"}),
    "ct.platform.thriverelay": ({"S103-PF-010"}, set(), {"S100-ENG-003"}, {"S100-DOM-003"}),
    "ct.platform.the-mane-experience": ({"S103-PF-022"}, {"S100-PORT-030"}, {"S100-ENG-035"}, {"S100-DOM-054"}),
    "ct.platform.thrivemaps": ({"S103-PF-069"}, {"S100-PORT-015"}, {"S100-ENG-038"}, {"S100-DOM-009"}),
    "ct.platform.collab-portal": ({"S103-PF-007"}, {"S100-PORT-009"}, set(), {"S100-DOM-078"}),
    "ct.platform.thrivesupport": ({"S103-PF-065"}, {"S100-PORT-010"}, set(), set()),
    "ct.platform.CrownThrive-OS": ({"S103-PF-065"}, {"S100-PORT-010"}, {"S100-ENG-043", "S100-ENG-044", "S100-ENG-045"}, {"S100-DOM-011"}),
    "ct.platform.locticians": ({"S103-PF-011"}, {"S100-PORT-037"}, set(), {"S100-DOM-063", "S100-DOM-064", "S100-DOM-073"}),
    "ct.platform.thriveseat": ({"S103-PF-021"}, {"S100-PORT-038"}, {"S100-ENG-031", "S100-ENG-032"}, {"S100-DOM-029"}),
    "ct.platform.crownlytics": ({"S103-PF-042"}, {"S100-PORT-012"}, {"S100-ENG-085"}, {"S100-DOM-058"}),
    "ct.platform.crownpulse": ({"S103-PF-043"}, {"S100-PORT-013"}, {"S100-ENG-005"}, {"S100-DOM-060"}),
    "ct.platform.thrivepush": ({"S103-PF-044"}, {"S100-PORT-014"}, {"S100-ENG-082"}, {"S100-DOM-056"}),
    "ct.platform.crownfluence": ({"S103-PF-046"}, {"S100-PORT-060"}, {"S100-ENG-057"}, {"S100-DOM-047"}),
    "ct.platform.crown-affiliates": ({"S103-PF-048"}, {"S100-PORT-061"}, {"S100-ENG-030"}, {"S100-DOM-040"}),
    "ct.platform.crown-ambassadors": ({"S103-PF-047"}, {"S100-PORT-062"}, {"S100-ENG-030"}, set()),
}


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def text(path: Path) -> str:
    if not path.is_file():
        fail(f"Missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(path: Path, fragment: str) -> None:
    if fragment not in text(path):
        fail(f"Required fragment {fragment!r} missing from {path.relative_to(ROOT)}")


def main() -> int:
    if not MANIFEST.is_file():
        fail(f"Missing manifest: {MANIFEST.relative_to(ROOT)}")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if data.get("manifest_version") != "1.1.0":
        fail("Unexpected edge manifest version")
    if data.get("phase") != "3" or data.get("historical_origin_phase") != "2.99":
        fail("Edge registry must remain Phase 3 with explicit historical origin")
    if data.get("historical_source_workstream") != "3A":
        fail("Historical source-workstream identity drifted")
    if data.get("baseline_commit") != "461fb7085510c29b4a605bdb1996903b534a7996":
        fail("Baseline commit drifted")
    if data.get("edge_state") != "source_relationship_only":
        fail("Edge state must remain source_relationship_only")
    if data.get("current_integration_certification") != "incomplete":
        fail("Current integration certification must remain incomplete")

    records = data.get("records", [])
    stable_ids = [record.get("stable_id") for record in records]
    if stable_ids != EXPECTED_IDS:
        fail(f"Stable-ID order/set drifted: {stable_ids}")
    if len(set(stable_ids)) != 25:
        fail("Expected 25 unique stable identities in tranche 2")

    record_by_id = {record["stable_id"]: record for record in records}
    for stable_id, expected in EXPECTED.items():
        record = record_by_id[stable_id]
        actual = (
            set(record.get("s103_rows", [])),
            set(record.get("s100_portfolio_rows", [])),
            set(record.get("engine_rows", [])),
            set(record.get("domain_rows", [])),
        )
        if actual != expected:
            fail(f"Edge drift for {stable_id}: {actual!r} != {expected!r}")

    s103_text = text(S103)
    port_text = text(PORT)
    eng_text = text(ENG)
    dom_text = text(DOM)

    referenced_s103: set[str] = set()
    referenced_ports: set[str] = set()
    referenced_engines: set[str] = set()
    referenced_domains: set[str] = set()
    for record in records:
        referenced_s103.update(record.get("s103_rows", []))
        referenced_ports.update(record.get("s100_portfolio_rows", []))
        referenced_engines.update(record.get("engine_rows", []))
        referenced_domains.update(record.get("domain_rows", []))

    if len(referenced_engines) != 30:
        fail(f"Expected 30 unique effective engine source rows, found {len(referenced_engines)}")
    if len(referenced_domains) != 24:
        fail(f"Expected 24 unique effective domain source rows, found {len(referenced_domains)}")

    for row_id in referenced_s103 | {"S103-PF-028"}:
        if f"id: {row_id};" not in s103_text:
            fail(f"Missing referenced S103 source row {row_id}")
    for row_id in referenced_ports | {"S100-PORT-018", "S100-PORT-019", "S100-PORT-027", "S100-PORT-028"}:
        if row_id not in port_text:
            fail(f"Missing referenced S100 portfolio row {row_id}")
    for row_id in referenced_engines | {"S100-ENG-062", "S100-ENG-083"}:
        if f"id: {row_id};" not in eng_text:
            fail(f"Missing referenced S100 engine row {row_id}")
    for row_id in referenced_domains:
        if f"id: {row_id};" not in dom_text:
            fail(f"Missing referenced S100 domain row {row_id}")

    viloud_holders = {
        record["stable_id"]
        for record in records
        if "S100-ENG-025" in record.get("engine_rows", [])
    }
    expected_viloud = {
        "ct.platform.melanated-tv",
        "ct.platform.melanated-voices-tv",
        "ct.platform.locticians-tv",
    }
    if viloud_holders != expected_viloud:
        fail(f"Viloud shared-engine invariant drifted: {viloud_holders}")
    if "S100-ENG-025" in record_by_id["ct.platform.melanated-voices-platform"].get("engine_rows", []):
        fail("MVP orchestration must not inherit Viloud by naming proximity")

    partnero_holders = {
        record["stable_id"]
        for record in records
        if "S100-ENG-030" in record.get("engine_rows", [])
    }
    expected_partnero = {"ct.platform.crown-affiliates", "ct.platform.crown-ambassadors"}
    if partnero_holders != expected_partnero:
        fail(f"Partnero shared-provider invariant drifted: {partnero_holders}")

    support_family = record_by_id["ct.platform.thrivesupport"]
    if support_family.get("engine_rows") or support_family.get("domain_rows"):
        fail("ThriveSupport family must not inherit CrownThrive Support implementation edges")
    support_projection = record_by_id["ct.platform.CrownThrive-OS"]
    if set(support_projection.get("engine_rows", [])) != {"S100-ENG-043", "S100-ENG-044", "S100-ENG-045"}:
        fail("CrownThrive Support implementation engine set drifted")
    if set(support_projection.get("domain_rows", [])) != {"S100-DOM-011"}:
        fail("CrownThrive Support implementation domain set drifted")

    root_tools = record_by_id["ct.platform.thrivetools"]
    if "S100-ENG-083" in root_tools.get("engine_rows", []) or "S100-ENG-062" in root_tools.get("engine_rows", []):
        fail("ThriveTools root must not silently inherit SEO/OPT child engines")
    if record_by_id["ct.platform.collab-portal"].get("engine_rows"):
        fail("Collab Portal must not invent an S100 85-engine row")
    if record_by_id["ct.platform.locticians"].get("engine_rows"):
        fail("Locticians must not invent Brilliant Directories as an S100 85-engine row")

    blocked = data.get("blocked_relationships", [])
    if len(blocked) != 3:
        fail(f"Expected exactly three blocked relationships in tranche 2, found {len(blocked)}")

    mvp = blocked[0]
    if mvp.get("source_row") != "S103-PF-028" or mvp.get("source_name") != "MVP (Roku)":
        fail("MVP Roku blocked relationship identity drifted")
    if mvp.get("relationship_state") != "unresolved_fail_closed":
        fail("MVP Roku must remain unresolved_fail_closed")
    if mvp.get("effective_engine_rows") or mvp.get("effective_domain_rows"):
        fail("MVP Roku must not receive effective engine/domain edges")
    if set(mvp.get("candidate_portfolio_rows", [])) != {"S100-PORT-027", "S100-PORT-028"}:
        fail("MVP Roku candidate portfolio context drifted")

    expected_children = {
        "ThriveTools SEO": ("S100-PORT-018", "S100-ENG-083"),
        "ThriveTools OPT": ("S100-PORT-019", "S100-ENG-062"),
    }
    child_rows = {entry.get("source_name"): entry for entry in blocked[1:]}
    if set(child_rows) != set(expected_children):
        fail(f"Blocked ThriveTools child set drifted: {set(child_rows)}")
    for name, (portfolio_row, engine_row) in expected_children.items():
        entry = child_rows[name]
        if entry.get("portfolio_row") != portfolio_row or entry.get("engine_row") != engine_row:
            fail(f"Blocked source relationship drifted for {name}")
        if entry.get("relationship_state") != "parent_child_resolution_pending":
            fail(f"{name} must remain parent_child_resolution_pending")
        if entry.get("candidate_parent") != "ct.platform.thrivetools":
            fail(f"Unexpected candidate parent for {name}")
        if entry.get("effective_engine_rows") or entry.get("effective_domain_rows"):
            fail(f"{name} must not receive effective engine/domain edges before adjudication")

    rules = data.get("rules", {})
    required_false_rules = [
        "source_relationship_is_current_certification",
        "shared_engine_collapses_platform_identity",
        "source_absence_allows_inference",
        "shared_provider_collapses_program_identity",
        "family_inherits_projection_implementation",
        "child_capability_promotes_to_parent",
    ]
    for rule in required_false_rules:
        if rules.get(rule) is not False:
            fail(f"Rule {rule} must remain false")
    if rules.get("mvp_roku_fail_closed") is not True:
        fail("MVP Roku fail-closed rule missing")

    require(EDGE_DOC, "resolved_identity_records: 25")
    require(EDGE_DOC, "blocked_relationship_records: 3")
    require(EDGE_DOC, "engine_source_rows_referenced: 30")
    require(EDGE_DOC, "domain_source_rows_referenced: 24")
    require(EDGE_DOC, "relationship_state: parent_child_resolution_pending")
    require(CHANGELOG, "documentation_impact: docs_updated")
    require(CHANGELOG, "No downstream hard gate is widened")
    require(PLAN, "Tranche 2")
    require(GATE, "Tranche 2")
    require(GATE, "blocked_pending_phase_2_99_hard_exit")
    require(CHARTER, "Tranche 2")
    require(CHARTER, "Partnero")

    print(
        "S103/S100 engine-domain edge validation PASSED: "
        "25 stable identities, 30 unique effective engine rows, 24 unique effective domain rows, "
        "Viloud and Partnero shared-provider sets preserved, ThriveSupport projection boundary preserved, "
        "ThriveTools child capabilities remain blocked, MVP Roku remains fail-closed, "
        "current integration certification remains incomplete."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
