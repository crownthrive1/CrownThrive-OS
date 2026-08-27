#!/usr/bin/env python3
"""Validate the S103 74-row canonical identity crosswalk.

This validator protects source-row completeness, mapping-type distribution,
S100 cross-source relationship count, critical alias/predecessor/split mappings,
two evidence-backed stable-ID completion tranches, and the fail-closed Phase 3
gate. It does not treat an unresolved mapping as a failure: unresolved is an
intentional machine state until stronger evidence or adjudication exists.
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
CHARTER = ROOT / "standards/ten-phase-institutional-program-charter.mdx"

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
    "composite_split": 2,
    "unresolved": 20,
}

CRITICAL = {
    "S103-PF-001": ("composite_split", "ct.org.crownthrive-llc", "ct.platform.crownthrive"),
    "S103-PF-002": ("framework_platform_split", "ct.framework.chlom", "ct.platform.chlom"),
    "S103-PF-005": ("framework_platform_split", "ct.framework.mm-suites", "ct.platform.mm-suites"),
    "S103-PF-009": ("exact", "ct.platform.thrivetools"),
    "S103-PF-010": ("exact", "ct.platform.thriverelay"),
    "S103-PF-019": ("framework_platform_split", "ct.framework.mm-suites", "ct.platform.mm-suites"),
    "S103-PF-021": ("alias", "ct.platform.thriveseat"),
    "S103-PF-022": ("exact", "ct.platform.the-mane-experience"),
    "S103-PF-024": ("exact", "ct.platform.backroad-fm"),
    "S103-PF-025": ("exact", "ct.platform.melanated-voices-platform"),
    "S103-PF-026": ("exact", "ct.platform.melanated-voices-tv"),
    "S103-PF-027": ("exact", "ct.platform.melanated-tv"),
    "S103-PF-029": ("exact", "ct.platform.locticians-tv"),
    "S103-PF-032": ("exact", "ct.platform.melanated-vault"),
    "S103-PF-033": ("exact", "ct.platform.melanated-stock"),
    "S103-PF-034": ("exact", "ct.platform.tame-gallery"),
    "S103-PF-035": ("exact", "ct.asset.artful-mane-gallery"),
    "S103-PF-054": ("exact", "ct.platform.kjv-sermon-toolkit"),
    "S103-PF-057": ("predecessor", "ct.platform.ops-oasis"),
    "S103-PF-065": ("composite_split", "ct.platform.thrivesupport", "ct.platform.CrownThrive-OS"),
    "S103-PF-066": ("predecessor", "ct.platform.virality-music"),
    "S103-PF-067": ("predecessor", "ct.platform.crownthrive-studios"),
    "S103-PF-068": ("alias", "ct.platform.ops-oasis"),
    "S103-PF-069": ("exact", "ct.platform.thrivemaps"),
    "S103-PF-071": ("alias", "ct.platform.crownapps-thriveapps"),
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
    mapping_types = Counter()
    s100_linked = 0
    row_lookup = {}

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

    if dict(mapping_types) != EXPECTED_TYPES:
        fail(f"Unexpected mapping distribution: {dict(mapping_types)}")
    if s100_linked != 49:
        fail(f"Expected 49 S103 rows with S100 portfolio relationships, found {s100_linked}")

    for row_id, expected in CRITICAL.items():
        mapping_type, canonical, _, _ = row_lookup[row_id]
        if mapping_type != expected[0]:
            fail(f"Critical mapping type drift for {row_id}: {mapping_type!r}")
        for fragment in expected[1:]:
            if fragment not in canonical:
                fail(f"Critical canonical reference {fragment!r} missing from {row_id}")

    mvp_roku_type, mvp_roku_canonical, _, mvp_roku_disposition = row_lookup["S103-PF-028"]
    if mvp_roku_type != "unresolved" or mvp_roku_canonical != "—":
        fail("MVP (Roku) must remain unresolved until its orchestration/channel lineage is independently reconciled")
    if "lineage" not in mvp_roku_disposition.lower():
        fail("MVP (Roku) must preserve explicit lineage-reconciliation state")

    s100_text = S100.read_text(encoding="utf-8")
    for source_row, canonical_id in TRANCHE_S100.items():
        matching = [line for line in s100_text.splitlines() if source_row in line]
        if len(matching) != 1:
            fail(f"Expected exactly one S100 row for {source_row}, found {len(matching)}")
        if canonical_id not in matching[0]:
            fail(f"S100 row {source_row} missing stable ID {canonical_id}")

    require(THRIVERELAY, "Stable platform ID: `ct.platform.thriverelay`")
    require(THRIVEMAPS, "Stable platform ID: `ct.platform.thrivemaps`")
    require(BACKROAD, "Stable platform ID:** `ct.platform.backroad-fm`")
    require(ADAPTER_MATRIX, "`ct.platform.kjv-sermon-toolkit`")
    require(TRANCHE1, "s103_unresolved: 29")
    require(TRANCHE1, "phase_3_entry: blocked_pending_phase_2_99_hard_exit")
    require(TRANCHE2, "unresolved: 20")
    require(TRANCHE2, "phase_3_entry: blocked_pending_phase_2_99_hard_exit")
    require(MEDIA_FEDERATION, "`ct.platform.melanated-voices-platform`")
    require(MEDIA_FEDERATION, "`MVP (Roku)` remains a separate unresolved lineage record")
    require(D6, "`ct.platform.crownapps-thriveapps`")
    require(PLATFORM_STATE, "53 source rows map one-to-one")
    require(PLATFORM_STATE, "six remain canonical/child identity resolution items")
    require(CROSSWALK, "ct_count_002_row_classification: pass")
    require(CROSSWALK, "ct_count_002_all_canonical_ids_resolved: false")
    require(CROSSWALK, "phase_3_entry: blocked_pending_phase_2_99_hard_exit")
    require(PLAN, "two evidence-backed stable-ID tranches")
    require(GATE, "20 unresolved")
    require(CHARTER, "20 `unresolved`")

    print(
        "S103 74-row canonical crosswalk validation PASSED: "
        "74 source-aligned mapping rows, 43 exact, 3 aliases, 3 predecessors, "
        "3 framework/platform splits, 2 composite splits, 20 unresolved, "
        "49 S100 relationships, tranche-2 alias/media IDs pinned, MVP Roku remains fail-closed, "
        "Phase 3 remains blocked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
