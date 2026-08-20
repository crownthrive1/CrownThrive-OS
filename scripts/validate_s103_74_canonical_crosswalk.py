#!/usr/bin/env python3
"""Validate the current S103 74-row canonical identity/disposition crosswalk.

The validator preserves the original S103 source census and the historical
stable-ID tranche evidence while enforcing the post-founder-adjudication
relationship schema. Identity/disposition closure is deliberately separate
from provider, deployment, runtime, domain, legal, rights, economic and
security certification. Phase 3 must remain fail-closed.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "knowledge/phase-2-99-workstream-3a-phase-2-7-74-platform-framework-source-seed.mdx"
CROSSWALK = ROOT / "knowledge/phase-2-99-workstream-3a-s103-74-canonical-identity-crosswalk.mdx"
S100 = ROOT / "knowledge/phase-2-99-workstream-3a-holdings-68-source-row-identity-seed.mdx"
TRANCHE1 = ROOT / "changelog/phase-2-99-workstream-3a-s103-stable-id-tranche-1.mdx"
TRANCHE2 = ROOT / "changelog/phase-2-99-workstream-3a-s103-stable-id-tranche-2.mdx"
THRIVERELAY = ROOT / "platforms/thriverelay-institutional-registry.mdx"
THRIVEMAPS = ROOT / "platforms/thrivemaps-institutional-registry.mdx"
BACKROAD = ROOT / "platforms/backroad-fm-institutional-registry.mdx"
MEDIA_FEDERATION = ROOT / "platforms/media-federation-institutional-registry.mdx"
D6 = ROOT / "knowledge/phase-2-98-d6-long-tail-platform-disposition-register.mdx"
PLATFORM_STATE = ROOT / "portfolio/platform-state-register.mdx"
ADAPTER_MATRIX = ROOT / "developers/platform-api-adapter-matrix.mdx"
PLAN = ROOT / "changelog/phase-2-99-plan.mdx"
GATE = ROOT / "technology/phase-3-readiness-gate.mdx"
TEN_PHASE_CHARTER = ROOT / "standards/ten-phase-institutional-program-charter.mdx"
TWENTY_PHASE_CHARTER = ROOT / "standards/twenty-phase-institutional-program-charter.mdx"
FOUNDER_ADJUDICATIONS = ROOT / "knowledge/founder-adjudications-2026-08-19.mdx"

SOURCE_RE = re.compile(
    r'^- id: (S103-PF-\d{3}); source_index: \d+; source_name: "([^"]+)"$',
    re.MULTILINE,
)
ROW_RE = re.compile(
    r'^\| `(S103-PF-\d{3})` \| ([^|]+?) \| `([^`]+)` \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \|$',
    re.MULTILINE,
)

EXPECTED_TYPES = {
    "exact": 43,
    "alias": 3,
    "predecessor": 3,
    "framework_platform_split": 3,
    "composite_split": 3,
    "reserve_identity": 6,
    "sunset_reserve": 2,
    "role_program_of": 1,
    "merged_into": 1,
    "provider_lineage_reserved": 1,
    "predecessor_concept": 1,
    "current_top_level_identity": 2,
    "program_series_of": 1,
    "sunset_repurpose": 1,
    "predecessor_alias": 1,
    "legacy_identity": 1,
    "subtool_of": 1,
    "unresolved": 0,
}

CRITICAL = {
    "S103-PF-001": ("composite_split", "ct.org.crownthrive-llc", "ct.platform.crownthrive"),
    "S103-PF-002": ("framework_platform_split", "ct.framework.chlom", "ct.platform.chlom"),
    "S103-PF-005": ("framework_platform_split", "ct.framework.mm-suites", "ct.platform.mm-suites"),
    "S103-PF-009": ("exact", "ct.platform.thrivetools"),
    "S103-PF-010": ("exact", "ct.platform.thriverelay"),
    "S103-PF-012": ("reserve_identity",),
    "S103-PF-013": ("sunset_reserve",),
    "S103-PF-014": ("sunset_reserve",),
    "S103-PF-017": ("reserve_identity",),
    "S103-PF-019": ("framework_platform_split", "ct.framework.mm-suites", "ct.platform.mm-suites"),
    "S103-PF-020": ("role_program_of", "ct.framework.mm-suites", "ct.platform.mm-suites"),
    "S103-PF-021": ("alias", "ct.platform.thriveseat"),
    "S103-PF-022": ("exact", "ct.platform.the-mane-experience"),
    "S103-PF-024": ("exact", "ct.platform.backroad-fm"),
    "S103-PF-025": ("exact", "ct.platform.melanated-voices-platform"),
    "S103-PF-026": ("exact", "ct.platform.melanated-voices-tv"),
    "S103-PF-027": ("exact", "ct.platform.melanated-tv"),
    "S103-PF-028": ("merged_into", "ct.platform.melanated-tv"),
    "S103-PF-029": ("exact", "ct.platform.locticians-tv"),
    "S103-PF-032": ("exact", "ct.platform.melanated-vault"),
    "S103-PF-033": ("exact", "ct.platform.melanated-stock"),
    "S103-PF-034": ("exact", "ct.platform.tame-gallery"),
    "S103-PF-035": ("exact", "ct.asset.artful-mane-gallery"),
    "S103-PF-036": ("provider_lineage_reserved",),
    "S103-PF-037": ("reserve_identity",),
    "S103-PF-053": ("predecessor_concept", "ct.platform.crownthrive-u"),
    "S103-PF-054": ("exact", "ct.platform.kjv-sermon-toolkit"),
    "S103-PF-055": ("current_top_level_identity", "ct.platform.thrive-ai-studio"),
    "S103-PF-056": ("current_top_level_identity", "ct.platform.neuralcraft-ai-studio"),
    "S103-PF-057": ("predecessor", "ct.platform.ops-oasis"),
    "S103-PF-058": ("composite_split", "ct.initiative.crownthrive-quantum"),
    "S103-PF-059": ("reserve_identity", "ct.brand.crownjewel"),
    "S103-PF-060": ("program_series_of", "ct.series.melanated-studios.storytime"),
    "S103-PF-061": ("reserve_identity",),
    "S103-PF-063": ("sunset_repurpose",),
    "S103-PF-064": ("predecessor_alias", "ct.platform.crownthrive-ecosystem-status"),
    "S103-PF-065": ("composite_split", "ct.platform.thrivesupport", "ct.platform.crownthrive-support"),
    "S103-PF-066": ("predecessor", "ct.platform.virality-music"),
    "S103-PF-067": ("predecessor", "ct.platform.crownthrive-studios"),
    "S103-PF-068": ("alias", "ct.platform.ops-oasis"),
    "S103-PF-069": ("exact", "ct.platform.thrivemaps"),
    "S103-PF-070": ("legacy_identity",),
    "S103-PF-071": ("alias", "ct.platform.crownapps-thriveapps"),
    "S103-PF-073": ("reserve_identity",),
    "S103-PF-074": ("subtool_of", "ct.platform.melanated-voices", "ct.platform.crownthrive-studios"),
}

TRANCHE_S100 = {
    "S100-PORT-015": "ct.platform.thrivemaps",
    "S100-PORT-017": "ct.platform.thrivetools",
    "S100-PORT-020": "ct.platform.crownapps-thriveapps",
    "S100-PORT-025": "ct.platform.melanated-voices",
    "S100-PORT-026": "ct.platform.melanated-tv",
    "S100-PORT-027": "ct.platform.melanated-voices-platform",
    "S100-PORT-028": "ct.platform.melanated-voices-tv",
    "S100-PORT-029": "ct.platform.locticians-tv",
    "S100-PORT-030": "ct.platform.the-mane-experience",
    "S100-PORT-031": "ct.platform.tame-gallery",
    "S100-PORT-034": "ct.platform.melanated-vault",
    "S100-PORT-035": "ct.platform.melanated-stock",
    "S100-PORT-036": "ct.asset.artful-mane-gallery",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def require(path: Path, fragment: str) -> None:
    if not path.is_file():
        fail(f"Missing required file: {path.relative_to(ROOT)}")
    if fragment not in path.read_text(encoding="utf-8"):
        fail(f"Required fragment {fragment!r} missing from {path.relative_to(ROOT)}")


def main() -> int:
    if not SOURCE.is_file():
        fail(f"Missing S103 source seed: {SOURCE.relative_to(ROOT)}")
    if not CROSSWALK.is_file():
        fail(f"Missing S103 canonical crosswalk: {CROSSWALK.relative_to(ROOT)}")

    source_text = SOURCE.read_text(encoding="utf-8")
    crosswalk_text = CROSSWALK.read_text(encoding="utf-8")

    source_rows = SOURCE_RE.findall(source_text)
    rows = ROW_RE.findall(crosswalk_text)
    if len(source_rows) != 74:
        fail(f"Expected 74 S103 source rows, found {len(source_rows)}")
    if len(rows) != 74:
        fail(f"Expected 74 crosswalk rows, found {len(rows)}")

    expected_ids = [f"S103-PF-{i:03d}" for i in range(1, 75)]
    source_ids = [row[0] for row in source_rows]
    row_ids = [row[0] for row in rows]
    if source_ids != expected_ids:
        fail("S103 source IDs are missing, duplicated, reordered or renumbered")
    if row_ids != expected_ids:
        fail("Crosswalk IDs are missing, duplicated, reordered or renumbered")

    source_names = {row_id: name for row_id, name in source_rows}
    mapping_types: Counter[str] = Counter()
    s100_linked = 0
    row_lookup: dict[str, tuple[str, str, str, str]] = {}

    for row_id, name, mapping_type, canonical, s100, disposition in rows:
        name = name.strip()
        canonical = canonical.strip()
        s100 = s100.strip()
        disposition = disposition.strip()
        if source_names[row_id] != name:
            fail(f"Source-name drift for {row_id}: {name!r} != {source_names[row_id]!r}")
        if mapping_type not in EXPECTED_TYPES:
            fail(f"Unsupported mapping type {mapping_type!r} on {row_id}")
        mapping_types[mapping_type] += 1
        if "S100-PORT-" in s100:
            s100_linked += 1
        if mapping_type == "unresolved" and canonical != "—":
            fail(f"Unresolved row {row_id} must not silently receive a canonical ID")
        if not disposition:
            fail(f"Missing disposition for {row_id}")
        row_lookup[row_id] = (mapping_type, canonical, s100, disposition)

    actual_types = {key: mapping_types.get(key, 0) for key in EXPECTED_TYPES}
    if actual_types != EXPECTED_TYPES:
        fail(f"Unexpected mapping distribution: {actual_types}")
    if s100_linked != 51:
        fail(f"Expected 51 S103 rows with S100 portfolio relationships, found {s100_linked}")
    if mapping_types.get("unresolved", 0) != 0:
        fail("Founder-adjudicated current owner identity/disposition queue must contain zero unresolved rows")

    for row_id, expected in CRITICAL.items():
        mapping_type, canonical, _, _ = row_lookup[row_id]
        if mapping_type != expected[0]:
            fail(f"Critical mapping type drift for {row_id}: {mapping_type!r}")
        for fragment in expected[1:]:
            if fragment not in canonical:
                fail(f"Critical canonical reference {fragment!r} missing from {row_id}")

    mvp_type, mvp_canonical, _, mvp_disposition = row_lookup["S103-PF-028"]
    if mvp_type != "merged_into" or "ct.platform.melanated-tv" not in mvp_canonical:
        fail("MVP (Roku) must resolve as historical Roku/distribution lineage merged into Melanated TV")
    if "historical" not in mvp_disposition.lower() or "roku" not in mvp_disposition.lower():
        fail("MVP (Roku) disposition must preserve explicit historical Roku lineage")

    dba_type, dba_canonical, _, dba_disposition = row_lookup["S103-PF-053"]
    if dba_type != "predecessor_concept" or "ct.platform.crownthrive-u" not in dba_canonical:
        fail("Digital Business Academy must remain a CrownThriveU reserve/predecessor concept")
    if "reserve/predecessor" not in dba_disposition.lower():
        fail("Digital Business Academy disposition must preserve reserve/predecessor treatment")

    neural_type, neural_canonical, _, neural_disposition = row_lookup["S103-PF-056"]
    if neural_type != "current_top_level_identity" or "ct.platform.neuralcraft-ai-studio" not in neural_canonical:
        fail("NeuralCraft AI Studio must remain a separate current top-level identity")
    if "separate current top-level" not in neural_disposition.lower():
        fail("NeuralCraft disposition must preserve its separate top-level role")

    s100_text = S100.read_text(encoding="utf-8")
    for source_row, canonical_id in TRANCHE_S100.items():
        matching = [line for line in s100_text.splitlines() if source_row in line]
        if len(matching) != 1:
            fail(f"Expected exactly one S100 row for {source_row}, found {len(matching)}")
        if canonical_id not in matching[0]:
            fail(f"S100 row {source_row} missing stable ID {canonical_id}")

    # Historical tranche evidence remains immutable even though the current owner queue is closed.
    require(TRANCHE1, "s103_unresolved: 29")
    require(TRANCHE2, "unresolved: 20")
    require(TRANCHE2, "Historical checkpoint with current overlay")

    # Current identity/control projections must agree with the founder adjudication.
    require(THRIVERELAY, "Stable platform ID: `ct.platform.thriverelay`")
    require(THRIVEMAPS, "Stable platform ID: `ct.platform.thrivemaps`")
    require(BACKROAD, "Stable platform ID:** `ct.platform.backroad-fm`")
    require(ADAPTER_MATRIX, "`ct.platform.kjv-sermon-toolkit`")
    require(MEDIA_FEDERATION, "historical Roku/distribution lineage merged into Melanated TV")
    require(D6, "`ct.platform.crownapps-thriveapps`")
    require(PLATFORM_STATE, "Founder adjudication")
    require(CROSSWALK, "rows_with_s100_portfolio_relationship: 51")
    require(CROSSWALK, "founder_terminal_adjudications_applied: 20")
    require(CROSSWALK, "ct_count_002_owner_identity_disposition_unresolved: 0")
    require(CROSSWALK, "phase_3_entry: blocked_pending_phase_2_99_hard_exit_and_full_docs_reconciliation")
    require(FOUNDER_ADJUDICATIONS, "S103 owner identity/disposition closure")
    require(PLAN, "## Twenty-phase roadmap inheritance")
    require(PLAN, "## Founder full-documentation hard gate and exact transition snapshot")
    require(GATE, "current_owner_identity_disposition_unresolved: 0")
    require(TEN_PHASE_CHARTER, "Historical roadmap generation 1")
    require(TWENTY_PHASE_CHARTER, "roadmap_namespace: twenty_phase_v2")
    require(TWENTY_PHASE_CHARTER, "phase_3_entry: blocked_pending_phase_2_99_hard_exit_and_full_docs_reconciliation")

    print(
        "S103 74-row canonical crosswalk validation PASSED: "
        "74 source-aligned rows, current relationship/disposition schema pinned, "
        "51 S100 relationships, 20 founder adjudications applied, 0 current owner-identity unresolved, "
        "historical unresolved tranches preserved, operational/provider/legal/rights/economic proof separate, "
        "Phase 3 remains blocked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
