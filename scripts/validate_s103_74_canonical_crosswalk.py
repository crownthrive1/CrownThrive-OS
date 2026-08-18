#!/usr/bin/env python3
"""Validate the S103 74-row canonical identity crosswalk.

This validator protects source-row completeness, mapping-type distribution,
S100 cross-source relationship count, critical alias/predecessor/split mappings,
and the fail-closed Phase 3 gate. It does not treat an unresolved mapping as a
failure: unresolved is an intentional machine state until stronger evidence or
adjudication exists.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "knowledge/phase-2-99-workstream-3a-phase-2-7-74-platform-framework-source-seed.mdx"
CROSSWALK = ROOT / "knowledge/phase-2-99-workstream-3a-s103-74-canonical-identity-crosswalk.mdx"
PLAN = ROOT / "changelog/phase-2-99-plan.mdx"
GATE = ROOT / "technology/phase-3-readiness-gate.mdx"

SOURCE_RE = re.compile(
    r'^- id: (S103-PF-\d{3}); source_index: \d+; source_name: "([^"]+)"$',
    re.MULTILINE,
)
ROW_RE = re.compile(
    r'^\| `(S103-PF-\d{3})` \| ([^|]+?) \| `([^`]+)` \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \|$',
    re.MULTILINE,
)

EXPECTED_TYPES = {
    "exact": 29,
    "alias": 2,
    "predecessor": 3,
    "framework_platform_split": 3,
    "composite_split": 2,
    "unresolved": 35,
}

CRITICAL = {
    "S103-PF-001": ("composite_split", "ct.org.crownthrive-llc", "ct.platform.crownthrive"),
    "S103-PF-002": ("framework_platform_split", "ct.framework.chlom", "ct.platform.chlom"),
    "S103-PF-005": ("framework_platform_split", "ct.framework.mm-suites", "ct.platform.mm-suites"),
    "S103-PF-019": ("framework_platform_split", "ct.framework.mm-suites", "ct.platform.mm-suites"),
    "S103-PF-021": ("alias", "ct.platform.thriveseat"),
    "S103-PF-057": ("predecessor", "ct.platform.ops-oasis"),
    "S103-PF-065": ("composite_split", "ct.platform.thrivesupport", "ct.platform.crownthrive-support"),
    "S103-PF-066": ("predecessor", "ct.platform.virality-music"),
    "S103-PF-067": ("predecessor", "ct.platform.crownthrive-studios"),
    "S103-PF-068": ("alias", "ct.platform.ops-oasis"),
}


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


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

    required_fragments = [
        (CROSSWALK, "ct_count_002_row_classification: pass"),
        (CROSSWALK, "ct_count_002_all_canonical_ids_resolved: false"),
        (CROSSWALK, "phase_3_entry: blocked_pending_phase_2_99_hard_exit"),
        (PLAN, "S103 74-Row Canonical Identity Crosswalk"),
        (GATE, "S103 74-Row Canonical Identity Crosswalk"),
    ]
    for path, fragment in required_fragments:
        text = path.read_text(encoding="utf-8")
        if fragment not in text:
            fail(f"Required crosswalk-governance fragment {fragment!r} missing from {path.relative_to(ROOT)}")

    print(
        "S103 74-row canonical crosswalk validation PASSED: "
        "74 source-aligned mapping rows, 29 exact, 2 aliases, 3 predecessors, "
        "3 framework/platform splits, 2 composite splits, 35 unresolved, "
        "49 S100 relationships, Phase 3 remains fail-closed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
