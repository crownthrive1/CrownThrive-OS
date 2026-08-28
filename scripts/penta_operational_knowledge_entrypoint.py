#!/usr/bin/env python3
"""Governed entrypoint for the operational Penta knowledge generator.

The machine taxonomy intentionally carries richer audience identities than the
existing PentaDocs presentation schema. This adapter preserves those machine
identities while mapping MDX metadata into the narrower PentaDocs enums.

It also prevents a noncanonical identity from inheriting operational jobs merely
because a provisional/docs-inferred family classifier guessed a family. Such
identities are routed through the canonicalization/governance lane first, with
only explicit keyword overlays used as provisional intended-function metadata.
"""
from __future__ import annotations

import argparse
import json
import re

import penta_operational_knowledge as core

FRONTMATTER_AUDIENCE_MAP = {
    "agent": "developer",
    "developer": "developer",
    "operator": "operator",
    "owner-admin": "operator",
    "auditor": "operator",
    "partner-integrator": "developer",
}
ALLOWED_PENTADOCS_AUDIENCES = {
    "executive",
    "public",
    "operator",
    "developer",
    "rights_support",
    "historical",
}
ALLOWED_PENTADOCS_PAGE_TYPES = {
    "orientation",
    "doctrine",
    "registry",
    "reference",
    "status",
    "workflow",
    "runbook",
    "standard",
    "support",
    "how_to",
    "policy",
    "legal",
    "developer",
    "changelog",
    "historical_record",
    "redirect",
}

_original_fm = core.fm
_original_classification = core.classification


def presentation_page_type(title: str, page_type: str) -> str:
    if page_type != "guide":
        return page_type
    value = title.casefold()
    if "runbook" in value or "incident" in value:
        return "runbook"
    if "development" in value or "integration" in value:
        return "developer"
    if "quickstart" in value:
        return "how_to"
    if any(token in value for token in ("layer", "job", "lifecycle", "audience")):
        return "registry"
    return "reference"


def governed_fm(title: str, description: str, *, page_type: str = "guide", audience: str = "operator") -> str:
    rendered_audience = FRONTMATTER_AUDIENCE_MAP.get(audience, audience)
    rendered_page_type = presentation_page_type(title, page_type)
    if rendered_audience not in ALLOWED_PENTADOCS_AUDIENCES:
        raise ValueError(
            f"unsupported PentaDocs presentation audience: machine={audience!r} rendered={rendered_audience!r}"
        )
    if rendered_page_type not in ALLOWED_PENTADOCS_PAGE_TYPES:
        raise ValueError(
            f"unsupported PentaDocs page type: source={page_type!r} rendered={rendered_page_type!r} title={title!r}"
        )
    return _original_fm(
        title,
        description,
        page_type=rendered_page_type,
        audience=rendered_audience,
    )


def _normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def governed_classification(record: dict, taxonomy: dict) -> dict:
    base = _original_classification(record, taxonomy)
    if record.get("namespace_state") == "canonical":
        return base

    assignment_state = str(record.get("assignment_state") or "pending_canonicalization")
    # A registry-backed noncanonical extension may use its governed family as a
    # classification input. Provisional/docs-inferred family guesses may not.
    if assignment_state == "registry_backed":
        return base

    layers = ["control-governance", "data-knowledge"]
    jobs = ["govern", "document"]
    overlays: list[dict] = []
    haystack = _normalize(" ".join([
        str(record.get("name") or ""),
        str(record.get("canonical_machine_key") or ""),
        str(record.get("role") or ""),
        str(record.get("kind") or ""),
    ]))
    for overlay in taxonomy.get("keyword_overlays", []):
        if not isinstance(overlay, dict):
            continue
        matched = [
            str(word)
            for word in overlay.get("match", [])
            if _normalize(word) and _normalize(word) in haystack
        ]
        if not matched:
            continue
        layers.extend(str(value) for value in overlay.get("layers", []))
        jobs.extend(str(value) for value in overlay.get("jobs", []))
        overlays.append({
            "matched": matched,
            "layers": list(overlay.get("layers", [])),
            "jobs": list(overlay.get("jobs", [])),
        })

    layers = _dedupe(layers)[:5]
    jobs = _dedupe(jobs)[:6]
    return {
        "layers": layers,
        "jobs": jobs,
        "lifecycle_stages": ["discover", "design", "govern", "evolve"],
        "audiences": ["agent", "developer", "owner-admin", "auditor"],
        "provenance": {
            "family": assignment_state,
            "layers": "candidate_canonicalization_plus_keyword" if overlays else "candidate_canonicalization_default",
            "jobs": "candidate_canonicalization_plus_keyword" if overlays else "candidate_canonicalization_default",
            "overlays": overlays,
        },
    }


core.fm = governed_fm
core.classification = governed_classification


def validate_taxonomy_contract() -> None:
    taxonomy = core.load_json(core.TAXONOMY)
    machine_ids = {str(item["id"]) for item in taxonomy.get("audiences", []) if isinstance(item, dict)}
    missing = machine_ids - set(FRONTMATTER_AUDIENCE_MAP)
    if missing:
        raise ValueError(f"machine audiences missing PentaDocs presentation mapping: {sorted(missing)}")
    invalid = set(FRONTMATTER_AUDIENCE_MAP.values()) - ALLOWED_PENTADOCS_AUDIENCES
    if invalid:
        raise ValueError(f"invalid mapped PentaDocs audiences: {sorted(invalid)}")
    for required in ("control-governance", "data-knowledge"):
        if required not in {str(x["id"]) for x in taxonomy.get("layers", []) if isinstance(x, dict)}:
            raise ValueError(f"candidate canonicalization layer missing from taxonomy: {required}")
    for required in ("govern", "document"):
        if required not in {str(x["id"]) for x in taxonomy.get("jobs", []) if isinstance(x, dict)}:
            raise ValueError(f"candidate canonicalization job missing from taxonomy: {required}")
    for sample in (
        "Penta Operational Knowledge",
        "Penta Architectural Layers",
        "Penta Jobs & Functions",
        "Penta Lifecycle",
        "Penta Audience Guides",
        "Penta Development Guide",
        "Penta Quickstarts",
        "Penta Agent Ingestion",
        "Penta Integration Guide",
        "Penta Runbooks & Incidents",
    ):
        resolved = presentation_page_type(sample, "guide")
        if resolved not in ALLOWED_PENTADOCS_PAGE_TYPES:
            raise ValueError(f"invalid page-type mapping for {sample!r}: {resolved!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    validate_taxonomy_contract()
    result = core.apply() if args.apply else core.check()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
