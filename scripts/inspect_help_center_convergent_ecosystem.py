#!/usr/bin/env python3
from __future__ import annotations
import base64, gzip, json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/help_center_article_manifest.v1.bundle.json"
TARGET = "Convergent Ecosystem"

bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
encoded = "".join((ROOT / p).read_text(encoding="utf-8").strip() for p in bundle["parts"])
decoded = json.loads(gzip.decompress(base64.b64decode(encoded)).decode("utf-8"))
fields = bundle.get("record_encoding", {}).get("fields", [])
records = decoded.get("records", decoded.get("rows", decoded)) if isinstance(decoded, dict) else decoded
out = []
for i, row in enumerate(records, 1):
    r = dict(zip(fields, row)) if isinstance(row, list) else dict(row)
    r.setdefault("recovered_order", r.get("order", i))
    r.setdefault("recovered_section", r.get("section"))
    r.setdefault("recovered_subcategory", r.get("subcategory"))
    r.setdefault("recovered_title", r.get("title"))
    if r.get("recovered_section") == TARGET:
        out.append(r)

if len(out) != 206:
    raise SystemExit(f"expected 206 records, found {len(out)}")

counts = Counter(str(r.get("recovered_subcategory")) for r in out)
samples = defaultdict(list)
for r in out:
    sub = str(r.get("recovered_subcategory"))
    if len(samples[sub]) < 12:
        samples[sub].append(str(r.get("recovered_title")))

print("PASS_CONVERGENT_ECOSYSTEM_INSPECTION")
print("records=206")
print("subcategory_counts=" + json.dumps(dict(sorted(counts.items())), ensure_ascii=False, sort_keys=True))
for sub in sorted(samples):
    print(f"SUBCATEGORY::{sub}::{counts[sub]}")
    for title in samples[sub]:
        print("TITLE::" + title)
