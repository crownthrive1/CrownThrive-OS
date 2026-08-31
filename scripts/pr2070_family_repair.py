#!/usr/bin/env python3
"""Apply the bounded family-of-families admission required by PR #2070.

This helper is temporary. It runs only on the isolated repair branch and is
removed before the generated repair commit is published. The durable mutation
is the explicit primary/secondary family assignment in the canonical registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REGISTRY = Path("penta/registry/penta-families.v1.json")

PRIMARY_ASSIGNMENTS = {
    "communications-service": [
        "PentaMailer",
        "PentaAds",
    ],
    "workforce-people": [
        "PentaPersonas",
    ],
    "automation-agentic": [
        "PentaPersonaExecution",
    ],
    "build-release": [
        "PentaPersonaFactory",
        "PentaCommunicationsFactory",
        "PentaAdsFactory",
    ],
    "routing-interoperability": [
        "PentaAds Placement OS",
    ],
}

SECONDARY_ASSIGNMENTS = {
    "PentaMailer": [
        "routing-interoperability",
        "resilience-continuity",
        "security-trust",
    ],
    "PentaPersonas": [
        "automation-agentic",
        "communications-service",
        "security-trust",
        "workforce-people",
    ],
    "PentaPersonaExecution": [
        "communications-service",
        "security-trust",
        "workforce-people",
    ],
    "PentaPersonaFactory": [
        "automation-agentic",
        "security-trust",
        "workforce-people",
    ],
    "PentaCommunicationsFactory": [
        "automation-agentic",
        "communications-service",
        "security-trust",
    ],
    "PentaAds": [
        "commerce-economy",
        "media-creative",
        "routing-interoperability",
        "security-trust",
    ],
    "PentaAdsFactory": [
        "commerce-economy",
        "communications-service",
        "security-trust",
    ],
    "PentaAds Placement OS": [
        "commerce-economy",
        "communications-service",
        "media-creative",
        "security-trust",
    ],
}


def family_map(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    families = document.get("families")
    if not isinstance(families, list):
        raise SystemExit("family registry does not expose a families array")
    output: dict[str, dict[str, Any]] = {}
    for family in families:
        if not isinstance(family, dict) or not isinstance(family.get("family_id"), str):
            raise SystemExit("invalid family entry")
        output[family["family_id"]] = family
    return output


def main() -> None:
    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    families = family_map(document)
    family_ids = set(families)

    unknown_primary = sorted(set(PRIMARY_ASSIGNMENTS) - family_ids)
    if unknown_primary:
        raise SystemExit(f"unknown primary families: {unknown_primary}")

    intended_primary = {
        name: family_id
        for family_id, names in PRIMARY_ASSIGNMENTS.items()
        for name in names
    }

    # Do not silently move an existing explicit identity between primary
    # families. A contradictory predecessor must be reconciled deliberately.
    for family_id, family in families.items():
        members = family.get("explicit_members", [])
        if not isinstance(members, list):
            raise SystemExit(f"explicit_members is not a list for {family_id}")
        for name in members:
            target = intended_primary.get(str(name))
            if target is not None and target != family_id:
                raise SystemExit(
                    f"explicit primary-family conflict for {name}: existing={family_id}, intended={target}"
                )

    for family_id, names in PRIMARY_ASSIGNMENTS.items():
        members = families[family_id].setdefault("explicit_members", [])
        for name in names:
            if name not in members:
                members.append(name)

    cross = document.setdefault("cross_family_assignments", {})
    if not isinstance(cross, dict):
        raise SystemExit("cross_family_assignments is not an object")
    for name, roles in SECONDARY_ASSIGNMENTS.items():
        unknown = sorted(set(roles) - family_ids)
        if unknown:
            raise SystemExit(f"unknown secondary families for {name}: {unknown}")
        existing = cross.get(name, [])
        if not isinstance(existing, list):
            raise SystemExit(f"cross-family assignment is not a list for {name}")
        primary = intended_primary[name]
        cross[name] = sorted((set(str(value) for value in existing) | set(roles)) - {primary})

    REGISTRY.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "PASS",
                "primary_assignments": intended_primary,
                "secondary_assignments": SECONDARY_ASSIGNMENTS,
                "authority_manufactured": False,
                "maturity_promoted": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
