#!/usr/bin/env python3
"""Validate current S103/S100 identity→engine/domain edges.

This validator preserves historical source rows while enforcing the current
post-founder-adjudication graph. ThriveTools SEO and OPT are distinct child
applications. Child evidence never promotes to the ThriveTools root, and
identity resolution never substitutes for current provider/runtime proof.
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
OPT_DOC = ROOT / "developers/thrivetools-opt-api-adapter.mdx"
PLAN = ROOT / "changelog/phase-2-99-plan.mdx"
GATE = ROOT / "technology/phase-3-readiness-gate.mdx"

EXPECTED_IDS = [
    "ct.platform.crownapps-thriveapps", "ct.platform.melanated-voices",
    "ct.platform.melanated-voices-platform", "ct.platform.melanated-voices-tv",
    "ct.platform.melanated-tv", "ct.platform.locticians-tv",
    "ct.platform.melanated-vault", "ct.platform.melanated-stock",
    "ct.platform.tame-gallery", "ct.asset.artful-mane-gallery",
    "ct.platform.thrivetools", "ct.platform.thrivetools-seo",
    "ct.platform.thrivetools-opt", "ct.platform.thriverelay",
    "ct.platform.the-mane-experience", "ct.platform.thrivemaps",
    "ct.platform.collab-portal", "ct.platform.thrivesupport",
    "ct.platform.crownthrive-support", "ct.platform.locticians",
    "ct.platform.thriveseat", "ct.platform.crownlytics",
    "ct.platform.crownpulse", "ct.platform.thrivepush",
    "ct.platform.crownfluence", "ct.platform.crown-affiliates",
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
    "ct.platform.thrivetools-seo": (set(), {"S100-PORT-018"}, {"S100-ENG-083"}, set()),
    "ct.platform.thrivetools-opt": (set(), {"S100-PORT-019"}, {"S100-ENG-062"}, set()),
    "ct.platform.thriverelay": ({"S103-PF-010"}, set(), {"S100-ENG-003"}, {"S100-DOM-003"}),
    "ct.platform.the-mane-experience": ({"S103-PF-022"}, {"S100-PORT-030"}, {"S100-ENG-035"}, {"S100-DOM-054"}),
    "ct.platform.thrivemaps": ({"S103-PF-069"}, {"S100-PORT-015"}, {"S100-ENG-038"}, {"S100-DOM-009"}),
    "ct.platform.collab-portal": ({"S103-PF-007"}, {"S100-PORT-009"}, set(), {"S100-DOM-078"}),
    "ct.platform.thrivesupport": ({"S103-PF-065"}, {"S100-PORT-010"}, set(), set()),
    "ct.platform.crownthrive-support": ({"S103-PF-065"}, {"S100-PORT-010"}, {"S100-ENG-043", "S100-ENG-044", "S100-ENG-045"}, {"S100-DOM-011"}),
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
    print(f"ERROR: {message}"); raise SystemExit(1)

def read(path: Path) -> str:
    if not path.is_file(): fail(f"Missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")

def require(path: Path, fragment: str) -> None:
    if fragment not in read(path): fail(f"Required fragment {fragment!r} missing from {path.relative_to(ROOT)}")

def main() -> int:
    data = json.loads(read(MANIFEST))
    if data.get("manifest_version") != "1.2.0": fail("Unexpected edge manifest version")
    if data.get("phase") != "2.99" or data.get("workstream") != "3A": fail("Unexpected phase/workstream identity")
    if data.get("edge_state") != "source_relationship_plus_governed_child_identity": fail("Unexpected edge state")
    if data.get("current_integration_certification") != "incomplete": fail("Current integration certification must remain incomplete")
    records = data.get("records", []); ids = [r.get("stable_id") for r in records]
    if ids != EXPECTED_IDS or len(set(ids)) != 27: fail(f"Stable-ID order/set drifted: {ids}")
    by_id = {r["stable_id"]: r for r in records}
    for stable_id, expected in EXPECTED.items():
        r = by_id[stable_id]
        actual = (set(r.get("s103_rows", [])), set(r.get("s100_portfolio_rows", [])), set(r.get("engine_rows", [])), set(r.get("domain_rows", [])))
        if actual != expected: fail(f"Edge drift for {stable_id}: {actual!r} != {expected!r}")
    s103_text, port_text, eng_text, dom_text = read(S103), read(PORT), read(ENG), read(DOM)
    refs_s103, refs_port, refs_eng, refs_dom = set(), set(), set(), set()
    for r in records:
        refs_s103.update(r.get("s103_rows", [])); refs_port.update(r.get("s100_portfolio_rows", [])); refs_eng.update(r.get("engine_rows", [])); refs_dom.update(r.get("domain_rows", []))
    if len(refs_eng) != 32: fail(f"Expected 32 unique effective engine source rows, found {len(refs_eng)}")
    if len(refs_dom) != 24: fail(f"Expected 24 unique effective domain source rows, found {len(refs_dom)}")
    for rid in refs_s103 | {"S103-PF-028"}:
        if f"id: {rid};" not in s103_text: fail(f"Missing S103 row {rid}")
    for rid in refs_port:
        if rid not in port_text: fail(f"Missing S100 portfolio row {rid}")
    for rid in refs_eng:
        if f"id: {rid};" not in eng_text: fail(f"Missing S100 engine row {rid}")
    for rid in refs_dom:
        if f"id: {rid};" not in dom_text: fail(f"Missing S100 domain row {rid}")
    viloud = {r["stable_id"] for r in records if "S100-ENG-025" in r.get("engine_rows", [])}
    if viloud != {"ct.platform.melanated-tv", "ct.platform.melanated-voices-tv", "ct.platform.locticians-tv"}: fail(f"Viloud holder set drifted: {viloud}")
    partnero = {r["stable_id"] for r in records if "S100-ENG-030" in r.get("engine_rows", [])}
    if partnero != {"ct.platform.crown-affiliates", "ct.platform.crown-ambassadors"}: fail(f"Partnero holder set drifted: {partnero}")
    if by_id["ct.platform.thrivesupport"].get("engine_rows") or by_id["ct.platform.thrivesupport"].get("domain_rows"): fail("ThriveSupport family inherited implementation edges")
    if set(by_id["ct.platform.crownthrive-support"].get("engine_rows", [])) != {"S100-ENG-043", "S100-ENG-044", "S100-ENG-045"}: fail("CrownThrive Support projection engine set drifted")
    if set(by_id["ct.platform.thrivetools"].get("engine_rows", [])) != {"S100-ENG-006"}: fail("ThriveTools root must retain only its root engine edge")
    if set(by_id["ct.platform.thrivetools-seo"].get("engine_rows", [])) != {"S100-ENG-083"}: fail("ThriveTools SEO child engine drifted")
    if set(by_id["ct.platform.thrivetools-opt"].get("engine_rows", [])) != {"S100-ENG-062"}: fail("ThriveTools OPT child engine drifted")
    if by_id["ct.platform.thrivetools-seo"].get("relationship_to_parent") != "child_of:ct.platform.thrivetools": fail("ThriveTools SEO parent relationship missing")
    if by_id["ct.platform.thrivetools-opt"].get("relationship_to_parent") != "child_of:ct.platform.thrivetools": fail("ThriveTools OPT parent relationship missing")
    if data.get("blocked_relationships") != []: fail("Current identity relationship layer must have zero blocked relationships")
    history = {x.get("key"): x for x in data.get("historical_resolved_relationships", [])}
    if set(history) != {"mvp_roku", "thrivetools_seo", "thrivetools_opt"}: fail("Historical resolved relationship set drifted")
    if history["mvp_roku"].get("current_resolution") != "merged_into_melanated_tv_lineage": fail("MVP Roku historical resolution drifted")
    if history["thrivetools_seo"].get("stable_id") != "ct.platform.thrivetools-seo": fail("ThriveTools SEO history resolution drifted")
    opt = history["thrivetools_opt"]
    if opt.get("stable_id") != "ct.platform.thrivetools-opt" or opt.get("documented_version") != "v4.0.0": fail("ThriveTools OPT history/version resolution drifted")
    if opt.get("http_method_certification") != "pending" or opt.get("authenticated_read") != "open" or opt.get("provider_writes") != "closed": fail("ThriveTools OPT fail-closed runtime state drifted")
    rules = data.get("rules", {})
    for key in ["source_relationship_is_current_certification", "shared_engine_collapses_platform_identity", "source_absence_allows_inference", "mvp_roku_current_provider_edge_inference", "shared_provider_collapses_program_identity", "family_inherits_projection_implementation", "child_capability_promotes_to_parent"]:
        if rules.get(key) is not False: fail(f"Rule {key} must remain false")
    if rules.get("child_identity_may_have_independent_edges") is not True: fail("Child independent-edge rule missing")
    require(PORT, "ct.platform.thrivetools-seo"); require(PORT, "ct.platform.thrivetools-opt")
    require(EDGE_DOC, "resolved_identity_records: 27"); require(EDGE_DOC, "blocked_relationship_records: 0")
    require(EDGE_DOC, "engine_source_rows_referenced: 32"); require(EDGE_DOC, "domain_source_rows_referenced: 24")
    require(OPT_DOC, "observed_product_version: v4.0.0"); require(OPT_DOC, "http_method_certification: pending"); require(OPT_DOC, "provider_writes_enabled: false")
    require(GATE, "current_owner_identity_disposition_unresolved: 0"); require(GATE, "blocked_pending_phase_2_99_hard_exit_and_full_docs_reconciliation")
    require(PLAN, "Workstream 3A — ThriveTools OPT API contract")
    print("S103/S100 engine-domain edge validation PASSED: 27 stable identities, 32 unique effective engine rows, 24 unique S100 domain rows, ThriveTools SEO/OPT resolved as child applications without root inheritance, historical blocked relationships preserved, provider/runtime certification still fail-closed where unproved, Phase 3 blocked.")
    return 0

if __name__ == "__main__": sys.exit(main())
