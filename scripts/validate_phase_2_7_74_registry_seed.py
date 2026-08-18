#!/usr/bin/env python3
"""Validate the S103 Phase 2.7 74-row platform/framework source census.

This validator checks historical source-row identity and version/count lineage only.
It must not infer current production, canonical naming, legal status, or commercial state.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "knowledge/phase-2-99-workstream-3a-phase-2-7-74-platform-framework-source-seed.mdx"
SOURCE_REGISTER = ROOT / "knowledge/source-register.mdx"
CONTRADICTIONS = ROOT / "knowledge/contradiction-ledger.mdx"
CROSSWALK = ROOT / "knowledge/phase-2-99-workstream-3a-relationship-portfolio-crosswalk.mdx"
PLAN = ROOT / "changelog/phase-2-99-plan.mdx"
GATE = ROOT / "technology/phase-3-readiness-gate.mdx"
CHARTER = ROOT / "standards/ten-phase-institutional-program-charter.mdx"

EXPECTED_NAMES = [
    "CrownThrive",
    "CHLOM",
    "Cultural Imprint Engine",
    "Thrive Flywheel",
    "MM Suites",
    "CrownThrive IO",
    "Collab Portal",
    "BrandCards",
    "ThriveTools",
    "ThriveRelay",
    "Locticians",
    "FindCliques",
    "ChainCliques",
    "NFTCliques",
    "ThrivePeer",
    "ThriveAlumni",
    "Tribes",
    "Melanin Magic",
    "MM Suites / Melanin Magic Suites",
    "SuitePros",
    "ThriveSeats",
    "The Mane Experience",
    "Virality Music",
    "Backroad FM",
    "Melanated Voices Platform",
    "Melanated Voices TV",
    "Melanated TV",
    "MVP (Roku)",
    "Locticians TV",
    "CrownThrive Studios",
    "Go-Flipbooks",
    "Melanated Vault",
    "Melanated Stock",
    "The Tame Gallery",
    "The Artful Mane Gallery",
    "Wearable Art / Legaleriste",
    "Melanated Culture & Heritage Museum",
    "AdLuxe Studio",
    "AdLuxe Network",
    "AdLuxe Places",
    "ThriveKiosks",
    "CrownLytics",
    "CrownPulse",
    "ThrivePush",
    "CrownRewards",
    "CrownFluence",
    "Crown Ambassadors",
    "Crown Affiliates",
    "ThriveGather",
    "ThriveTickets",
    "CrownThriveU",
    "CrownThrive Impact Institute",
    "Digital Business Academy",
    "The Sermon Toolkit",
    "Thrive AI Studio",
    "NeuralCraft AI Studio",
    "Kamora360",
    "Ilyass.AI & CrownThrive Quantum Initiative",
    "CrownJewel",
    "Storytime",
    "My CrownOasis",
    "Rooted Noir",
    "ThriveCafe",
    "Network Status",
    "CrownThrive Support",
    "CrownThrive Music",
    "ThriveStudio",
    "Ops Oasis",
    "ThriveMaps",
    "SocialAIly",
    "CrownApps",
    "CrownInsights",
    "ThriveFoundry",
    "MV VoiceForge",
]

ROW_RE = re.compile(
    r'^- id: (S103-PF-\d{3}); source_index: (\d+); source_name: "([^"]+)"$',
    re.MULTILINE,
)

REQUIRED_SEED_FRAGMENTS = [
    "source_snapshot_created_at: 2026-07-29T17:29:32Z",
    "source_rows: 74",
    "source_index_range: 0..73",
    "P0: 4",
    "P1: 20",
    "P2: 31",
    "P3: 14",
    "P4: 4",
    "P5: 1",
    "items_requiring_validation: 60",
    "source_backed_pallets: 12",
    "off_chain_service_modules: 15",
    "phase_3_entry: blocked_pending_phase_2_99_hard_exit",
    "ct_count_002_exact_source_row_recovery: pass",
    "ct_count_002_canonical_mapping: incomplete",
]

REQUIRED_DOC_FRAGMENTS = [
    (SOURCE_REGISTER, "| `S103` | CrownThrive / CHLOM Platform and Pallet Registry v1.0"),
    (SOURCE_REGISTER, "| `S104` | CrownThrive / CHLOM Platform and Pallet Registry v1.1"),
    (CONTRADICTIONS, "| CT-CON-040 |"),
    (CROSSWALK, "`S103-PF-001`–`S103-PF-074`"),
    (PLAN, "Phase 2.7 74-Row Platform/Framework Seed"),
    (GATE, "Phase 2.7 74-Row Platform/Framework Seed"),
    (CHARTER, "Downstream update — S103/S104 Phase 2.7 registry lineage recovery"),
]

FORBIDDEN_PROMOTIONS = [
    "74 current platforms",
    "74 active platforms",
    "all 74 are active",
    "all 74 are production",
    "CT-COUNT-002 = current platform count",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def main() -> int:
    if not SEED.is_file():
        fail(f"Missing seed page: {SEED.relative_to(ROOT)}")

    text = SEED.read_text(encoding="utf-8")
    rows = ROW_RE.findall(text)
    if len(rows) != 74:
        fail(f"Expected 74 S103 source rows, found {len(rows)}")

    expected_ids = [f"S103-PF-{i:03d}" for i in range(1, 75)]
    actual_ids = [row[0] for row in rows]
    if actual_ids != expected_ids:
        fail("S103 row IDs are missing, duplicated, reordered or renumbered")

    expected_indexes = [str(i) for i in range(74)]
    actual_indexes = [row[1] for row in rows]
    if actual_indexes != expected_indexes:
        fail("S103 source indexes must remain exact 0..73 in source order")

    actual_names = [row[2] for row in rows]
    if actual_names != EXPECTED_NAMES:
        for i, (expected, actual) in enumerate(zip(EXPECTED_NAMES, actual_names)):
            if expected != actual:
                fail(f"S103 source-name drift at index {i}: expected={expected!r}, actual={actual!r}")
        fail("S103 source-name list drifted")

    if len(set(actual_ids)) != 74:
        fail("Duplicate S103 source-row ID detected")

    for fragment in REQUIRED_SEED_FRAGMENTS:
        if fragment not in text:
            fail(f"Required S103 seed fragment missing: {fragment!r}")

    for path, fragment in REQUIRED_DOC_FRAGMENTS:
        if not path.is_file():
            fail(f"Required documentation file missing: {path.relative_to(ROOT)}")
        if fragment not in path.read_text(encoding="utf-8"):
            fail(f"Required 74-registry fragment {fragment!r} missing from {path.relative_to(ROOT)}")

    lowered = text.lower()
    for phrase in FORBIDDEN_PROMOTIONS:
        if phrase.lower() in lowered:
            fail(f"Forbidden source-to-current promotion detected in seed: {phrase!r}")

    print(
        "Phase 2.7 74-registry seed validation PASSED: "
        "74 ordered S103 rows, exact indexes 0..73, source names pinned, "
        "S103/S104/CT-CON-040 lineage present, Phase 3 remains blocked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
