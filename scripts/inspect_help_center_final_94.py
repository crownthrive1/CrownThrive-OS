#!/usr/bin/env python3
from __future__ import annotations
import base64, gzip, json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/help_center_article_manifest.v1.bundle.json"
ALREADY_MAPPED = {"CrownThrive Legal Depot", "CHLOM", "Convergent Ecosystem"}

bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
encoded = "".join((ROOT / p).read_text(encoding="utf-8").strip() for p in bundle["parts"])
decoded = json.loads(gzip.decompress(base64.b64decode(encoded)).decode("utf-8"))
fields = bundle.get("record_encoding", {}).get("fields", [])
records = decoded.get("records", decoded.get("rows", decoded)) if isinstance(decoded, dict) else decoded
normalized = []
for i, row in enumerate(records, 1):
    r = dict(zip(fields, row)) if isinstance(row, list) else dict(row)
    r.setdefault("recovered_order", r.get("order", i))
    r.setdefault("recovered_section", r.get("section"))
    r.setdefault("recovered_subcategory", r.get("subcategory"))
    r.setdefault("recovered_title", r.get("title"))
    normalized.append(r)

if len(normalized) != 795:
    raise SystemExit(f"expected 795 records, found {len(normalized)}")
out = [r for r in normalized if r.get("recovered_section") not in ALREADY_MAPPED]
if len(out) != 94:
    all_counts = Counter(str(r.get("recovered_section")) for r in normalized)
    raise SystemExit(f"expected 94 remaining records after mapped sections, found {len(out)}; all_section_counts={dict(sorted(all_counts.items()))}")

section_counts = Counter(str(r.get("recovered_section")) for r in out)
by_section = defaultdict(lambda: Counter())
for r in out:
    by_section[str(r["recovered_section"])][str(r["recovered_subcategory"])] += 1

print("PASS_FINAL_94_INSPECTION")
print("records=94")
print("already_mapped_sections=" + json.dumps(sorted(ALREADY_MAPPED), ensure_ascii=False))
print("section_counts=" + json.dumps(dict(sorted(section_counts.items())), ensure_ascii=False, sort_keys=True))
for section in sorted(section_counts):
    print(f"SECTION::{section}::{section_counts[section]}")
    print("SUBCATEGORY_COUNTS::" + json.dumps(dict(sorted(by_section[section].items())), ensure_ascii=False, sort_keys=True))
    for r in sorted((x for x in out if str(x["recovered_section"]) == section), key=lambda x: int(x["recovered_order"])):
        print(f"TITLE::{r['recovered_subcategory']}::{r['recovered_title']}")
