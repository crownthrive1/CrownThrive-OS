#!/usr/bin/env python3
'''Generate the registry-driven PentaDocs portal and namespace census.

The generator projects current registry truth into documentation. It never
promotes maturity, creates authority, or converts a candidate/reference name
into a canonical Penta merely because a page exists.
'''
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OS_REGISTRY = ROOT / "data/penta/os-v1.registry.json"
CANDIDATE_SEED = ROOT / "data/penta/namespace-candidates.v1.json"
FAMILY_REGISTRY = ROOT / "penta/registry/penta-families.v1.json"
FAMILY_RUNTIME = ROOT / "runtime/penta_families.py"
DOC_ROOT = ROOT / "pentas"
DOCS_CONFIG = ROOT / "docs.json"

FAMILY_IDS = {
    "system-architecture", "routing-interoperability", "transport-primitives",
    "automation-agentic", "build-release", "security-trust",
    "resilience-continuity", "observability-organic",
    "knowledge-semantics-data", "governance-legal", "workforce-people",
    "intelligence-research", "communications-service", "media-creative",
    "commerce-economy",
}

def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value

def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"[™®]", "", str(name)).casefold())

def slugify(name: str) -> str:
    clean = re.sub(r"[™®]", "", str(name)).strip()
    clean = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", clean)
    clean = clean.replace("&", " and ")
    return re.sub(r"[^a-zA-Z0-9]+", "-", clean).strip("-").lower()

def q(value: Any) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=False)

def load_family_snapshot() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("penta_families_runtime", FAMILY_RUNTIME)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Penta family runtime")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.compose_snapshot(ROOT)

def family_maps() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    snapshot = load_family_snapshot()
    by_member: dict[str, dict[str, Any]] = {}
    by_family: dict[str, dict[str, Any]] = {}
    for family in snapshot["families"]:
        by_family[family["family_id"]] = family
        for member in family["members"]:
            by_member[normalize(member["name"])] = {
                "family_id": family["family_id"],
                "family_name": family["canonical_name"],
                "family_slug": family["slug"],
                "assignment_state": "registry_backed",
            }
    return by_member, by_family

def extension_records() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "data/penta").glob("systems*.json")):
        data = load_json(path)
        systems = data.get("systems")
        if not isinstance(systems, list):
            continue
        for row in systems:
            if not isinstance(row, dict):
                continue
            name = row.get("canonical_name")
            if isinstance(name, str) and normalize(name).startswith("penta"):
                item = dict(row)
                item["_source_path"] = path.relative_to(ROOT).as_posix()
                out[normalize(name)] = item
    return out

def infer_family(name: str, row: dict[str, Any] | None = None) -> dict[str, Any]:
    n = normalize(name)
    parent = normalize((row or {}).get("parent_machine_key", ""))
    if parent == "pentagreen":
        fid = "commerce-economy"
    elif parent == "pentafabric":
        fid = "system-architecture"
    else:
        groups = [
            ("security-trust", ("security","secure","auth","vault","identity","privacy","risk","audit","compliance","ofac","red","blue","honeypot","immune","credential","bound","safe","safety","shield","guardian","sentry","sentinel","trust","quarantine")),
            ("build-release", ("factory","build","certify","assure","quality","release","merge","closer","runner","punter","action","result","gate","heal","deploy","compile","generate","lint","ci","qa","prototype","forge")),
            ("resilience-continuity", ("backup","restore","rollback","snapshot","serialized","version","format","sop","sla","time","heartbeat","nurture","continuity","liency","schedule","maintain","sustain","wave","cron")),
            ("observability-organic", ("error","logger","logs","trace","metric","telemetry","observability","brain","spine","nerves","body","load","balancer","health","specter","flagger","tagger","report","alert","pulse","sre")),
            ("knowledge-semantics-data", ("docs","scribe","data","record","notes","sets","maps","stars","context","index","asset","memory","template","changelog")),
            ("governance-legal", ("board","policy","legal","law","contract","license","ethic","capital","procure","vendor","supplier","patent","trademark","rights","govern")),
            ("workforce-people", ("manager","director","cohort","accelerator","triage","hr","benefit","alumni","hybrid","workforce","people","staff","talent","recruit","coach","mentor","volunteer","career","academy","campus","train")),
            ("intelligence-research", ("signal","analytic","institute","impact","research","predict","intelligence","scorecard","reason","census","crawler","stats","roi")),
            ("communications-service", ("mail","concierge","marketer","marketing","campaign","audience","brand","cta","conversion","funnel","seo","content","copy","social","sponsor","persona","loyalty","email","reputation","proposal","customerjourney","landingpage","narrative","offer","growth","community","affiliate","partner","voice")),
            ("media-creative", ("media","studio","books","broadcast","sound","creator","story","print","venue")),
            ("commerce-economy", ("green","credits","pay","cost","market","invoice","payout","checkout","settle","entitle","compensate","ledger","price","sku","bill","budget","finance","cfo","revenue","profit","treasury","fund","venture","economic","account")),
            ("routing-interoperability", ("route","federation","interops","flex","mcp","wire","bind","link","host","node")),
            ("automation-agentic", ("orchestrator","mation","flows","flow","agents","llm","mcl","boxes","skills","tools","rithms","scripts","suite","rfa","maker","workflow","project","sprint","toolkit","lab","kit","assist","advisor","deepresearch")),
            ("system-architecture", ("os","vergence","techture","pology","planes","fabric","mesh","base","control","self","truth","authority","execution","interoperation","family","kernel","axis","hub","site","dev")),
            ("transport-primitives", ("fetch","get","head","options","post","put","patch","delete","query","search","read","list","parse","transform","validate","resolve","observe","cache","sync","ingest","import","export","create","update","upsert","queue","retry","dispatch","lock","reconcile","hook","event","stream","tun","test")),
        ]
        matches = [fid for fid, words in groups if any(word in n for word in words)]
        fid = matches[0] if matches else None
    if fid is None:
        return {"family_id": None, "family_name": "Pending canonical family", "family_slug": None, "assignment_state": "pending_canonicalization"}
    return {"family_id": fid, "family_name": fid.replace("-", " ").title(), "family_slug": fid, "assignment_state": "docs_inferred"}

def build_records() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, dict[str, Any]]]:
    os_registry = load_json(OS_REGISTRY)
    os_rows = os_registry.get("systems", [])
    if len(os_rows) != os_registry["counts"]["total"]:
        raise ValueError("Penta OS registry count drift")
    candidate_seed = load_json(CANDIDATE_SEED)
    seed_names = candidate_seed.get("candidates", [])
    if not all(isinstance(x, str) for x in seed_names):
        raise ValueError("candidate seed must be a string array")
    overrides = candidate_seed.get("overrides", {})
    family_by_member, family_by_id = family_maps()
    extensions = extension_records()

    aliases: dict[str, str] = {}
    for alias in os_registry.get("aliases", []):
        if isinstance(alias, dict) and isinstance(alias.get("alias"), str):
            aliases[normalize(alias["alias"])] = str(alias.get("canonical_machine_key") or "")

    canonical_norms = {normalize(row["canonical_name"]) for row in os_rows}
    names: dict[str, dict[str, Any]] = {}
    for row in os_rows:
        n = normalize(row["canonical_name"])
        names[n] = {"name": row["canonical_name"], "namespace_state": "canonical", "row": row, "source_state": "penta_os_v1_5_registry"}

    for name in seed_names:
        n = normalize(name)
        if n not in names:
            meta = overrides.get(name, {}) if isinstance(overrides, dict) else {}
            names[n] = {"name": name, "namespace_state": "candidate", "row": None, "source_state": meta.get("source_state", "prior_namespace_reconciliation"), "note": meta.get("note")}

    for n, ext in extensions.items():
        if n not in names:
            names[n] = {"name": ext["canonical_name"], "namespace_state": "candidate", "row": None, "source_state": "governed_system_extension"}
        if n not in canonical_norms:
            names[n]["extension"] = ext
            if names[n]["source_state"] == "prior_namespace_reconciliation":
                names[n]["source_state"] = "governed_system_extension"

    for n in family_by_member:
        if n not in names:
            display = next(member["name"] for family in family_by_id.values() for member in family["members"] if normalize(member["name"]) == n)
            names[n] = {"name": display, "namespace_state": "candidate", "row": None, "source_state": "governed_family_extension"}

    used_slugs: dict[str, str] = {}
    records: list[dict[str, Any]] = []
    machine_to_name = {str(row["machine_key"]): row["canonical_name"] for row in os_rows}
    for n, item in sorted(names.items(), key=lambda kv: kv[1]["name"].casefold()):
        name = item["name"]
        row = item.get("row") or {}
        base_slug = slugify(name)
        slug = base_slug
        if slug in used_slugs and used_slugs[slug] != n:
            slug = f"{base_slug}-{hashlib.sha256(n.encode()).hexdigest()[:8]}"
        used_slugs[slug] = n
        fam = family_by_member.get(n) or infer_family(name, row)
        namespace_state = item["namespace_state"]
        alias_machine = aliases.get(n) if namespace_state != "canonical" else None
        extension = item.get("extension")
        candidate_class = None
        if namespace_state != "canonical":
            if alias_machine:
                candidate_class = "alias_reference"
            elif extension:
                candidate_class = "governed_extension"
            else:
                candidate_class = "reference_candidate"

        record = {
            "name": name,
            "normalized_name": n,
            "slug": slug,
            "namespace_state": namespace_state,
            "candidate_class": candidate_class,
            "source_state": item.get("source_state"),
            "note": item.get("note"),
            "canonical_machine_key": row.get("machine_key") if namespace_state == "canonical" else alias_machine,
            "canonical_target_name": machine_to_name.get(alias_machine) if alias_machine else None,
            "kind": row.get("kind") if namespace_state == "canonical" else (extension or {}).get("kind"),
            "role": row.get("role") if namespace_state == "canonical" else (extension or {}).get("purpose"),
            "maturity": row.get("maturity") if namespace_state == "canonical" else (extension or {}).get("maturity"),
            "risk_ceiling": row.get("risk_ceiling") if namespace_state == "canonical" else None,
            "execution_eligible_by_registry": bool(row.get("execution_eligible_by_registry")) if namespace_state == "canonical" else False,
            "strict_readiness_state": row.get("strict_readiness_state") if namespace_state == "canonical" else "NOT_CANONICAL_OS_V1_5_MEMBER",
            "operator_route": row.get("operator_route") if namespace_state == "canonical" else None,
            "public_status_route": row.get("public_status_route") if namespace_state == "canonical" else None,
            "dependencies": row.get("dependencies", []) if namespace_state == "canonical" else [],
            "evidence_paths": row.get("evidence_paths", []) if namespace_state == "canonical" else ([extension["_source_path"]] if extension else []),
            **fam,
        }
        record["docs_path"] = f"pentas/{'canonical' if namespace_state == 'canonical' else 'candidates'}/{slug}"
        records.append(record)
    return records, os_registry, family_by_id

def link_for(record: dict[str, Any]) -> str:
    return "/" + record["docs_path"]

def canonical_page(record: dict[str, Any]) -> str:
    deps = record.get("dependencies") or []
    evidence = record.get("evidence_paths") or []
    fam_link = f"/pentas/families/{record['family_slug']}" if record.get("family_slug") else "/pentas/families"
    dep_text = ", ".join(f"`{d}`" for d in deps) if deps else "No dependency edges are declared in this registry snapshot."
    evidence_text = "\n".join(f"- `{p}`" for p in evidence[:20]) if evidence else "- No dedicated evidence path is embedded in this registry snapshot."
    return f'''---
title: {q(record["name"])}
sidebarTitle: {q(record["name"])}
description: {q("Registry-driven PentaDocs portal guide for " + record["name"] + ".")}
---

# {record["name"]}

> **Canonical registry member.** Documentation is a projection of governed state, not a maturity or authority promotion.

## Overview
**Mission / role:** {record.get("role") or "Resolve the live role from `data/penta/os-v1.registry.json`."}

| Field | Registry value |
| --- | --- |
| Machine key | `{record.get("canonical_machine_key") or "unresolved"}` |
| Kind | `{record.get("kind") or "unspecified"}` |
| Maturity | `{record.get("maturity") or "unspecified"}` |
| Risk ceiling | `{record.get("risk_ceiling") or "unspecified"}` |
| Execution eligible by registry | `{str(bool(record.get("execution_eligible_by_registry"))).lower()}` |
| Strict readiness | `{record.get("strict_readiness_state") or "unresolved"}` |
| Family | [{record.get("family_name") or "Family directory"}]({fam_link}) |
| Family assignment | `{record.get("assignment_state")}` |
| Operator route | `{record.get("operator_route") or "resolve from registry"}` |
| Public status route | `{record.get("public_status_route") or "resolve from registry"}` |

## Responsibilities
Operate only within the canonical role, contracts, maturity, risk ceiling, dependency gates, CHLOM/DAIL authority, PentaHybrid controls, and certified provider bindings. This page cannot broaden any of them.

## Inputs & outputs
Inputs, outputs, events, state transitions, provider bindings, and data stores are governed by the machine registry, linked contracts, interoperability envelopes, and implementation evidence.

## Authority boundary
`DOCUMENTED ≠ CERTIFIED ≠ AUTHORIZED ≠ PRODUCTION`. No Penta may manufacture legal, economic, security, licensing, governance, credential, fiduciary, provider-write, or D3/human authority.

## Family & related Pentas
Primary family context: [{record.get("family_name") or "Pending family classification"}]({fam_link}). Sibling, upstream, downstream, and cross-family relationships resolve through the family topology and dependency graph rather than prose inference.

## Dependencies
{dep_text}

## SOPs, SLAs, runbooks & guides
Use PentaSOPs, PentaSLAs, PentaDocs, owner/admin guides, incident playbooks, and system-specific runbooks. Missing required operating material is a readiness defect.

## Evidence
{evidence_text}

## API / MCP
Use the canonical machine key, PentaMCP/PentaRoute interoperability envelopes, explicit authority traces, idempotency, certified provider bindings, and readback. This documentation route is not an execution proxy.

## Releases & changelog
Version, release, migration, rollback, supersession, and exact-head evidence remain independently governed by PentaVersion, PentaSerialized, PentaRelease, PentaAssure, and DAIL.

## Support
Return to the [Penta Portal](/pentas), [canonical directory](/pentas/canonical), or [family directory](/pentas/families). Escalation and accountable ownership remain system-specific.
'''

def candidate_page(record: dict[str, Any], by_machine: dict[str, dict[str, Any]]) -> str:
    fam_link = f"/pentas/families/{record['family_slug']}" if record.get("family_slug") else "/pentas/families"
    target = by_machine.get(record.get("canonical_machine_key")) if record.get("canonical_machine_key") else None
    target_line = f"[{target['name']}]({link_for(target)})" if target else "No canonical target is established."
    extension_note = ""
    if record.get("candidate_class") == "governed_extension":
        extension_note = f" A governed extension record currently reports maturity `{record.get('maturity') or 'unspecified'}`, but it is outside the frozen Penta OS V1.5 canonical registry."
    return f'''---
title: {q(record["name"])}
sidebarTitle: {q(record["name"])}
description: {q("Penta namespace reference and canonicalization guide for " + record["name"] + ".")}
---

# {record["name"]}

> **Namespace reference / canonicalization pending — not a production claim.** Creating this page does not create a new canonical Penta, maturity, authority, credentials, provider permission, or execution eligibility.{extension_note}

## Overview
This name is preserved so CrownThrive does not lose a previously declared, discovered, extension, or compatibility Penta reference.

| Field | Current docs projection |
| --- | --- |
| Namespace state | `candidate` |
| Candidate class | `{record.get("candidate_class") or "reference_candidate"}` |
| Source state | `{record.get("source_state") or "reference_candidate"}` |
| Canonical target | {target_line} |
| Extension maturity | `{record.get("maturity") or "not asserted"}` |
| Provisional family | [{record.get("family_name") or "Pending canonical family"}]({fam_link}) |
| Family assignment | `{record.get("assignment_state")}` |
| Execution eligible | `false from this namespace record` |

## Responsibilities
PentaScribe and PentaPology must preserve the name, determine whether it is a distinct system, alias, subcomponent, primitive, engine, or superseded reference, and route any implementation gap to the appropriate governed build lane.

## Inputs & outputs
No new operational I/O contract is created here. Existing source evidence and any governed extension record remain authoritative until canonicalization.

## Authority boundary
This record is fail-closed. It cannot authorize provider writes, spending, money movement, rights, publication, credential use, destructive actions, or D3/human-reserved decisions.

## Family & related Pentas
The family shown above is either registry-backed for an existing extension or a **docs-only provisional classification**. Canonical family assignment must be resolved through the production Penta family registry.

## Dependencies
Dependencies remain `UNRESOLVED` until canonicalization or alias binding establishes an exact machine identity.

## SOPs, SLAs, runbooks & guides
No independent operating SLA is implied. Required guides, SOPs, SLAs, ownership, escalation, access, and recovery controls must be created before institutionalization.

## Evidence
Candidate seed and/or governed extension evidence is preserved in `data/penta/namespace-census.v1.json`. No secret material is projected.

## API / MCP
No independent API/MCP authority is created. If this resolves to an alias, callers must use the canonical target machine key.

## Releases & changelog
Promotion, aliasing, retirement, or subcomponent disposition must be versioned, evidence-backed, and preserved through PentaVersion/PentaSerialized/PentaScribe.

## Support
Return to the [Penta Portal](/pentas), [candidate directory](/pentas/candidates), or [family directory](/pentas/families).
'''

def table(records: list[dict[str, Any]], candidate: bool = False) -> str:
    rows = []
    for r in records:
        family = r.get("family_name") or "Pending"
        status = r.get("candidate_class") if candidate else r.get("maturity")
        rows.append(f'| [{r["name"]}]({link_for(r)}) | `{status or "unspecified"}` | {family} |')
    return "\n".join(rows)

def build_artifacts() -> dict[str, str]:
    records, os_registry, family_by_id = build_records()
    canonical = [r for r in records if r["namespace_state"] == "canonical"]
    candidates = [r for r in records if r["namespace_state"] != "canonical"]
    if len(canonical) != os_registry["counts"]["total"]:
        raise ValueError("canonical docs count does not match Penta OS registry")
    by_machine = {r["canonical_machine_key"]: r for r in canonical if r.get("canonical_machine_key")}
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unassigned: list[dict[str, Any]] = []
    for r in records:
        if r.get("family_id") in FAMILY_IDS:
            by_family[r["family_id"]].append(r)
        else:
            unassigned.append(r)

    counts = Counter(r["candidate_class"] or "canonical" for r in records)
    census = {
        "schema_version": "1.0.0",
        "registry_id": "crownthrive.penta.namespace-census.v1",
        "generated_from": {
            "canonical_registry": "data/penta/os-v1.registry.json",
            "candidate_seed": "data/penta/namespace-candidates.v1.json",
            "family_registry": "penta/registry/penta-families.v1.json",
            "family_runtime": "runtime/penta_families.py"
        },
        "authority_invariant": "Documentation and namespace discovery never manufacture maturity, authority, certification, credentials, provider permission, money movement, rights, release authority, or D3 authority.",
        "counts": {
            "total": len(records), "canonical": len(canonical), "noncanonical": len(candidates),
            "alias_references": counts["alias_reference"], "governed_extensions": counts["governed_extension"],
            "reference_candidates": counts["reference_candidate"], "families": len(FAMILY_IDS), "family_pending": len(unassigned)
        },
        "records": records
    }
    artifacts: dict[str, str] = {"data/penta/namespace-census.v1.json": json.dumps(census, indent=2, ensure_ascii=False, sort_keys=True) + "\n"}
    for r in canonical:
        artifacts[r["docs_path"] + ".mdx"] = canonical_page(r)
    for r in candidates:
        artifacts[r["docs_path"] + ".mdx"] = candidate_page(r, by_machine)

    artifacts["pentas/index.mdx"] = f'''---
title: "Penta Portal"
sidebarTitle: "Penta Portal"
description: "Registry-driven PentaDocs portal for every canonical, extension, alias, and candidate Penta identity."
---

# Penta Portal

This is the institutional documentation entrance for the complete Penta namespace.

| Census | Count |
| --- | ---: |
| Total documented identities | **{len(records)}** |
| Canonical Penta OS V1.5 entries | **{len(canonical)}** |
| Noncanonical references/extensions | **{len(candidates)}** |
| Institutional families | **{len(FAMILY_IDS)}** |
| Family classification pending | **{len(unassigned)}** |

<Note>
A page existing here does **not** make a Penta production. Canonical maturity, execution eligibility, strict readiness, provider bindings, and authority remain independently governed.
</Note>

## Enter the system

- [15-family directory](/pentas/families)
- [All canonical Pentas](/pentas/canonical)
- [Candidate, alias & extension queue](/pentas/candidates)
- [Complete A–Z directory](/pentas/all)

## Institutional rule

Every canonical Penta gets a dedicated guide and links back to its machine registry, family topology, status/readiness, evidence, API/MCP boundary, runbooks, releases and support. Every noncanonical reference gets a fail-closed canonicalization page so no name disappears and no name silently becomes production.
'''
    artifacts["pentas/canonical/index.mdx"] = f'''---
title: "Canonical Pentas"
description: "All canonical Penta OS V1.5 registry identities."
---

# Canonical Pentas

**{len(canonical)} canonical registry entries.** Live maturity and readiness come from `data/penta/os-v1.registry.json`.

| Penta | Maturity | Family |
| --- | --- | --- |
{table(canonical)}
'''
    artifacts["pentas/candidates/index.mdx"] = f'''---
title: "Penta Canonicalization Queue"
description: "All noncanonical Penta references, aliases and governed extensions preserved for disposition."
---

# Penta Canonicalization Queue

**{len(candidates)} noncanonical identities are preserved.** None becomes a production system merely because it is documented.

| Penta | Class | Provisional / registry family |
| --- | --- | --- |
{table(candidates, True)}
'''
    all_rows = sorted(records, key=lambda r: r["name"].casefold())
    artifacts["pentas/all.mdx"] = '''---
title: "All Pentas A–Z"
description: "Complete Penta namespace directory."
---

# All Pentas A–Z

| Penta | Namespace | Family |
| --- | --- | --- |
''' + "\n".join(f'| [{r["name"]}]({link_for(r)}) | `{r["namespace_state"]}` | {r.get("family_name") or "Pending"} |' for r in all_rows) + "\n"

    fam_registry = load_json(FAMILY_REGISTRY)
    family_links = []
    for family in fam_registry["families"]:
        fid = family["family_id"]
        members = sorted(by_family.get(fid, []), key=lambda r: r["name"].casefold())
        page = f"pentas/families/{family['slug']}"
        family_links.append((family["canonical_name"], page, len(members)))
        artifacts[page + ".mdx"] = f'''---
title: {q(family["canonical_name"])}
description: {q(family["mission"])}
---

# {family["canonical_name"]}

**Mission:** {family["mission"]}

**Operator family route:** `{family["portal_route"]}`

This page is the documentation projection of the family. Registry-backed assignments and docs-inferred candidate assignments are labeled independently; family membership never promotes child maturity or authority.

## Members documented in this portal

| Penta | Namespace | Assignment |
| --- | --- | --- |
''' + "\n".join(f'| [{r["name"]}]({link_for(r)}) | `{r["namespace_state"]}` | `{r.get("assignment_state")}` |' for r in members) + f'''

## Cross-family handoffs
{", ".join(f"`{x}`" for x in family.get("handoffs_to", [])) or "None declared."}

## Authority boundary
Connectivity, documentation, family placement, readiness, or confidence never creates provider, financial, rights, governance, credential, legal, security, or D3 authority.

## Evidence & operations
Use `penta/registry/penta-families.v1.json`, `runtime/penta_families.py`, the child Penta page, PentaStatus, PentaAssure, DAIL, and CHLOM authority traces.
'''

    artifacts["pentas/families.mdx"] = '''---
title: "Penta Families"
description: "The 15-family Penta institutional topology."
---

# Penta Families

The production family topology groups related Pentas without promoting child maturity or authority.

| Family | Documented identities |
| --- | ---: |
''' + "\n".join(f"| [{name}](/" + page + f") | **{count}** |" for name, page, count in family_links)
    if unassigned:
        artifacts["pentas/families.mdx"] += f"\n\n## Pending family canonicalization\n\n{len(unassigned)} namespace references remain family-pending and stay fail-closed in the [candidate directory](/pentas/candidates).\n"

    artifacts["changelog/penta-portal-full-census-2026-08-28.mdx"] = f'''---
title: "Penta Portal Full Census — 2026-08-28"
description: "Registry-driven PentaDocs portal expansion and namespace reconciliation."
---

# Penta Portal Full Census — August 28, 2026

The PentaDocs surface is now generated from governed sources rather than maintained as a flat manual list.

- Canonical Penta OS V1.5 entries documented: **{len(canonical)}**
- Noncanonical aliases/extensions/candidates documented: **{len(candidates)}**
- Total dedicated Penta pages: **{len(records)}**
- Family portals: **{len(FAMILY_IDS)}**
- Production promotion performed by this docs change: **none**

The generator fails closed on canonical-count drift and preserves candidate/reference identities without manufacturing authority.
'''

    docs = load_json(DOCS_CONFIG)
    penta_tab = {
        "tab": "Pentas",
        "groups": [
            {"group": "Penta Portal", "pages": ["pentas/index", "pentas/all", "pentas/canonical/index", "pentas/candidates/index"]},
            {"group": "15 Families", "pages": [page for _, page, _ in family_links]},
            {"group": "Governance & Evidence", "pages": ["automation/penta-family", "automation/penta-os-v1", "changelog/penta-portal-full-census-2026-08-28"]}
        ]
    }
    tabs = docs.setdefault("navigation", {}).setdefault("tabs", [])
    tabs[:] = [tab for tab in tabs if not (isinstance(tab, dict) and tab.get("tab") == "Pentas")]
    tabs.insert(1, penta_tab)
    artifacts["docs.json"] = json.dumps(docs, indent=2, ensure_ascii=False) + "\n"
    return artifacts

def write_artifacts() -> None:
    artifacts = build_artifacts()
    expected_doc_files = {path for path in artifacts if path.startswith("pentas/")}
    if DOC_ROOT.exists():
        for path in DOC_ROOT.rglob("*.mdx"):
            rel = path.relative_to(ROOT).as_posix()
            if rel not in expected_doc_files:
                path.unlink()
    for rel, content in artifacts.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

def check_artifacts() -> None:
    artifacts = build_artifacts()
    mismatches = []
    for rel, expected in artifacts.items():
        path = ROOT / rel
        actual = path.read_text(encoding="utf-8") if path.exists() else None
        if actual != expected:
            mismatches.append(rel)
    expected_doc_files = {path for path in artifacts if path.startswith("pentas/")}
    actual_doc_files = {p.relative_to(ROOT).as_posix() for p in DOC_ROOT.rglob("*.mdx")} if DOC_ROOT.exists() else set()
    extra = sorted(actual_doc_files - expected_doc_files)
    if mismatches or extra:
        raise SystemExit("Penta portal docs drift: " + ", ".join(sorted(mismatches) + extra))

def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        write_artifacts()
    else:
        check_artifacts()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
