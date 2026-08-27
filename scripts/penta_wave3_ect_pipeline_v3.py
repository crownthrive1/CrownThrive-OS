#!/usr/bin/env python3
"""Final exact-main overrides for Penta Wave 3 ECT."""
from __future__ import annotations
import importlib.util, os, sys
from pathlib import Path
from typing import Any
V2_PIPELINE = Path(os.environ.get("V2_PIPELINE_PATH", "/tmp/penta_wave3_ect_pipeline_v2.py"))
def load_v2():
    spec=importlib.util.spec_from_file_location("penta_wave3_ect_pipeline_v2_loaded",V2_PIPELINE)
    if spec is None or spec.loader is None: raise RuntimeError(f"cannot load v2 ECT pipeline: {V2_PIPELINE}")
    module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
v2=load_v2(); base=v2.base; ROOT=v2.ROOT; v2_reconcile_context_and_builder=v2.reconcile_context_and_builder; base_synchronize_os_golden=base.synchronize_os_golden
def _replace_once(text:str,old:str,new:str,label:str)->str:
    if old in text:return text.replace(old,new,1)
    if new in text:return text
    raise base.PipelineError(f"ECT source contract not found: {label}")
def reconcile_context_and_builder()->None:
    v2_reconcile_context_and_builder(); p=ROOT/"scripts/build_penta_os_v1.py"; b=p.read_text(encoding="utf-8")
    im='                "explicit_registration_state": incoming.get("registration_state"),\n'
    ie=('                "_evidence_backed_maturity": (\n''                    incoming.get("maturity")\n''                    if incoming.get("source_kind") == "production_family_catalog"\n''                    and isinstance(incoming.get("production_evidence"), dict)\n''                    and bool(incoming.get("production_evidence"))\n''                    else None\n''                ),\n')
    if '"_evidence_backed_maturity": (' not in b:b=_replace_once(b,im,im+ie,"evidence-backed maturity initialization")
    pm='            current["dependencies"] = sorted(set(incoming.get("dependencies", [])))\n'
    pe=('            if isinstance(incoming.get("production_evidence"), dict) and incoming.get("production_evidence"):\n''                current["_evidence_backed_maturity"] = incoming.get("maturity")\n')
    if 'current["_evidence_backed_maturity"] = incoming.get("maturity")' not in b:b=_replace_once(b,pm,pm+pe,"evidence-backed maturity production merge")
    fm='    for row in by_token.values():\n        key = row["machine_key"]\n'
    fe=('    for row in by_token.values():\n''        evidence_backed_maturity = row.pop("_evidence_backed_maturity", None)\n''        if evidence_backed_maturity in MATURITY_ORDER:\n''            row["maturity"] = evidence_backed_maturity\n''        key = row["machine_key"]\n')
    if 'evidence_backed_maturity = row.pop("_evidence_backed_maturity", None)' not in b:b=_replace_once(b,fm,fe,"evidence-backed maturity finalization")
    p.write_text(b,encoding="utf-8")
def synchronize_os_golden()->dict[str,Any]:
    result=base_synchronize_os_golden(); p=ROOT/"tests/test_penta_os_v1.py"; t=p.read_text(encoding="utf-8"); stale='("truth", "implemented", "D2")'; prod='("truth", "production", "D2")'; t=t.replace(stale,prod)
    if stale in t: raise base.PipelineError("stale PentaContext implemented-state assertion remains")
    if t.count(prod)<1: raise base.PipelineError("canonical PentaContext production assertion is missing")
    p.write_text(t,encoding="utf-8"); result["penta_context_production_assertion_count"]=t.count(prod); result["authority_anchor_scope"]="unchanged_by_wave3"; return result
base.reconcile_context_and_builder=reconcile_context_and_builder; base.synchronize_os_golden=synchronize_os_golden
if __name__=="__main__": raise SystemExit(base.main())
