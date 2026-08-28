#!/usr/bin/env python3
"""Governed entrypoint for the operational Penta knowledge generator.

The machine taxonomy intentionally carries richer audience identities than the
existing PentaDocs presentation schema. This adapter preserves those machine
identities while mapping MDX `primary_audience` metadata into the narrower,
repository-governed PentaDocs enum.
"""
from __future__ import annotations

import argparse
import json

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

_original_fm = core.fm


def governed_fm(title: str, description: str, *, page_type: str = "guide", audience: str = "operator") -> str:
    rendered_audience = FRONTMATTER_AUDIENCE_MAP.get(audience, audience)
    if rendered_audience not in ALLOWED_PENTADOCS_AUDIENCES:
        raise ValueError(
            f"unsupported PentaDocs presentation audience: machine={audience!r} rendered={rendered_audience!r}"
        )
    return _original_fm(title, description, page_type=page_type, audience=rendered_audience)


core.fm = governed_fm


def validate_taxonomy_contract() -> None:
    taxonomy = core.load_json(core.TAXONOMY)
    machine_ids = {str(item["id"]) for item in taxonomy.get("audiences", []) if isinstance(item, dict)}
    missing = machine_ids - set(FRONTMATTER_AUDIENCE_MAP)
    if missing:
        raise ValueError(f"machine audiences missing PentaDocs presentation mapping: {sorted(missing)}")
    invalid = set(FRONTMATTER_AUDIENCE_MAP.values()) - ALLOWED_PENTADOCS_AUDIENCES
    if invalid:
        raise ValueError(f"invalid mapped PentaDocs audiences: {sorted(invalid)}")


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
