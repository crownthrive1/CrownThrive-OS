#!/usr/bin/env python3
"""Validate and optionally materialize the compact 795-record Help Center article seed bundle.

This validator proves that the recovered title/hierarchy machine manifest is complete
and byte-stable. It deliberately does NOT claim that article bodies were recovered,
terminal dispositions are complete, or Phase 2.99 has passed.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR_PATH = ROOT / "data/help_center_article_manifest.v1.bundle.json"

EXPECTED_SCHEMA_VERSION = "1.3.0-compact"
EXPECTED_RECORD_FIELDS = [
    "inventory_id",
    "recovered_order",
    "recovered_section",
    "recovered_subcategory",
    "recovered_title",
]
EXPECTED_SECTION_CENSUS = {
    "CHLOM": 297,
    "Convergent Ecosystem": 206,
    "CrownThrive Legal Depot": 198,
    "CrownThrive HQ": 46,
    "Thrive Flywheel": 14,
    "MM Suites": 13,
    "Cultural Imprint Engine (CIE)": 11,
    "Hybrid Incubator": 5,
    "Investor Relations": 5,
}
EXPECTED_DEFAULTS: dict[str, Any] = {
    "recovery_status": "title_and_hierarchy_recovered",
    "body_status": "reconstruction_required",
    "confidence": "high",
    "source_refs": ["S11"],
    "disposition": "source_recovery_pending",
    "content_state": "reconstruction_required",
    "canonical_route": None,
    "current_page_path": None,
    "platform_ids": [],
    "category_ids": [],
    "audiences": [],
    "exposure": "unclassified",
    "risk_class": "unclassified",
    "owner_role_id": None,
    "related_article_ids": [],
    "redirects_from": [],
    "effective_at": None,
    "last_verified_at": "2026-08-18",
    "correction_events": [],
}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_bundle() -> tuple[dict[str, Any], bytes, bytes, dict[str, Any]]:
    descriptor = load_json(DESCRIPTOR_PATH)
    parts = descriptor.get("parts", [])
    if len(parts) != descriptor.get("part_count") or len(parts) != 3:
        fail("bundle must declare exactly three ordered base64 parts")

    chunks: list[str] = []
    for rel in parts:
        path = ROOT / str(rel)
        if not path.is_file():
            fail(f"bundle part missing: {rel}")
        chunks.append("".join(path.read_text(encoding="ascii").split()))

    encoded = "".join(chunks)
    if len(encoded) != descriptor.get("concatenated_base64_length"):
        fail(
            "base64 length drifted: "
            f"{len(encoded)} != {descriptor.get('concatenated_base64_length')}"
        )

    try:
        compressed = base64.b64decode(encoded, validate=True)
    except Exception as exc:  # pragma: no cover - fail-closed parser path
        fail(f"bundle base64 is invalid: {exc}")

    if len(compressed) != descriptor.get("gzip_bytes"):
        fail(f"gzip byte length drifted: {len(compressed)} != {descriptor.get('gzip_bytes')}")
    if sha256_bytes(compressed) != descriptor.get("gzip_sha256"):
        fail("gzip SHA-256 drifted")

    try:
        raw = gzip.decompress(compressed)
    except Exception as exc:  # pragma: no cover
        fail(f"bundle gzip is invalid: {exc}")

    if len(raw) != descriptor.get("json_bytes"):
        fail(f"JSON byte length drifted: {len(raw)} != {descriptor.get('json_bytes')}")
    if sha256_bytes(raw) != descriptor.get("json_sha256"):
        fail("uncompressed JSON SHA-256 drifted")

    try:
        manifest = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # pragma: no cover
        fail(f"manifest JSON is invalid: {exc}")
    if not isinstance(manifest, dict):
        fail("manifest root must be an object")

    return descriptor, compressed, raw, manifest


def validate_manifest(descriptor: dict[str, Any], manifest: dict[str, Any]) -> None:
    source = descriptor.get("source", {})
    if manifest.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        fail("compact manifest schema version drifted")
    if manifest.get("source_id") != source.get("source_id") or manifest.get("source_id") != "S11":
        fail("source ID drifted")
    if manifest.get("source_file") != source.get("source_file"):
        fail("source file drifted")
    if manifest.get("source_sha256") != source.get("source_sha256"):
        fail("registered S11 SHA-256 drifted")
    if manifest.get("source_inventory_count") != 795 or source.get("inventory_count") != 795:
        fail("source inventory count must remain exactly 795")

    article_template = manifest.get("article_id_template")
    if article_template != descriptor.get("stable_identity", {}).get("article_id_template"):
        fail("article ID template drifted")
    if article_template != "ct.article.recovered.{recovered_order:04d}":
        fail("unexpected article ID template")

    encoding = manifest.get("record_encoding", {})
    if encoding.get("fields") != EXPECTED_RECORD_FIELDS:
        fail("compact record field encoding drifted")
    if descriptor.get("record_encoding", {}).get("fields") != EXPECTED_RECORD_FIELDS:
        fail("descriptor record field encoding drifted")

    defaults = manifest.get("record_defaults")
    if defaults != EXPECTED_DEFAULTS:
        fail("manifest safe default record state drifted")
    if descriptor.get("default_record_state") != EXPECTED_DEFAULTS:
        fail("descriptor safe default record state drifted")

    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 795:
        fail("manifest must contain exactly 795 compact records")

    inventory_ids: list[str] = []
    orders: list[int] = []
    article_ids: list[str] = []
    sections: Counter[str] = Counter()

    for position, record in enumerate(records, 1):
        if not isinstance(record, list) or len(record) != len(EXPECTED_RECORD_FIELDS):
            fail(f"record {position} does not match compact positional schema")
        inventory_id, order, section, subcategory, title = record
        expected_inventory = f"HC-{position:04d}"
        expected_article = f"ct.article.recovered.{position:04d}"
        if inventory_id != expected_inventory:
            fail(f"record {position} inventory ID drifted: {inventory_id!r}")
        if order != position:
            fail(f"record {position} recovered order drifted: {order!r}")
        if not isinstance(section, str) or not section.strip():
            fail(f"record {position} lacks recovered section")
        if not isinstance(subcategory, str) or not subcategory.strip():
            fail(f"record {position} lacks recovered subcategory")
        if not isinstance(title, str) or not title.strip():
            fail(f"record {position} lacks recovered title")

        inventory_ids.append(inventory_id)
        orders.append(order)
        article_ids.append(expected_article)
        sections[section] += 1

    if len(set(inventory_ids)) != 795:
        fail("duplicate inventory IDs detected")
    if len(set(orders)) != 795 or orders != list(range(1, 796)):
        fail("recovered order sequence is incomplete or duplicated")
    if len(set(article_ids)) != 795:
        fail("derived stable article IDs are not unique")
    if article_ids[0] != descriptor["stable_identity"]["first_article_id"]:
        fail("first stable article ID drifted")
    if article_ids[-1] != descriptor["stable_identity"]["last_article_id"]:
        fail("last stable article ID drifted")

    if dict(sections) != EXPECTED_SECTION_CENSUS:
        fail(f"section census drifted: {dict(sections)!r}")
    if descriptor.get("expected_section_census") != EXPECTED_SECTION_CENSUS:
        fail("descriptor section census drifted")
    if len(sections) != source.get("top_level_section_count"):
        fail("top-level section count drifted")

    if descriptor.get("publication_state") != "machine_manifest_materialized_canonical_via_pr_91":
        fail("machine materialization must remain bound to the governed PR #91 merge")
    materialization = descriptor.get("materialization", {})
    if materialization.get("state") != "merged_canonical" or materialization.get("pull_request") != 91:
        fail("canonical materialization provenance drifted")
    if descriptor.get("terminal_disposition_state") != "incomplete":
        fail("terminal disposition may not be falsely promoted")
    if descriptor.get("p0_p1_reconstruction_state") != "incomplete":
        fail("P0/P1 reconstruction may not be falsely promoted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--materialize-output",
        type=Path,
        help="Optional output path for the validated uncompressed compact JSON. Does not change source authority.",
    )
    args = parser.parse_args()

    descriptor, _compressed, raw, manifest = load_bundle()
    validate_manifest(descriptor, manifest)

    if args.materialize_output:
        output = args.materialize_output
        if not output.is_absolute():
            output = ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(raw)
        print(f"Validated compact JSON materialized at {output}")

    print("Help Center 795 canonical machine-manifest bundle validation: PASS")
    print("Recovered records: 795; stable article identities derivable: 795; section census: 9 sections.")
    print("Source authority: S11; original article bodies remain unrecovered unless separately proven.")
    print("Machine materialization: CANONICAL via governed PR #91 merge.")
    print("Terminal disposition: INCOMPLETE; P0/P1 substantive reconstruction: INCOMPLETE.")
    print("Important: bundle PASS != Phase 2.99 Workstream 0 completion or hard-exit PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
