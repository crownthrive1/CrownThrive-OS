#!/usr/bin/env python3
"""Core model builder for the Pentagonal reference suite."""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any
from pentagonal_reference_catalog import *

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "penta/registry/penta-component-registry.v1.json"
FAMILIES = ROOT / "penta/registry/penta-families.v1.json"
TAXONOMY = ROOT / "data/penta/operational-taxonomy.v1.json"
OPERATIONAL = ROOT / "data/penta/operational-knowledge.v1.json"
DOCS = ROOT / "docs.json"
MANIFEST = ROOT / "data/penta/pentagonal-reference.v1.json"
JSONL = ROOT / "data/penta/pentagonal-reference.v1.jsonl"

def load(p: Path)->dict[str,Any]:
    v=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(v,dict): raise ValueError(f"expected object: {p}")
    return v
def dump(p:Path,v:Any)->None:
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
def slug(s:str)->str: return re.sub(r"[^a-z0-9]+","-",s.casefold()).strip("-")
def fm(title:str,desc:str,aud="operator",typ="reference",aid="")->str:
    lines=["---",f"title: {json.dumps(title,ensure_ascii=False)}",f"sidebarTitle: {json.dumps(title,ensure_ascii=False)}",f"description: {json.dumps(desc,ensure_ascii=False)}",
           'standard_version: "1.0.0"',f"primary_audience: {json.dumps(aud)}",f"page_type: {json.dumps(typ)}",'content_state: "current_with_holds"']
    if aid: lines.append(f"article_id: {json.dumps(aid)}")
    return "\n".join(lines+["---",""])

def term_record(term,cls,definition,rule,sources,aliases=None,related=None):
    r={"term":term,"slug":slug(term),"class":cls,"definition":definition,"machine_rule":rule,"source_refs":sources,"aliases":aliases or [],"related":related or []}
    r["record_sha256"]=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest(); return r

def build()->dict[str,Any]:
    c,f,t,o=load(COMPONENTS),load(FAMILIES),load(TAXONOMY),load(OPERATIONAL)
    if c.get("axes")!=AXES: raise ValueError(f"Pentagonal axis drift: {c.get('axes')}")
    by_axis={a:[] for a in AXES}
    for x in c.get("components",[]):
        if x.get("axis") not in AXES: raise ValueError(f"unknown axis: {x.get('name')}={x.get('axis')}")
        by_axis[x["axis"]].append({k:x.get(k) for k in ("key","name","role","contract","state","aliases")})
    for v in by_axis.values(): v.sort(key=lambda x:str(x.get("name")).casefold())
    terms=[term_record(*x) for x in FOUNDATION]
    seen={x["term"].casefold() for x in terms}
    for a in AXES:
        terms.append(term_record(f"{a.title()} axis","pentagonal_axis",AXIS_DEF[a],"Axis membership is architectural context, not authority/readiness/production.",["penta/registry/penta-component-registry.v1.json"],[a],["Pentagonal Architecture"]))
    seen={x["term"].casefold() for x in terms}
    for x in c.get("components",[]):
        n=str(x.get("name") or "")
        if not n or n.casefold() in seen: continue
        terms.append(term_record(n,"penta_component",str(x.get("role") or "Canonical Penta component."),f"Resolve canonical contract `{x.get('contract') or 'unresolved'}` and current operating state before use.",["penta/registry/penta-component-registry.v1.json"],list(x.get("aliases") or []),[f"{str(x.get('axis')).title()} axis"]))
        seen.add(n.casefold())
    for x in f.get("families",[]):
        n=str(x.get("canonical_name") or x.get("name") or ""); fid=str(x.get("family_id") or x.get("id") or "")
        if n and n.casefold() not in seen:
            terms.append(term_record(n,"penta_family",str(x.get("mission") or f"Canonical family `{fid}`."),f"Use family `{fid}` for institutional grouping, not task authority.",["penta/registry/penta-families.v1.json"],[],["Penta family"])); seen.add(n.casefold())
    for bucket,cls,parent in [("layers","architectural_layer","Architectural layer"),("jobs","job_function","Job/function"),("lifecycle_stages","lifecycle_stage","Lifecycle stage"),("audiences","audience","Audience")]:
        for x in t.get(bucket,[]):
            n=str(x.get("name") or x.get("id") or "")
            if n and n.casefold() not in seen:
                terms.append(term_record(n,cls,str(x.get("mission") or x.get("description") or f"Taxonomy `{x.get('id')}`."),"Discovery/routing metadata only; never creates authority, maturity or production.",["data/penta/operational-taxonomy.v1.json"],[str(x.get("id"))] if x.get("id") else [],[parent])); seen.add(n.casefold())
    terms.sort(key=lambda x:x["term"].casefold())
    papers=[]
    for pid,title,aud,typ,thesis,sections in PAPERS:
        r={"id":pid,"title":title,"route":f"pentas/papers/{pid}","primary_audience":aud,"page_type":typ,"thesis":thesis,"section_titles":[s[0] for s in sections]}
        r["record_sha256"]=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest(); papers.append(r)
    axes=[{"id":a,"name":a.title(),"definition":AXIS_DEF[a],"component_count":len(by_axis[a]),"components":by_axis[a]} for a in AXES]
    m={"schema_version":"1.0.0","registry_id":"crownthrive.penta.pentagonal-reference.v1",
       "generated_from":[str(COMPONENTS.relative_to(ROOT)),str(FAMILIES.relative_to(ROOT)),str(TAXONOMY.relative_to(ROOT)),str(OPERATIONAL.relative_to(ROOT))],
       "authority_invariant":INVARIANT,"penta_definition":PENTA,"pentagonal_model":{"name":"Pentagonal Architecture","axes":axes},
       "operational_dimensions":[
         {"id":"family","question":"Where does this Penta belong institutionally?","source":"penta/registry/penta-families.v1.json"},
         {"id":"layer","question":"Where does it sit in the technical/operational stack?","source":"data/penta/operational-taxonomy.v1.json"},
         {"id":"job","question":"What class of work does it perform?","source":"data/penta/operational-taxonomy.v1.json"},
         {"id":"lifecycle","question":"When does it participate?","source":"data/penta/operational-taxonomy.v1.json"},
         {"id":"audience","question":"Who consumes or operates the contract?","source":"data/penta/operational-taxonomy.v1.json"}],
       "ingestion_contract":{"read_order":["data/penta/pentagonal-reference.v1.json","data/penta/agent-knowledge.v1.json","target Penta canonical machine contract","current authority + PentaStatus/readiness + dependency/provider evidence"],
        "intent_routing":["jobs","layers","family","namespace_state","audiences"],
        "execution_gate":["canonical identity","registry execution eligibility","current readiness","current authority trace","healthy required dependencies","certified provider binding when applicable","idempotency/retry boundary","expected readback/evidence target"],
        "hard_rules":["Penta name does not grant authority.","Candidate identity is fail-closed for independent execution.","Documentation/taxonomy never manufacture PASS, CERTIFIED or PRODUCTION.","Use the narrowest canonical interface and preserve correlation/authority/evidence context.","Ambiguity routes to docs/search/govern/observe/recover rather than guesswork."]},
       "counts":{"pentagonal_axes":5,"registered_axis_components":sum(map(len,by_axis.values())),"namespace_identities":len(o.get("records",[])),"terms":len(terms),"papers":len(papers),"layers":len(t.get("layers",[])),"jobs":len(t.get("jobs",[])),"lifecycle_stages":len(t.get("lifecycle_stages",[])),"audiences":len(t.get("audiences",[]))},
       "terms":terms,"papers":papers,
       "reference_routes":["pentas/pentagonal","pentas/anatomy","pentas/axes",*[f"pentas/axes/{a}" for a in AXES],"pentas/glossary","pentas/dictionary","pentas/index","pentas/faq","pentas/papers",*[f"pentas/papers/{x[0]}" for x in PAPERS]]}
    m["manifest_sha256"]=hashlib.sha256(json.dumps(m,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return m
