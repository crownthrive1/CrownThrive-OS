#!/usr/bin/env python3
import argparse
import json
import pathlib
from collections import Counter

DEFAULT_SOURCE_ID = "S11"
DEFAULT_SOURCE_SHA = "c7f16bd8b504431e71a4407728e22ab9a950ab9dcd891d831bd78f6802335b0f"

REQUIRED_FIELDS = {
    "inventory_id",
    "order",
    "section",
    "subcategory",
    "title",
    "source",
    "recovery_status",
    "body_status",
    "confidence",
}


def load_inventory(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("inventory root must be a list")
    return data


def build_manifest(rows, verified_at="2026-08-18"):
    seen_inventory_ids = set()
    records = []

    for index, row in enumerate(rows, 1):
        missing = REQUIRED_FIELDS.difference(row)
        if missing:
            raise ValueError(f"row {index} missing required fields: {sorted(missing)}")

        inventory_id = row["inventory_id"]
        if inventory_id in seen_inventory_ids:
            raise ValueError(f"duplicate inventory_id: {inventory_id}")
        seen_inventory_ids.add(inventory_id)

        records.append(
            {
                "article_id": f"ct.article.recovered.{index:04d}",
                "inventory_id": inventory_id,
                "recovered_order": int(row["order"]),
                "recovered_section": row["section"],
                "recovered_subcategory": row["subcategory"],
                "recovered_title": row["title"],
                "source_id": DEFAULT_SOURCE_ID,
                "source_file": row["source"],
                "source_sha256": DEFAULT_SOURCE_SHA,
                "recovery_status": row["recovery_status"],
                "body_status": row["body_status"],
                "confidence": row["confidence"],
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
                "source_refs": [DEFAULT_SOURCE_ID],
                "related_article_ids": [],
                "redirects_from": [],
                "effective_at": None,
                "last_verified_at": verified_at,
                "correction_events": [],
            }
        )

    if len(records) != 795:
        raise ValueError(f"expected 795 recovered records, found {len(records)}")

    article_ids = [record["article_id"] for record in records]
    if len(article_ids) != len(set(article_ids)):
        raise ValueError("duplicate article_id generated")

    section_counts = Counter(record["recovered_section"] for record in records)

    return {
        "schema_version": "1.0.0",
        "source_id": DEFAULT_SOURCE_ID,
        "source_sha256": DEFAULT_SOURCE_SHA,
        "source_inventory_count": len(records),
        "section_counts": dict(sorted(section_counts.items())),
        "records": records,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate CrownThrive's deterministic 795-record Help Center article seed manifest."
    )
    parser.add_argument("input", help="Path to help_center_inventory.json")
    parser.add_argument(
        "-o",
        "--output",
        default="data/help_center_article_seed_manifest.json",
        help="Output manifest path",
    )
    args = parser.parse_args()

    inventory = load_inventory(args.input)
    manifest = build_manifest(inventory)

    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"wrote {len(manifest['records'])} records to {output}")
    print(json.dumps(manifest["section_counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
