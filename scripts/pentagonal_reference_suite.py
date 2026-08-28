#!/usr/bin/env python3
"""Generate and validate CrownThrive's Pentagonal Penta reference suite."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
_HELPER_DIR = str(Path(__file__).resolve().parent)
if _HELPER_DIR not in sys.path:
    sys.path.insert(0, _HELPER_DIR)
from pentagonal_reference_catalog import *
from pentagonal_reference_core import *
from pentagonal_reference_render import *

# Stable public names consumed by tests and downstream validators.
BEGIN_PORTAL, BEGIN_DEV, BEGIN_AGENT = PORTAL_B, DEV_B, AGENT_B
nav_pages = navpages

def apply():
    m=build(); dump(MANIFEST,m); JSONL.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in jsonlines(m)),encoding="utf-8")
    for rel,content in pages(m).items():
        p=ROOT/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding="utf-8")
    e=patch_shared(True)
    if e: raise ValueError(" | ".join(e))
    DOCS.write_text(json.dumps(nav(load(DOCS),m),indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    q=quality(); receipt=q.apply_repository(ROOT); errs,stats=q.validate_repository(ROOT)
    if errs: raise ValueError("PentaDocs quality failed: "+" | ".join(errs[:30]))
    return {"status":"APPLIED","axes":5,"terms":m["counts"]["terms"],"papers":m["counts"]["papers"],"routes":len(m["reference_routes"]),"manifest_sha256":m["manifest_sha256"],"quality":receipt,"quality_stats":stats}

def check():
    m=build(); errs=[]
    if not MANIFEST.exists() or load(MANIFEST)!=m: errs.append("manifest drift")
    if not JSONL.exists() or [json.loads(x) for x in JSONL.read_text(encoding="utf-8").splitlines() if x.strip()]!=jsonlines(m): errs.append("JSONL drift")
    mk=mark(m)
    for rel in pages(m):
        p=ROOT/rel
        if not p.exists(): errs.append(f"missing {rel}")
        elif mk not in p.read_text(encoding="utf-8"): errs.append(f"stale hash {rel}")
    errs.extend(patch_shared(False))
    np=navpages(load(DOCS))
    for r in m["reference_routes"]:
        if np.count(r)!=1: errs.append(f"nav multiplicity {r}={np.count(r)}")
    if m["counts"]["terms"]<100: errs.append(f"dictionary shallow {m['counts']['terms']}")
    if m["counts"]["papers"]<10: errs.append("paper suite shallow")
    q=quality(); qe,stats=q.validate_repository(ROOT); errs.extend("PentaDocs: "+x for x in qe)
    if errs: raise SystemExit("Pentagonal reference drift:\n"+"\n".join(errs[:120]))
    return {"status":"PASS","axes":5,"terms":m["counts"]["terms"],"papers":m["counts"]["papers"],"routes":len(m["reference_routes"]),"manifest_sha256":m["manifest_sha256"],"quality_stats":stats}

def main():
    ap=argparse.ArgumentParser(); g=ap.add_mutually_exclusive_group(required=True); g.add_argument("--apply",action="store_true"); g.add_argument("--check",action="store_true"); a=ap.parse_args()
    r=apply() if a.apply else check(); print(json.dumps(r,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())