#!/usr/bin/env python3
"""Validate the first S103/S100 engine-domain identity edge tranche.

The validator protects referential integrity and anti-promotion invariants. It
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
CHANGELOG = ROOT / "changelog/phase-2-99-workstream-3a-engine-domain-identity-edge-tranche-1.mdx"
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

    if data.get("manifest_version") != "1.0.0":
        fail("Unexpected edge manifest version")
    if data.get("phase") != "2.99" or data.get("workstream") != "3A":
        fail("Unexpected phase/workstream identity")
    if data.get("baseline_commit") != "da468c7659f681cd800897c01db82c59fd102c39":
        fail("Baseline commit drifted")
    if data.get("edge_state") != "source_relationship_only":
        fail("Edge state must remain source_relationship_only")
    if data.get("current_integration_certification") != "incomplete":
        fail("Current integration certification must remain incomplete in tranche 1")

    records = data.get("records", [])
    stable_ids = [record.get("stable_id") for record in records]
    if stable_ids != EXPECTED_IDS:
        fail(f"Stable-ID order/set drifted: {stable_ids}")
    if len(set(stable_ids)) != len(stable_ids):
        fail("Duplicate stable identity in edge manifest")

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

    referenced_s103 = set()
    referenced_ports = set()
    referenced_engines = set()
    referenced_domains = set()
    for record in records:
        referenced_s103.update(record.get("s103_rows", []))
        referenced_ports.update(record.get("s100_portfolio_rows", []))
        referenced_engines.update(record.get("engine_rows", []))
        referenced_domains.update(record.get("domain_rows", []))

    if len(referenced_engines) != 16:
        fail(f"Expected 16 unique engine source rows, found {len(referenced_engines)}")
    if len(referenced_domains) != 9:
        fail(f"Expected 9 unique domain source rows, found {len(referenced_domains)}")

    for row_id in referenced_s103 | {"S103-PF-028"}:
        if f"id: {row_id};" not in s103_text:
            fail(f"Missing referenced S103 source row {row_id}")
    for row_id in referenced_ports | {"S100-PORT-027", "S100-PORT-028"}:
        if row_id not in port_text:
            fail(f"Missing referenced S100 portfolio row {row_id}")
    for row_id in referenced_engines:
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

    blocked = data.get("blocked_relationships", [])
    if len(blocked) != 1:
        fail("Expected exactly one blocked relationship in tranche 1")
    mvp = blocked[0]
    if mvp.get("source_row") != "S103-PF-028" or mvp.get("source_name") != "MVP (Roku)":
        fail("MVP Roku blocked relationship identity drifted")
    if mvp.get("relationship_state") != "unresolved_fail_closed":
        fail("MVP Roku must remain unresolved_fail_closed")
    if mvp.get("effective_engine_rows") or mvp.get("effective_domain_rows"):
        fail("MVP Roku must not receive effective engine/domain edges")
    if set(mvp.get("candidate_portfolio_rows", [])) != {"S100-PORT-027", "S100-PORT-028"}:
        fail("MVP Roku candidate portfolio context drifted")

    rules = data.get("rules", {})
    if rules.get("source_relationship_is_current_certification") is not False:
        fail("Source relationship must never equal current certification")
    if rules.get("shared_engine_collapses_platform_identity") is not False:
        fail("Shared engine must not collapse platform identity")
    if rules.get("source_absence_allows_inference") is not False:
        fail("Source absence must not permit inferred edges")
    if rules.get("mvp_roku_fail_closed") is not True:
        fail("MVP Roku fail-closed rule missing")

    require(EDGE_DOC, "engine_source_rows_referenced: 16")
    require(EDGE_DOC, "domain_source_rows_referenced: 9")
    require(EDGE_DOC, "relationship_state: unresolved_fail_closed")
    require(CHANGELOG, "documentation_impact: docs_updated")
    require(CHANGELOG, "No downstream hard gate is widened")
    require(PLAN, "Engine/Domain Identity Edge Register")
    require(GATE, "Engine/Domain Identity Edge Register")
    require(GATE, "blocked_pending_phase_2_99_hard_exit")
    require(CHARTER, "shared provider such as Viloud")

    print(
        "S103/S100 engine-domain edge validation PASSED: "
        "10 stabilized identities, 16 unique engine rows, 9 unique domain rows, "
        "Viloud remains shared across 3 distinct platform identities, MVP orchestration inherits no TV engine, "
        "MVP Roku remains fail-closed, current integration certification remains incomplete."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
