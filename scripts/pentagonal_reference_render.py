#!/usr/bin/env python3
"""Human and machine projection renderer for the Pentagonal reference suite."""
from __future__ import annotations
import importlib.util, json, re, sys
from collections import defaultdict
from typing import Any
from pentagonal_reference_catalog import *
from pentagonal_reference_core import *

def mark(m): return f"<!-- pentagonal-reference-sha256:{m['manifest_sha256']} -->"
def axislinks(): return " · ".join(f"[{a.title()}](/pentas/axes/{a})" for a in AXES)

def pages(m):
    out={}
    axisrows="\n".join(f"| [{x['name']}](/pentas/axes/{x['id']}) | **{x['component_count']}** | {x['definition']} |" for x in m["pentagonal_model"]["axes"])
    dims="\n".join(f"| `{d['id']}` | {d['question']} | `{d['source']}` |" for d in m["operational_dimensions"])
    out["pentas/pentagonal.mdx"]=fm("Pentagonal Architecture","Canonical five-axis Penta architecture and operating-coordinate relationship.","developer","doctrine","ct.article.penta.pentagonal-v1")+f"""{mark(m)}
# Pentagonal Architecture

**Pentagonal** is literal architecture: the canonical component registry defines five axes—**truth, authority, execution, interoperation and continuity**.

## What a Penta is

{PENTA}

## Five axes

| Axis | Core components | Responsibility |
| --- | ---: | --- |
{axisrows}

## Five-question design test

1. **Truth:** What is the governing identity/contract/state assertion?
2. **Authority:** Who/what may decide or act, in what scope?
3. **Execution:** What performs the bounded work?
4. **Interoperation:** How do bounded parts exchange work/data/events/evidence?
5. **Continuity:** How are evidence, history, reconciliation, recovery and succession preserved?

## Operating coordinates

| Coordinate | Question | Source |
| --- | --- | --- |
{dims}

**Family is not layer. Layer is not job. Job is not lifecycle. Audience is not authority. Pentagonal axis is not production state.**

`DOCUMENTED ≠ ROUTABLE ≠ EXECUTION-ELIGIBLE ≠ AUTHORIZED ≠ CERTIFIED ≠ PRODUCTION`.

Read [Penta Anatomy](/pentas/anatomy), [Dictionary](/pentas/dictionary), [Deep Index](/pentas/index), [Paper Series](/pentas/papers), [Layers](/pentas/layers), [Jobs](/pentas/jobs), and [Agent Ingestion](/pentas/agents).
"""
    out["pentas/anatomy.mdx"]=fm("Penta Anatomy","Minimum identity, contracts, state, authority, observability and lifecycle anatomy of a Penta.","developer","reference","ct.article.penta.anatomy-v1")+f"""{mark(m)}
# Penta Anatomy

{PENTA}

## Minimum institutional anatomy

| Field | Required question |
| --- | --- |
| Stable identity / machine key | What durable identity survives provider/version changes? |
| Role and non-authorities | What bounded job exists and what is prohibited? |
| Family / axis / layer / jobs | Where does it belong and what work may route toward it? |
| Lifecycle / audiences | When does it participate and who consumes the contract? |
| Interfaces / data | What versioned API/MCP/event/state/data contracts exist? |
| Authority / risk | What may it do under which grants, consent, security, rights/economic constraints? |
| Dependencies / providers | What must be healthy/bound first? |
| Readiness / observability | How are health, version, incidents and evidence freshness read? |
| Reliability | What are timeout, retry, idempotency, reconciliation and recovery semantics? |
| Evidence / readback | What proves material action/result? |
| Owner / escalation | Who owns ambiguity/failure/exceptions? |
| Version / supersession | How are migrations/history preserved? |

## Not automatically agentic or executable

A Penta may be deterministic, human-operated, agentic, provider-backed, data-centric or composite. Canonical identity, execution eligibility, readiness, authority, provider binding, certification and production remain independent.

Safe path: `intent → job/layer → canonical identity → readiness → authority → dependencies/bindings → narrow interface → execution → readback/evidence → status/reconciliation`.

{axislinks()}
"""
    out["pentas/axes.mdx"]=fm("Pentagonal Axes","Five foundational Penta architecture axes.","developer","registry","ct.article.penta.axes-v1")+f"""{mark(m)}
# Pentagonal Axes

| Axis | Core components | Responsibility |
| --- | ---: | --- |
{axisrows}

Axis membership is primary architectural responsibility, not permission/readiness/certification/production. Use [families](/pentas/families), [layers](/pentas/layers), [jobs](/pentas/jobs), [lifecycle](/pentas/lifecycle) and [audiences](/pentas/audiences) for complementary operating coordinates.
"""
    for x in m["pentagonal_model"]["axes"]:
        rows="\n".join(f"| {c['name']} | `{c.get('key') or 'unresolved'}` | `{c.get('contract') or 'unresolved'}` | {c.get('role') or 'unresolved'} |" for c in x["components"]) or "| _None_ | - | - | - |"
        out[f"pentas/axes/{x['id']}.mdx"]=fm(f"{x['name']} Axis",x["definition"],"developer","registry",f"ct.article.penta.axis.{x['id']}-v1")+f"""{mark(m)}
# {x['name']} Axis

{x['definition']}

| Registered core Penta | Machine key | Contract | Role |
| --- | --- | --- | --- |
{rows}

Use complete [layers](/pentas/layers) and [jobs](/pentas/jobs) for 406-identity routing. Axis membership never transfers provider, legal, rights, financial, release or D3 authority.

{axislinks()}
"""
    glossary=[x for x in m["terms"] if x["class"] in {"doctrine","architecture","identity","taxonomy","state","governance","evidence","reliability","authority","release","agentic","interoperation","pentagonal_axis"}]
    gb="\n\n".join(f"## {x['term']}\n\n{x['definition']}\n\n**Machine rule:** {x['machine_rule']}" for x in glossary)
    out["pentas/glossary.mdx"]=fm("Penta Glossary","Foundational plain-language Penta/Pentagonal glossary.","operator","reference","ct.article.penta.glossary-v1")+f"""{mark(m)}
# Penta Glossary

For the complete generated corpus, use the [Penta Dictionary](/pentas/dictionary).

{gb}

Agents ingest `data/penta/pentagonal-reference.v1.json`; prose is explanatory context.
"""
    groups=defaultdict(list)
    for x in m["terms"]: groups[x["term"][0].upper()].append(x)
    db=[]
    for letter in sorted(groups):
        db.append(f"## {letter}")
        for x in groups[letter]:
            db.append(f"""### {x['term']}

**Class:** `{x['class']}`  
**Aliases:** {", ".join(f"`{a}`" for a in x["aliases"]) or "None"}  
**Related:** {", ".join(x["related"]) or "None"}  
**Definition:** {x['definition']}  
**Machine rule:** {x['machine_rule']}  
**Sources:** {", ".join(f"`{s}`" for s in x["source_refs"])}  
**Record hash:** `{x['record_sha256']}`
""")
    out["pentas/dictionary.mdx"]=fm("Penta Dictionary","Complete generated terminology dictionary for doctrine, components, families, layers, jobs, lifecycle and audiences.","developer","registry","ct.article.penta.dictionary-v1")+f"""{mark(m)}
# Penta Dictionary

**Terms:** {m['counts']['terms']}

Generated from governed registries/taxonomies plus bounded foundational doctrine.

{"\n".join(db)}
"""
    o=load(OPERATIONAL); ns=defaultdict(list)
    for x in o.get("records",[]): ns[str(x.get("identity","?"))[0].upper()].append(x)
    np=[]
    for letter in sorted(ns):
        np.append(f"### {letter}\n\n| Penta | Namespace | Family | Layers | Jobs |\n| --- | --- | --- | --- | --- |")
        for x in sorted(ns[letter],key=lambda z:str(z.get("identity")).casefold()):
            fam=(x.get("family") or {}).get("name") or "Pending"
            np.append(f"| [{x['identity']}](/"+str(x["docs_path"])+f") | `{x.get('namespace_state')}` | {fam} | {', '.join(x.get('layers',[])[:3]) or 'pending'} | {', '.join(x.get('jobs',[])[:3]) or 'pending'} |")
    tr="\n".join(f"| `{x['term']}` | `{x['class']}` | [Dictionary](/pentas/dictionary) |" for x in m["terms"])
    pr="\n".join(f"| [{x['title']}](/pentas/papers/{x['id']}) | `{x['page_type']}` | `{x['primary_audience']}` |" for x in m["papers"])
    out["pentas/index.mdx"]=fm("Penta Deep Index","Cross-index across axes, all Penta identities, terminology, families, layers, jobs, lifecycle, audiences and papers.","developer","registry","ct.article.penta.index-v1")+f"""{mark(m)}
# Penta Deep Index

[Pentagonal](/pentas/pentagonal) · [Anatomy](/pentas/anatomy) · [Axes](/pentas/axes) · [Families](/pentas/families) · [Layers](/pentas/layers) · [Jobs](/pentas/jobs) · [Lifecycle](/pentas/lifecycle) · [Audiences](/pentas/audiences) · [Glossary](/pentas/glossary) · [Dictionary](/pentas/dictionary) · [FAQ](/pentas/faq) · [Papers](/pentas/papers)

## Terminology index

| Term | Class | Reference |
| --- | --- | --- |
{tr}

## Paper index

| Paper | Type | Audience |
| --- | --- | --- |
{pr}

## Complete Penta namespace ({m['counts']['namespace_identities']})

{"\n".join(np)}
"""
    qa=[("What is a Penta?",PENTA),("Why Pentagonal?","The canonical component registry already declares five axes: truth, authority, execution, interoperation and continuity."),
        ("Is every Penta an AI agent?","No. Agentic execution is one implementation form; many Pentas are controls, registries, workflows, transports, factories, knowledge/evidence systems or composites."),
        ("Does a Penta name mean it can execute?","No. Identity, eligibility, readiness, authority, binding, certification and production are independent."),
        ("Axis vs family vs layer vs job?","Axis=foundational responsibility; family=institutional home; layer=stack placement; job=work class; lifecycle=when; audience=consumer."),
        ("How should an agent find the right Penta?","Load reference + agent manifests, normalize intent to jobs, filter layer/family, prefer canonical targets, then resolve live gates."),
        ("What happens to a new Penta name?","It enters candidate/canonicalization unless already governed, preserving discovery without manufacturing authority."),
        ("Can documentation prove production?","No. Production needs applicable runtime/release/provider readback evidence."),
        ("What does PentaScribe do?","The component registry assigns PentaScribe canonical institutional language, semantic continuity and glossary/dictionary/index/FAQ compilation."),
        ("Safest retry rule?","Retry only when replay safety/idempotency is known; otherwise read back and reconcile."),
        ("What is exact-head?","Approval/tests/release bind to one exact commit/artifact; changed bytes require re-evaluation."),
        ("What should external agents ingest?","`data/penta/pentagonal-reference.v1.json` then `data/penta/agent-knowledge.v1.json`, then target live contracts/status/authority.")]
    out["pentas/faq.mdx"]=fm("Penta FAQ","Frequently asked Penta/Pentagonal architecture, routing, authority and agent questions.","operator","support","ct.article.penta.faq-v1")+mark(m)+"\n# Penta FAQ\n\n"+"\n\n".join(f"## {q}\n\n{a}" for q,a in qa)
    rows="\n".join(f"| [{x['title']}](/pentas/papers/{x['id']}) | `{x['page_type']}` | `{x['primary_audience']}` | {x['thesis']} |" for x in m["papers"])
    out["pentas/papers.mdx"]=fm("Pentagonal Paper Series","Penta/Pentagonal doctrine, architecture, development, agent, reliability and semantic-continuity papers.","developer","registry","ct.article.penta.papers-v1")+f"""{mark(m)}
# Pentagonal Paper Series

| Paper | Type | Audience | Thesis |
| --- | --- | --- | --- |
{rows}

Developers: Pentagonal Architecture → Penta Doctrine → Development Contract → Interoperation. Agents load machine manifests first, then Agent Ingestion. Operators prioritize Operating Model → Authority/Evidence/State → Lifecycle/Reliability.

Papers are architecture/documentation references, not live provider/runtime/legal/rights/economic authority.
"""
    for pid,title,aud,typ,thesis,sections in PAPERS:
        sec="\n\n".join(f"## {h}\n\n{b}" for h,b in sections)
        out[f"pentas/papers/{pid}.mdx"]=fm(title,thesis,aud,typ,f"ct.article.penta.paper.{pid}-v1")+f"""{mark(m)}
# {title}

**Paper ID:** `ct.paper.penta.{pid}.v1`

## Thesis

{thesis}

{sec}

## Machine/implementation consequences

- Resolve canonical source records instead of treating this paper as live runtime state.
- Preserve identity, authority, data/evidence and version context through handoffs.
- Prefer explicit machine contracts over prose inference.
- Fail closed on unresolved high-consequence predicates.
- Record readback/evidence for material execution and preserve supersession/correction lineage.

[Pentagonal Architecture](/pentas/pentagonal) · [Penta Anatomy](/pentas/anatomy) · [Dictionary](/pentas/dictionary) · [Deep Index](/pentas/index) · [Agent Ingestion](/pentas/agents)
"""
    return out

def strip(text,b,e): return re.sub(re.escape(b)+r".*?"+re.escape(e),"",text,flags=re.S).rstrip()+"\n"
def patch_shared(write:bool):
    blocks={
      "pentas.mdx":(PORTAL_B,PORTAL_E,f"""{PORTAL_B}
## Pentagonal reference suite
[Pentagonal Architecture](/pentas/pentagonal), [Penta Anatomy](/pentas/anatomy), [Five Axes](/pentas/axes), [Glossary](/pentas/glossary), [Dictionary](/pentas/dictionary), [Deep Index](/pentas/index), [FAQ](/pentas/faq), and [Paper Series](/pentas/papers) are generated from governed Penta sources.
{PORTAL_E}"""),
      "pentas/development.mdx":(DEV_B,DEV_E,f"""{DEV_B}
## Pentagonal developer read order
1. [Pentagonal Architecture](/pentas/pentagonal) + [Penta Anatomy](/pentas/anatomy).
2. Select canonical target through [jobs](/pentas/jobs), [layers](/pentas/layers) and family.
3. Load `data/penta/pentagonal-reference.v1.json` + target `data/penta/operational-knowledge.v1.json` record.
4. Resolve source contracts, authority/readiness/dependencies/provider bindings.
5. Implement explicit data/error/idempotency/evidence/recovery contracts and denied/degraded tests.
6. Release exact head and verify provider/runtime readback.
See [Development Contract](/pentas/papers/penta-development-contract) and [Interoperation](/pentas/papers/penta-interoperation-handoffs).
{DEV_E}"""),
      "pentas/agents.mdx":(AGENT_B,AGENT_E,f"""{AGENT_B}
## Pentagonal agent boot sequence
1. `data/penta/pentagonal-reference.v1.json` — definitions, axes, terms, papers and hard rules.
2. `data/penta/agent-knowledge.v1.json` — per-Penta routing records.
3. Target canonical machine/API/MCP/event/data contracts.
4. Current PentaStatus/readiness, authority trace, dependencies and applicable provider binding.
5. Idempotency/retry and expected readback/evidence destination.
See [Agent Ingestion & Routing](/pentas/papers/penta-agent-ingestion-routing). Documentation match is never an authority grant.
{AGENT_E}""")}
    errs=[]
    for rel,(b,e,block) in blocks.items():
        p=ROOT/rel
        if not p.exists(): errs.append(f"missing shared page {rel}"); continue
        text=p.read_text(encoding="utf-8")
        if write: p.write_text(strip(text,b,e).rstrip()+"\n"+block+"\n",encoding="utf-8")
        elif text.count(b)!=1 or text.count(e)!=1: errs.append(f"shared block multiplicity {rel}")
    return errs

def navpages(d):
    out=[]
    for tab in d.get("navigation",{}).get("tabs",[]):
        if isinstance(tab,dict) and tab.get("tab")=="Pentas":
            for g in tab.get("groups",[]):
                if isinstance(g,dict): out.extend(x for x in g.get("pages",[]) if isinstance(x,str))
    return out
def nav(d,m):
    tab=next((x for x in d.get("navigation",{}).get("tabs",[]) if isinstance(x,dict) and x.get("tab")=="Pentas"),None)
    if not tab: raise ValueError("Pentas navigation tab missing")
    gs=[g for g in tab.get("groups",[]) if not(isinstance(g,dict) and g.get("group")=="Pentagonal Reference Suite")]
    pos=next((i+1 for i,g in enumerate(gs) if isinstance(g,dict) and g.get("group")=="Operational Knowledge"),1)
    gs.insert(pos,{"group":"Pentagonal Reference Suite","pages":m["reference_routes"]}); tab["groups"]=gs; return d
def quality():
    p=ROOT/"scripts/pentadocs_quality.py"; spec=importlib.util.spec_from_file_location("pentadocs_quality_pentagonal",p)
    if not spec or not spec.loader: raise RuntimeError("cannot load PentaDocs quality")
    mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod); return mod
def jsonlines(m): return [{"record_type":"term",**x} for x in m["terms"]]+[{"record_type":"paper",**x} for x in m["papers"]]
