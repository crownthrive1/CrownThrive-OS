#!/usr/bin/env python3
"""Validate CrownThrive CIE Wave 1 documentation and navigation invariants."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "doctrine/cultural-imprint-engine.mdx",
    "doctrine/cie-operating-model.mdx",
    "doctrine/cie-integration-handoffs.mdx",
    "doctrine/services-stack.mdx",
    "portfolio/kulture-house-kulture-radio-institutional-record.mdx",
    "portfolio/bonged-out-institutional-record.mdx",
    "knowledge/cie-wave1-source-register.mdx",
    "changelog/cie-institutionalization-wave-1-2026-08-23.mdx",
)

REQUIRED_NAV = set(REQUIRED_FILES)
REQUIRED_NAV = {path.rsplit(".", 1)[0] for path in REQUIRED_NAV}

CSS_DOMAINS = (
    "Identity",
    "Authentication",
    "Authorization",
    "Billing",
    "Licensing",
    "Analytics",
    "Notifications",
    "CRM",
    "Ticketing",
    "Search",
    "Commerce",
    "Routing",
    "Rewards",
    "Documentation",
)

SOURCE_IDS = {"S118", "S119", "S120", "S121", "S122", "S123"}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        fail(f"missing required file: {rel}")
    return path.read_text(encoding="utf-8")


def flatten_nav(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str):
        found.add(value)
    elif isinstance(value, list):
        for item in value:
            found.update(flatten_nav(item))
    elif isinstance(value, dict):
        for item in value.values():
            found.update(flatten_nav(item))
    return found


def main() -> int:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).is_file():
            fail(f"missing Wave 1 artifact: {rel}")

    cie = read("doctrine/cultural-imprint-engine.mdx")
    operating = read("doctrine/cie-operating-model.mdx")
    handoffs = read("doctrine/cie-integration-handoffs.mdx")
    css = read("doctrine/services-stack.mdx")
    kulture = read("portfolio/kulture-house-kulture-radio-institutional-record.mdx")
    bonged = read("portfolio/bonged-out-institutional-record.mdx")
    sources = read("knowledge/cie-wave1-source-register.mdx")
    seed = read("portfolio/imprint-brand-universe-seed-register.mdx")
    frameworks = read("doctrine/framework-engine-registry.mdx")

    if "Cultural Imprint Engine (CIE)" not in cie:
        fail("canonical CIE identity missing")
    if "current_public_package_state: CONTROLLED_TEST" not in cie:
        fail("CIE package-state boundary missing")
    if "authority_ceiling: D2" not in cie or "d3_authority: human_reserved" not in cie:
        fail("CIE authority ceiling/human D3 boundary missing")
    if "CIE does not manufacture rights" not in cie:
        fail("CIE/CHLOM separation missing")

    for domain in CSS_DOMAINS:
        if domain not in css:
            fail(f"CSS domain missing: {domain}")
    if "CrownThrive Services Stack (CSS)" not in css:
        fail("canonical CSS identity missing")
    if "execution layer, not an authority factory" not in css:
        fail("CSS authority boundary missing")
    if "CrownThrive Services Stack (CSS)" not in frameworks:
        fail("CSS not registered in framework registry")

    for state in ("PASS", "CONDITIONAL_PASS", "HOLD", "DENY", "CORRECT"):
        if state not in operating:
            fail(f"CIE operating decision state missing: {state}")
    if "CIE may not manufacture rights, execution authority, economic truth or sovereign authority" not in handoffs:
        fail("handoff authority boundary missing")

    if "source-derived relationship terms; not a universal CrownThrive offer" not in kulture:
        fail("Kulture relationship scope boundary missing")
    if "no classification, no split" not in kulture.lower():
        fail("Kulture project classification contract missing")
    if "Kulture House / Kulture Radio" not in seed:
        fail("Kulture seed record not linked")

    if "audience_class: adult_21_plus" not in bonged:
        fail("Bonged Out! adult audience boundary missing")
    if "not plant-touching permission" not in bonged:
        fail("Bonged Out! plant-touching boundary missing")
    for value in ("$50,000", "$40,000", "$150,000", "$120,000"):
        if value not in bonged:
            fail(f"Bonged Out! source commercial term missing: {value}")
    if "not automatically current public pricing" not in bonged:
        fail("Bonged Out! source-price quarantine missing")
    if "live commercial licensing remains separately gated" not in seed:
        fail("Bonged Out! seed commercial boundary missing")

    found_source_ids = set(re.findall(r"`(S1\d{2})`", sources))
    if not SOURCE_IDS.issubset(found_source_ids):
        fail(f"Wave 1 source IDs incomplete: {sorted(found_source_ids)}")
    if "Commercial-source quarantine" not in sources:
        fail("Wave 1 commercial source quarantine missing")

    docs = json.loads(read("docs.json"))
    nav = flatten_nav(docs.get("navigation", {}))
    missing_nav = sorted(REQUIRED_NAV - nav)
    if missing_nav:
        fail(f"Wave 1 Mintlify navigation missing: {missing_nav}")

    joined = "\n".join((cie, operating, handoffs, css, kulture, bonged, sources))
    credential_patterns = (
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"\bsb_secret_[A-Za-z0-9_-]{16,}\b",
        r"\bsk-[A-Za-z0-9]{20,}\b",
        r"\bmint_[A-Za-z0-9_-]{16,}\b",
    )
    for pattern in credential_patterns:
        if re.search(pattern, joined):
            fail("credential-shaped value detected in public CIE Wave 1 documentation")

    print(
        "CIE Wave 1 docs validation PASS: doctrine, CSS, two imprint records, "
        "S118-S123 source continuation, commercial quarantine and Mintlify navigation are wired."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
