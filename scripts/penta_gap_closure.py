#!/usr/bin/env python3
"""PENTA institutional gap classifier.

Fail-closed scanner for stale institutional phase claims. Historical/archive material is
preserved; active material that still presents retired decimal phases as current is flagged.
No provider writes or destructive mutation are performed by this utility.
"""
from __future__ import annotations
import argparse, json, pathlib, re, sys

RETIRED = re.compile(r"\bPhase\s+2\.(?:5|7|8|9|95|97|98|99)\b", re.I)
CURRENT_STALE = re.compile(r"(?:current institutional phase|phase remains|remains current|current state)[^\n]{0,100}Phase\s+2\.(?:5|7|8|9|95|97|98|99)", re.I)
HISTORICAL_HINTS = ("archive/", "changelog/", "historical", "superseded", "retired", "lineage", "recovery")


def classify(path: pathlib.Path, text: str) -> dict:
    rel = path.as_posix()
    hits = [m.group(0) for m in RETIRED.finditer(text)]
    stale = [m.group(0) for m in CURRENT_STALE.finditer(text)]
    historical = any(h in rel.lower() or h in text[:1200].lower() for h in HISTORICAL_HINTS)
    if stale and not historical:
        disposition = "REPAIR_REQUIRED"
    elif hits:
        disposition = "PRESERVE_HISTORICAL_ALIAS" if historical else "REVIEW_CONTEXT"
    else:
        disposition = "PASS"
    return {"path": rel, "disposition": disposition, "retired_alias_hits": len(hits), "stale_current_claim_hits": len(stale)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = pathlib.Path(args.root)
    rows=[]
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".md", ".mdx", ".json", ".yml", ".yaml", ".py", ".sql"} and ".git" not in p.parts:
            try: text=p.read_text(encoding="utf-8")
            except UnicodeDecodeError: continue
            row=classify(p.relative_to(root), text)
            if row["disposition"] != "PASS": rows.append(row)
    summary={"service":"ct.penta.gap-closure.v1","rule":"retired phase aliases may remain as history but not current instruction","counts":{k:sum(r["disposition"]==k for r in rows) for k in ("REPAIR_REQUIRED","REVIEW_CONTEXT","PRESERVE_HISTORICAL_ALIAS")},"findings":rows}
    print(json.dumps(summary, indent=2) if args.json else "\n".join(f"{r['disposition']}: {r['path']}" for r in rows))
    return 2 if summary["counts"]["REPAIR_REQUIRED"] else 0

if __name__ == "__main__":
    sys.exit(main())
