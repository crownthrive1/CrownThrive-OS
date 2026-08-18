#!/usr/bin/env python3
"""Validate the public-safe S100 82-domain source-row seed.

This validator checks the recovered Appendix C source universe without making
network calls. It intentionally validates source-row integrity separately from
current registrar, DNS, TLS, routing or deployment state.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "knowledge/phase-2-99-workstream-3a-holdings-82-domain-source-seed.mdx"
CONTRADICTIONS = ROOT / "knowledge/contradiction-ledger.mdx"
PLAN = ROOT / "changelog/phase-2-99-plan.mdx"
GATE = ROOT / "technology/phase-3-readiness-gate.mdx"

EXPECTED_DOMAINS = [
    "crownthrive.com", "crownthrive.io", "thriverelay.com", "adluxeplaces.com",
    "adluxestudio.com", "rootednoir.com", "opsoasis.com", "thrivekiln.com",
    "thrivemaps.com", "thrivewick.com", "crownthrivesupport.com", "tapstations.com",
    "crownthrive.dev", "crownthrive.net", "crownthrive.org", "thrivekiosks.com",
    "brandcards.co", "crownthrivestudios.com", "chlomlex.io", "chlomlex.com",
    "melanatedvault.com", "melanatedstock.com", "quiznuggets.com",
    "melanatedvoicesplatform.com", "melanatedtv.com", "melanatedvoicestv.com",
    "lyftedsociety.com", "thezazaroom.com", "thriveseat.com", "thrivealumni.com",
    "chlom.io", "thelmarket.com", "bongedout.com", "goodshitonly.com",
    "socialaily.com", "tearsofdefeat.com", "chaincliques.com", "nftcliques.com",
    "findcliques.com", "crownaffiliates.com", "goflipbooks.com", "thetamegallery.com",
    "tamegallery.com", "kamoracrm.com", "kamora360.com", "mycrownoasis.com",
    "crownfluence.com", "thrivepeers.com", "thrivepeer.com", "luxperiences.com",
    "thrivetravels.com", "thrivebookings.com", "melaninmagicsuites.com",
    "themaneexperience.com", "crownthriveu.com", "thrivepush.io", "thrivetools.io",
    "crownlytics.com", "thrivetickets.com", "crownpulse.com", "mycrownrewards.com",
    "melanatedvoices.com", "locticians.org", "locticians.club", "crownthrive.cafe",
    "mywellnesspath.me", "crownlinks.xyz", "crownlinks.io", "gentsgrowth.com",
    "beautybrdg.com", "thrivelnk.io", "shopmelaninmagic.com", "locticians.com",
    "musiqhead.com", "naturalhair.me", "art.crownthrive.com", "status.crownthrive.com",
    "portal.crownthrive.com", "insights.crownthrive.com", "forms.crownthrive.com",
    "commons.crownthrive.com", "crownthriveholdings.com",
]

EXPECTED_STATUS_COUNTS = {
    "Active": 70,
    "User-confirmed active": 3,
    "User-confirmed / future": 1,
    "User-confirmed in use": 1,
    "Subdomain": 3,
    "Planned subdomain": 3,
    "Verify/register": 1,
}

EXPECTED_NEAR_TERM = {
    "crownlytics.com", "thrivetools.io", "lyftedsociety.com", "thezazaroom.com",
    "thrivepush.io", "crownthriveu.com", "melaninmagicsuites.com",
    "themaneexperience.com", "thrivebookings.com", "thrivetravels.com",
    "luxperiences.com", "melanatedvoicesplatform.com", "melanatedtv.com",
    "melanatedvoicestv.com", "thrivepeer.com", "thrivepeers.com",
}

ROW_RE = re.compile(
    r"^- id: (S100-DOM-\d{3}); domain: ([^;]+); mapped_property: \".*?\"; "
    r"source_status: \"(.*?)\"; next_due: ([^;]+); notes: \".*\"$",
    re.MULTILINE,
)


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def main() -> int:
    if not SEED.is_file():
        fail(f"Missing seed page: {SEED.relative_to(ROOT)}")

    text = SEED.read_text(encoding="utf-8")
    rows = ROW_RE.findall(text)
    if len(rows) != 82:
        fail(f"Expected 82 S100 domain rows, found {len(rows)}")

    ids = [row[0] for row in rows]
    expected_ids = [f"S100-DOM-{i:03d}" for i in range(1, 83)]
    if ids != expected_ids:
        fail("S100 domain IDs are missing, duplicated, reordered or renumbered")

    domains = [row[1] for row in rows]
    if domains != EXPECTED_DOMAINS:
        fail("Recovered S100 domain names/order drifted from the pinned 82-row source projection")
    if len(set(domains)) != 82:
        fail("Duplicate domain value detected in S100 domain seed")

    statuses = Counter(row[2] for row in rows)
    if dict(statuses) != EXPECTED_STATUS_COUNTS:
        fail(f"Unexpected source-status distribution: {dict(statuses)}")

    due = {row[1]: row[3] for row in rows if row[3] != "null"}
    if len(due) != 70:
        fail(f"Expected 70 source due dates, found {len(due)}")

    near_term = {
        domain
        for domain, due_date in due.items()
        if "2026-08-18" < due_date <= "2026-10-02"
    }
    if near_term != EXPECTED_NEAR_TERM:
        fail(
            "Near-term source-due cohort mismatch: "
            f"missing={sorted(EXPECTED_NEAR_TERM - near_term)}, "
            f"unexpected={sorted(near_term - EXPECTED_NEAR_TERM)}"
        )

    required_fragments = [
        (CONTRADICTIONS, "CT-CON-039"),
        (PLAN, "Holdings 82-Row Domain Seed"),
        (GATE, "Holdings 82-Row Domain Seed"),
        (SEED, "management status and due dates"),
        (SEED, "phase_3_entry: blocked_pending_phase_2_99_hard_exit"),
    ]
    for path, fragment in required_fragments:
        if fragment not in path.read_text(encoding="utf-8"):
            fail(f"Required domain-governance fragment {fragment!r} missing from {path.relative_to(ROOT)}")

    print(
        "Holdings 82-domain seed validation PASSED: "
        "82 ordered source rows, 70 source due dates, 16 near-term verification records, "
        "CT-CON-039 present, current certification remains independently gated."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
