#!/usr/bin/env python3
"""Build CrownThrive's operational Penta knowledge system.

This projection turns the Penta namespace into a shared human + machine operating
manual. It classifies every identity by architectural layer, job/function,
lifecycle stage and audience; emits agent-readable manifests; expands each Penta
guide with deterministic operational/development instructions; and generates
cross-cutting layer/job/lifecycle/audience directories.

Classification is routing/documentation metadata only. This script never creates
maturity, execution eligibility, credentials, provider permission, money/rights
movement, release authority, legal authority, or D3/human-reserved authority.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / "data/penta/namespace-census.v1.json"
TAXONOMY = ROOT / "data/penta/operational-taxonomy.v1.json"
KNOWLEDGE = ROOT / "data/penta/operational-knowledge.v1.json"
AGENT_MANIFEST = ROOT / "data/penta/agent-knowledge.v1.json"
AGENT_JSONL = ROOT / "data/penta/agent-knowledge.v1.jsonl"
DOCS_CONFIG = ROOT / "docs.json"
BEGIN = "<!-- BEGIN PENTA OPERATIONAL KNOWLEDGE v1 -->"
END = "<!-- END PENTA OPERATIONAL KNOWLEDGE v1 -->"
PORTAL_BEGIN = "<!-- BEGIN PENTA OPERATIONAL PORTAL v1 -->"
PORTAL_END = "<!-- END PENTA OPERATIONAL PORTAL v1 -->"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def fm(title: str, description: str, *, page_type: str = "guide", audience: str = "operator") -> str:
    return "\n".join([
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        f"sidebarTitle: {json.dumps(title, ensure_ascii=False)}",
        'standard_version: "1.0.0"',
        f"primary_audience: {json.dumps(audience)}",
        f"page_type: {json.dumps(page_type)}",
        'content_state: "current_with_holds"',
        "---",
        "",
    ])


def link(record: dict[str, Any]) -> str:
    return "/" + str(record["docs_path"])


def taxonomy_indexes(taxonomy: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        key: {str(item["id"]): item for item in taxonomy.get(key, []) if isinstance(item, dict) and item.get("id")}
        for key in ("layers", "jobs", "lifecycle_stages", "audiences")
    }


def classification(record: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    family_id = record.get("family_id")
    defaults = (taxonomy.get("family_defaults") or {}).get(family_id, {}) if family_id else {}
    layers = list(defaults.get("layers") or [])
    jobs = list(defaults.get("jobs") or [])
    provenance = {
        "family": record.get("assignment_state") or "pending_canonicalization",
        "layers": "family_default" if layers else "pending_classification",
        "jobs": "family_default" if jobs else "pending_classification",
        "overlays": [],
    }

    haystack = normalize(" ".join([
        str(record.get("name") or ""),
        str(record.get("canonical_machine_key") or ""),
        str(record.get("role") or ""),
        str(record.get("kind") or ""),
    ]))
    for overlay in taxonomy.get("keyword_overlays", []):
        if not isinstance(overlay, dict):
            continue
        matched = [word for word in overlay.get("match", []) if normalize(word) and normalize(word) in haystack]
        if not matched:
            continue
        layers.extend(str(v) for v in overlay.get("layers", []))
        jobs.extend(str(v) for v in overlay.get("jobs", []))
        provenance["overlays"].append({"matched": matched, "layers": overlay.get("layers", []), "jobs": overlay.get("jobs", [])})

    layers = dedupe(layers)[:5]
    jobs = dedupe(jobs)[:6]
    if provenance["overlays"]:
        provenance["layers"] = "family_plus_docs_inferred" if defaults.get("layers") else "docs_inferred"
        provenance["jobs"] = "family_plus_docs_inferred" if defaults.get("jobs") else "docs_inferred"

    canonical = record.get("namespace_state") == "canonical"
    lifecycle = ["discover", "design", "govern", "evolve"] if not canonical else ["design", "build", "verify", "operate", "observe", "govern", "evolve"]
    if "analyze-research" in jobs:
        lifecycle.insert(0, "discover")
    if canonical and ("publish" in jobs or "test-certify" in jobs or record.get("execution_eligible_by_registry")):
        lifecycle.insert(lifecycle.index("operate"), "release")
    if canonical and "recover" in jobs:
        lifecycle.insert(lifecycle.index("govern"), "recover")
    lifecycle = dedupe(lifecycle)

    audiences = ["agent", "developer", "owner-admin", "auditor"]
    if canonical:
        audiences.insert(2, "operator")
    if canonical and (record.get("operator_route") or record.get("canonical_machine_key")):
        audiences.append("partner-integrator")
    audiences = dedupe(audiences)

    return {
        "layers": layers,
        "jobs": jobs,
        "lifecycle_stages": lifecycle,
        "audiences": audiences,
        "provenance": provenance,
    }


def build_record(record: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    cls = classification(record, taxonomy)
    canonical = record.get("namespace_state") == "canonical"
    executable = bool(record.get("execution_eligible_by_registry")) if canonical else False
    role = record.get("role") or "Role unresolved; use canonicalization/governance evidence before operational use."
    jobs = cls["jobs"]
    routing_actions = [str(j) for j in jobs]
    dependencies = list(record.get("dependencies") or [])
    evidence_paths = list(record.get("evidence_paths") or [])

    use = (
        f"Route work to {record['name']} when the request matches its recorded role ({role}) and one of its job classifications: "
        + (", ".join(jobs) if jobs else "classification pending") + "."
    )
    not_use = (
        "Do not execute this identity independently. It is noncanonical and exists for preservation/canonicalization only."
        if not canonical
        else "Do not use it outside its recorded role, risk ceiling, dependency gates, CHLOM authority, certified bindings, or current readiness state."
    )

    prerequisites = [
        "Resolve this exact identity and current namespace state.",
        "Resolve current authority/consent through CHLOM or the applicable governed authority trace.",
        "Resolve current PentaStatus/readiness and dependency health.",
        "Define the intended evidence/readback target before any material action.",
    ]
    if dependencies:
        prerequisites.append("Verify declared dependencies before execution: " + ", ".join(map(str, dependencies)) + ".")
    if not canonical:
        prerequisites.append("Canonicalize or bind to an existing canonical target before execution.")
    elif executable:
        prerequisites.append("For provider writes, require a certified provider binding, credential reference, idempotency boundary and provider readback.")
    else:
        prerequisites.append("Registry execution eligibility is false; remain read-only/documentation/routing unless a separate canonical change promotes it.")

    forbidden = [
        "manufacture PASS, maturity, production status, credentials or provider permission",
        "manufacture legal, rights, financial, fiduciary, licensing, governance or D3 authority",
        "bypass CHLOM, PentaHybrid, provider certification, exact-head release gates or required human-reserved decisions",
        "treat documentation confidence as provider execution evidence",
        "expose plaintext secrets or sensitive credential values",
    ]
    if not canonical:
        forbidden.insert(0, "perform independent runtime/provider writes from this candidate identity")

    agent_steps = [
        "Match the task to this identity's jobs, layers and role; if confidence is low, route to PentaRoute/PentaSearch/PentaDocs rather than guessing.",
        "Confirm namespace_state=canonical before considering execution; candidates stay fail-closed.",
        "Read execution eligibility, risk ceiling, current readiness, authority trace and dependency health.",
        "Select the narrowest documented interface and preserve idempotency/retry boundaries.",
        "Execute only actions independently authorized by runtime policy; otherwise create a governed handoff/escalation.",
        "Collect provider/system readback and DAIL-compatible evidence for material actions.",
        "Re-read status after execution and route failures to the appropriate observe/recover/govern jobs.",
    ]

    interfaces = {
        "machine_key": record.get("canonical_machine_key"),
        "operator_route": record.get("operator_route"),
        "public_status_route": record.get("public_status_route"),
        "api_mcp_rule": "Use canonical contracts through PentaMCP/PentaRoute; this docs record is a routing/knowledge surface, not an execution proxy.",
    }
    data_contract = {
        "inputs": "Resolve from canonical machine/API/event/data contracts; do not infer undocumented fields.",
        "outputs": "Resolve from canonical machine/API/event/data contracts; require readback/evidence for material outputs.",
        "events": "Resolve from registered PentaEvent/PentaHook/PentaStream contracts where present.",
        "state": "Use institutional source-of-truth state, not page prose, for mutable runtime state.",
        "retention": "Follow the source system, DAIL, privacy, rights and provider-specific retention contract.",
    }

    material = {
        "identity": record.get("name"),
        "namespace_state": record.get("namespace_state"),
        "machine_key": record.get("canonical_machine_key"),
        "family": record.get("family_id"),
        "layers": cls["layers"],
        "jobs": cls["jobs"],
        "lifecycle": cls["lifecycle_stages"],
        "role": role,
    }
    return {
        "identity": record.get("name"),
        "slug": record.get("slug"),
        "docs_path": record.get("docs_path"),
        "namespace_state": record.get("namespace_state"),
        "candidate_class": record.get("candidate_class"),
        "canonical_machine_key": record.get("canonical_machine_key"),
        "canonical_target_name": record.get("canonical_target_name"),
        "family": {"id": record.get("family_id"), "name": record.get("family_name"), "assignment_state": record.get("assignment_state")},
        "role": role,
        "kind": record.get("kind"),
        "maturity": record.get("maturity"),
        "risk_ceiling": record.get("risk_ceiling"),
        "execution_eligible_by_registry": executable,
        "strict_readiness_state": record.get("strict_readiness_state"),
        "layers": cls["layers"],
        "jobs": cls["jobs"],
        "lifecycle_stages": cls["lifecycle_stages"],
        "audiences": cls["audiences"],
        "classification_provenance": cls["provenance"],
        "when_to_use": use,
        "when_not_to_use": not_use,
        "prerequisites": prerequisites,
        "routing_actions": routing_actions,
        "forbidden_actions": forbidden,
        "dependencies": dependencies,
        "interfaces": interfaces,
        "data_contract": data_contract,
        "evidence_paths": evidence_paths,
        "runbooks": [
            "PENTA-PORTAL-STANDARD.md",
            str(record.get("docs_path")) + ".mdx",
            "Use PentaStatus/PentaAssure/DAIL and system-specific incident/release evidence where registered.",
        ],
        "agent_instructions": agent_steps,
        "escalation": "Escalate unresolved authority, provider, readiness, ownership or contract ambiguity to the governed owner/PentaGovernance/PentaAssure lane; do not guess.",
        "freshness": {"taxonomy_date": taxonomy.get("updated"), "schema_version": taxonomy.get("schema_version"), "source": "data/penta/namespace-census.v1.json + data/penta/operational-taxonomy.v1.json"},
        "knowledge_sha256": hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }


def operational_section(k: dict[str, Any], indexes: dict[str, dict[str, dict[str, Any]]]) -> str:
    def refs(ids: list[str], bucket: str, prefix: str) -> str:
        values = []
        for item_id in ids:
            item = indexes[bucket].get(item_id, {"name": item_id})
            values.append(f"[{item['name']}](/pentas/{prefix}/{item_id})")
        return ", ".join(values) if values else "Pending classification"

    layer_refs = refs(k["layers"], "layers", "layers")
    job_refs = refs(k["jobs"], "jobs", "jobs")
    lifecycle_refs = refs(k["lifecycle_stages"], "lifecycle_stages", "lifecycle")
    audience_refs = refs(k["audiences"], "audiences", "audiences")
    deps = ", ".join(f"`{x}`" for x in k["dependencies"]) if k["dependencies"] else "No dependency edges are declared in the current namespace projection."
    evidence = "\n".join(f"- `{x}`" for x in k["evidence_paths"][:20]) if k["evidence_paths"] else "- Resolve evidence through PentaStatus/PentaAssure/DAIL and the canonical system contract."
    prereqs = "\n".join(f"{i}. {x}" for i, x in enumerate(k["prerequisites"], 1))
    forbidden = "\n".join(f"- Never {x}." for x in k["forbidden_actions"])
    agent_steps = "\n".join(f"{i}. {x}" for i, x in enumerate(k["agent_instructions"], 1))
    jobs = ", ".join(f"`{x}`" for x in k["routing_actions"]) or "classification-pending"
    interface = k["interfaces"]
    dc = k["data_contract"]
    return f"""
{BEGIN}

## Operational classification

| Dimension | Assignment |
| --- | --- |
| Architectural layers | {layer_refs} |
| Jobs / functions | {job_refs} |
| Lifecycle stages | {lifecycle_refs} |
| Intended audiences | {audience_refs} |
| Namespace | `{k['namespace_state']}` |
| Registry execution eligible | `{str(bool(k['execution_eligible_by_registry'])).lower()}` |
| Risk ceiling | `{k.get('risk_ceiling') or 'unresolved'}` |
| Strict readiness | `{k.get('strict_readiness_state') or 'unresolved'}` |
| Classification provenance | `{k['classification_provenance'].get('layers')}` / `{k['classification_provenance'].get('jobs')}` |

Layer/job classification is for discovery, routing and documentation. It does not create runtime authority or production status.

## When to use

{k['when_to_use']}

## When not to use

{k['when_not_to_use']}

## Prerequisites

{prereqs}

## Quickstart

1. Start from this exact identity and machine key: `{k.get('canonical_machine_key') or 'NONCANONICAL/UNRESOLVED'}`.
2. Match the request to the documented jobs: {jobs}.
3. Resolve current authority, readiness, dependencies and provider bindings before material execution.
4. Use the narrowest canonical interface; preserve idempotency and bounded retries.
5. Collect readback/evidence and re-check PentaStatus after any material action.
6. On ambiguity or failure, route to the documented observe/recover/govern lanes instead of manufacturing success.

## Developer guide

### Development workflow

1. Read `data/penta/operational-knowledge.v1.json` for the complete operating contract and `data/penta/agent-knowledge.v1.json` for the compact agent routing record.
2. Resolve the canonical implementation and contracts from machine key `{k.get('canonical_machine_key') or 'UNRESOLVED'}` and the evidence paths below.
3. Keep changes inside the role and authority boundary; add explicit contracts rather than relying on prose inference.
4. Add or update focused tests for happy path, denied authority, dependency failure, provider failure, idempotency/retry and evidence/readback behavior.
5. Run repository validation and Penta-specific certification before opening a governed PR.
6. Release only through exact-head governed merge/release lanes; re-read provider/runtime state after deployment.

### Extension rules

- Prefer existing PentaRoute/PentaMCP/PentaEvent/PentaHook contracts over one-off integrations.
- Use structured schemas, explicit versioning and backwards-compatible migration where possible.
- Secrets are references/bindings, never documentation values.
- New authority, money movement, rights, licensing, destructive writes or D3 behavior requires its own canonical governance path.
- A new Penta name must satisfy the PentaScribe/registry/PentaDocs/CrownThrive IO/PentaStatus creation contract before it is treated as institutional.

## Invocation & interfaces

| Interface | Current contract |
| --- | --- |
| Machine key | `{interface.get('machine_key') or 'unresolved'}` |
| Operator route | `{interface.get('operator_route') or 'resolve from canonical registry'}` |
| Public status route | `{interface.get('public_status_route') or 'resolve from canonical registry'}` |
| API / MCP | {interface['api_mcp_rule']} |

Do not invent endpoints, event names, schemas or provider capabilities that are absent from canonical contracts.

## Inputs, outputs, events & state

- **Inputs:** {dc['inputs']}
- **Outputs:** {dc['outputs']}
- **Events:** {dc['events']}
- **State:** {dc['state']}
- **Retention:** {dc['retention']}

## Authority, permissions & non-authorities

Execution eligibility is `{str(bool(k['execution_eligible_by_registry'])).lower()}` from the namespace projection. That flag is necessary but never sufficient for a material provider action; the caller must also satisfy current authority, risk, provider-binding, readiness and evidence gates.

{forbidden}

## Dependencies & handoffs

{deps}

Use family, layer and job directories to find sibling capabilities. Handoffs must preserve task context, authority context, correlation/idempotency keys and evidence lineage.

## Reliability, failure modes & recovery

Treat timeout, dependency degradation, stale evidence, invalid authority, unavailable provider bindings, provider refusal, partial write, duplicate delivery and inconsistent readback as explicit failure states. Fail closed for high-consequence ambiguity. Bounded retry is appropriate only when the underlying operation is retry-safe/idempotent; otherwise reconcile/read back before another write.

## Observability, SLOs & PentaStatus

At minimum expose or resolve: lifecycle/readiness state, last successful readback, dependency health, error/incident state, evidence freshness, release/version identity and accountable owner. Numeric SLO/SLA targets must come from the Penta-specific contract; documentation must not invent them.

## Testing, assurance & production certification

Certification should cover contract/schema validation, authorization denial, dependency failure, idempotency/retry, provider readback, observability, audit/evidence emission, migration/rollback and regression behavior. `DOCUMENTED ≠ TESTED ≠ CERTIFIED ≠ AUTHORIZED ≠ PRODUCTION`.

## Release, migration & rollback

Version software/contracts explicitly. Preserve supersession and migration lineage. Use exact-head PR/release evidence, deploy through the governed release lane, then compare provider/runtime readback to the intended artifact. Rollback must be a documented reversible action or an explicit forward-fix/reconciliation plan.

## Evidence

{evidence}

## Agent ingestion contract

Agents and Pentas should not scrape prose as their primary contract. Consume the machine-readable record keyed by `{k.get('canonical_machine_key') or k['identity']}` from `data/penta/agent-knowledge.v1.json`, then use this page for explanation and examples.

{agent_steps}

### Escalation

{k['escalation']}

## Examples & anti-patterns

**Valid pattern:** identify the Penta from its job/layer, resolve authority/readiness, invoke the canonical contract, collect readback, record evidence, and route the result onward.

**Anti-pattern:** infer that a Penta may write to a provider because its name sounds relevant, because its docs page exists, or because a previous run succeeded.

## Troubleshooting

1. Confirm identity and namespace state.
2. Confirm current registry/readiness rather than cached prose.
3. Confirm dependency health and provider binding.
4. Confirm authority/consent and risk ceiling.
5. Check logs/status/evidence for the first failed boundary.
6. Retry only when safe; otherwise reconcile or escalate.
7. Preserve the failure and recovery receipt in DAIL-compatible evidence.

## Machine-readable knowledge

- Complete knowledge graph projection: `data/penta/operational-knowledge.v1.json`
- Compact agent manifest: `data/penta/agent-knowledge.v1.json`
- Streaming/embedding-friendly records: `data/penta/agent-knowledge.v1.jsonl`
- This record hash: `{k['knowledge_sha256']}`

{END}
"""


def strip_block(text: str, begin: str, end: str) -> str:
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    return pattern.sub("", text).rstrip() + "\n"


def render_taxonomy_hubs(records: list[dict[str, Any]], knowledge: list[dict[str, Any]], taxonomy: dict[str, Any]) -> dict[str, str]:
    indexes = taxonomy_indexes(taxonomy)
    by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_job: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_lifecycle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_audience: dict[str, list[dict[str, Any]]] = defaultdict(list)
    record_by_name = {str(r["name"]): r for r in records}
    for item in knowledge:
        for value in item["layers"]: by_layer[value].append(item)
        for value in item["jobs"]: by_job[value].append(item)
        for value in item["lifecycle_stages"]: by_lifecycle[value].append(item)
        for value in item["audiences"]: by_audience[value].append(item)
    for mapping in (by_layer, by_job, by_lifecycle, by_audience):
        for values in mapping.values(): values.sort(key=lambda x: str(x["identity"]).casefold())

    def identity_table(values: list[dict[str, Any]]) -> str:
        rows = []
        for item in values:
            source = record_by_name.get(str(item["identity"]))
            href = link(source) if source else "/pentas/all"
            rows.append(f'| [{item["identity"]}]({href}) | `{item["namespace_state"]}` | {item["family"].get("name") or "Pending family"} | {", ".join(item["jobs"][:3]) or "pending"} |')
        return "\n".join(rows) or "| _None currently assigned_ | - | - | - |"

    files: dict[str, str] = {}
    files["pentas/operational.mdx"] = fm("Penta Operational Knowledge", "Human and machine operating model for the complete Penta namespace.") + f"""# Penta Operational Knowledge

The PentaDocs portal is a shared operating system for developers, operators, owners, auditors and autonomous Pentas. The same governed projection drives human guides and agent manifests.

| Surface | Count |
| --- | ---: |
| Penta identities | **{len(knowledge)}** |
| Architectural layers | **{len(indexes['layers'])}** |
| Jobs / functions | **{len(indexes['jobs'])}** |
| Lifecycle stages | **{len(indexes['lifecycle_stages'])}** |
| Audiences | **{len(indexes['audiences'])}** |

## Navigate by purpose

- [Architectural layers](/pentas/layers)
- [Jobs & functions](/pentas/jobs)
- [Lifecycle stages](/pentas/lifecycle)
- [Audience guides](/pentas/audiences)
- [Developer guide](/pentas/development)
- [Quickstarts](/pentas/quickstarts)
- [Agent ingestion](/pentas/agents)
- [Integration patterns](/pentas/integrations)
- [Runbooks & incident model](/pentas/runbooks)

Family answers **where the Penta belongs institutionally**. Layer answers **where it sits architecturally**. Job answers **what work it performs**. Lifecycle answers **when it participates**. Audience answers **who consumes the contract**.
"""

    files["pentas/layers.mdx"] = fm("Penta Architectural Layers", "Cross-family architectural layers for the Penta operating system.") + "# Penta Architectural Layers\n\n| Layer | Pentas | Mission |\n| --- | ---: | --- |\n" + "\n".join(
        f'| [{item["name"]}](/pentas/layers/{item["id"]}) | **{len(by_layer[item["id"]])}** | {item["mission"]} |' for item in taxonomy["layers"]
    ) + "\n"
    for item in taxonomy["layers"]:
        files[f'pentas/layers/{item["id"]}.mdx'] = fm(item["name"], item["mission"]) + f"""# {item['name']}

**Mission:** {item['mission']}

Layers are orthogonal to the 15-family topology. Assignment is discovery/routing metadata and never changes child maturity or authority.

| Penta | Namespace | Family | Jobs |
| --- | --- | --- | --- |
{identity_table(by_layer[item['id']])}

## Development use

Use this layer to find architectural peers, shared contracts, expected handoffs, common failure boundaries and reusable integration patterns. Do not assume every Penta in the layer has the same provider permissions or runtime maturity.
"""

    files["pentas/jobs.mdx"] = fm("Penta Jobs & Functions", "Functional job taxonomy for routing work across the Penta ecosystem.") + "# Penta Jobs & Functions\n\n| Job | Pentas | Purpose |\n| --- | ---: | --- |\n" + "\n".join(
        f'| [{item["name"]}](/pentas/jobs/{item["id"]}) | **{len(by_job[item["id"]])}** | {item["description"]} |' for item in taxonomy["jobs"]
    ) + "\n"
    for item in taxonomy["jobs"]:
        files[f'pentas/jobs/{item["id"]}.mdx'] = fm(item["name"], item["description"]) + f"""# {item['name']}

**Job verb:** `{item['verb']}`  
**Purpose:** {item['description']}

Use this directory for task routing. The job identifies what a Penta is suited to do; actual execution still requires canonical identity, current readiness, authority and provider bindings.

| Penta | Namespace | Family | Jobs |
| --- | --- | --- | --- |
{identity_table(by_job[item['id']])}
"""

    files["pentas/lifecycle.mdx"] = fm("Penta Lifecycle", "Lifecycle-stage view of Penta participation.") + "# Penta Lifecycle\n\n| Stage | Pentas | Purpose |\n| --- | ---: | --- |\n" + "\n".join(
        f'| [{item["name"]}](/pentas/lifecycle/{item["id"]}) | **{len(by_lifecycle[item["id"]])}** | {item["description"]} |' for item in taxonomy["lifecycle_stages"]
    ) + "\n"
    for item in taxonomy["lifecycle_stages"]:
        files[f'pentas/lifecycle/{item["id"]}.mdx'] = fm(item["name"], item["description"]) + f"""# {item['name']}

{item['description']}

Lifecycle assignment describes where an identity participates in the operating flywheel; it is not a maturity promotion.

| Penta | Namespace | Family | Jobs |
| --- | --- | --- | --- |
{identity_table(by_lifecycle[item['id']])}
"""

    files["pentas/audiences.mdx"] = fm("Penta Audience Guides", "Audience-specific entry points for PentaDocs.") + "# Penta Audience Guides\n\n| Audience | Pentas | Use |\n| --- | ---: | --- |\n" + "\n".join(
        f'| [{item["name"]}](/pentas/audiences/{item["id"]}) | **{len(by_audience[item["id"]])}** | {item["description"]} |' for item in taxonomy["audiences"]
    ) + "\n"
    for item in taxonomy["audiences"]:
        files[f'pentas/audiences/{item["id"]}.mdx'] = fm(item["name"], item["description"], audience=item["id"]) + f"""# {item['name']}

{item['description']}

| Penta | Namespace | Family | Jobs |
| --- | --- | --- | --- |
{identity_table(by_audience[item['id']])}
"""

    files["pentas/development.mdx"] = fm("Penta Development Guide", "How to build, extend, test and release CrownThrive Penta software.", audience="developer") + """# Penta Development Guide

## Development sequence

1. **Identify** the exact Penta from `/pentas/jobs`, `/pentas/layers` or `/pentas/all`.
2. **Read the machine record** in `data/penta/operational-knowledge.v1.json` and the compact agent record in `data/penta/agent-knowledge.v1.json`.
3. **Resolve canonical contracts** from the machine key and registry/evidence paths; never create undocumented API or provider assumptions.
4. **Model authority first**: CHLOM/PentaHybrid/risk/provider-binding requirements belong in the implementation contract, not tribal knowledge.
5. **Implement with explicit schemas** for inputs, outputs, events, state, idempotency and evidence/readback.
6. **Test denied and degraded paths**, not only happy paths.
7. **Certify and release at exact head**, preserving version, migration, rollback and evidence lineage.
8. **Read back production/provider state** after release before claiming convergence.

## Required test matrix

Every material Penta should have tests for contract/schema validation, authorization denial, dependency outage, provider refusal, timeout, duplicate/idempotent replay, partial failure/reconciliation, logging/status/evidence, migration and rollback/forward-fix.

## New Penta development

New names begin as candidate references. Institutionalization requires PentaScribe terminology, a canonical registry identity, family placement, layer/job classification, PentaDocs guide, CrownThrive IO route, PentaStatus producer contract, ownership/escalation and applicable security/build/certify/release controls.
"""

    files["pentas/quickstarts.mdx"] = fm("Penta Quickstarts", "Common task-routing and execution patterns across the Penta system.") + """# Penta Quickstarts

## Find the right Penta

Start with the [jobs directory](/pentas/jobs) when you know the work, the [layers directory](/pentas/layers) when you know the architectural boundary, or the [A–Z directory](/pentas/all) when you know the name.

## Safe read-only task

1. Match task → job → candidate Pentas.
2. Prefer canonical identities.
3. Resolve current status/evidence.
4. Use a read/query/search interface.
5. Preserve provenance in the returned result.

## Material write task

1. Resolve canonical Penta and machine key.
2. Verify execution eligibility, risk ceiling and current readiness.
3. Resolve CHLOM/consent/authority and certified provider binding.
4. Establish idempotency and expected readback.
5. Execute the narrowest authorized write.
6. Read back provider/runtime state and preserve DAIL-compatible evidence.
7. Route failure to recover/govern instead of retrying blindly.

## Build or change software

Use the [development guide](/pentas/development), then the target Penta page. Exact-head tests/certification and post-release readback are required before production claims.
"""

    files["pentas/agents.mdx"] = fm("Penta Agent Ingestion", "Machine-readable operating contract for CrownThrive agents and Pentas.", audience="agent") + """# Penta Agent Ingestion

Agents should treat the JSON manifests as the primary routing contract and PentaDocs prose as explanatory context.

## Resources

- `data/penta/operational-taxonomy.v1.json` — layer/job/lifecycle/audience taxonomy.
- `data/penta/operational-knowledge.v1.json` — complete per-Penta operating records.
- `data/penta/agent-knowledge.v1.json` — compact machine routing manifest.
- `data/penta/agent-knowledge.v1.jsonl` — one record per line for indexing, embeddings, retrieval and streaming ingestion.

## Agent decision procedure

1. Parse user/system intent into one or more job IDs.
2. Filter candidate Pentas by jobs and architectural layers.
3. Prefer `namespace_state=canonical`.
4. Verify `execution_eligible_by_registry`, readiness, risk and authority before material actions.
5. Respect `forbidden_actions` as hard guardrails.
6. Use `interfaces` and canonical machine contracts; do not invent APIs.
7. Carry dependencies, correlation/idempotency and evidence lineage through handoffs.
8. Collect readback and record the result; never convert missing evidence into PASS.

## Retrieval strategy

Index `identity`, `role`, `layers`, `jobs`, `lifecycle_stages`, `audiences`, `dependencies`, `when_to_use` and `agent_instructions`. Use `knowledge_sha256` to detect stale cached records.
"""

    files["pentas/integrations.mdx"] = fm("Penta Integration Guide", "Interoperability, API/MCP, events, providers and dependency patterns.", audience="developer") + """# Penta Integration Guide

Use canonical PentaRoute/PentaMCP/PentaEvent/PentaHook/PentaStream contracts instead of point-to-point undocumented coupling. Every material integration should define identity, schema/version, authentication/authority, idempotency, timeout/retry policy, failure semantics, readback, observability and evidence lineage.

## Provider boundary

A provider credential or SDK being available does not authorize a write. Certified binding + current authority + readiness + explicit operation scope + evidence/readback are separate gates.

## Handoff envelope

Preserve task/correlation ID, origin identity, target identity, requested job, authority context/reference, dependency assumptions, idempotency key when relevant, expected output/readback and evidence destination.
"""

    files["pentas/runbooks.mdx"] = fm("Penta Runbooks & Incidents", "Common operating, incident, recovery and escalation model.") + """# Penta Runbooks & Incidents

## Standard incident sequence

1. Detect via PentaStatus/telemetry/evidence drift.
2. Identify the first failing dependency/provider/authority boundary.
3. Stop unsafe retries and fail closed for high-consequence ambiguity.
4. Classify whether recovery is retry, reconcile, restore, rollback, forward-fix or external/provider hold.
5. Execute only bounded authorized recovery.
6. Read back state and preserve the incident/recovery receipt.
7. Update status, ownership and follow-up defects.

## Required runbook content

Each production Penta should identify trigger conditions, severity/blast radius, owner/escalation, dependencies, diagnostic evidence, safe actions, forbidden actions, rollback/recovery, provider-specific holds and closure/readback criteria. Missing required runbook material is a readiness/documentation defect.
"""
    return files


def build_navigation(docs: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    tabs = docs.get("navigation", {}).get("tabs", [])
    penta_tab = next((t for t in tabs if isinstance(t, dict) and t.get("tab") == "Pentas"), None)
    if not penta_tab:
        raise ValueError("Pentas navigation tab missing")
    existing = [g for g in penta_tab.get("groups", []) if isinstance(g, dict) and g.get("group") not in {
        "Operational Knowledge", "Architectural Layers", "Jobs & Functions", "Lifecycle Stages", "Audience Guides"
    }]
    operational = {
        "group": "Operational Knowledge",
        "pages": ["pentas/operational", "pentas/development", "pentas/quickstarts", "pentas/agents", "pentas/integrations", "pentas/runbooks", "pentas/layers", "pentas/jobs", "pentas/lifecycle", "pentas/audiences"],
    }
    layers = {"group": "Architectural Layers", "pages": [f'pentas/layers/{x["id"]}' for x in taxonomy["layers"]]}
    jobs = {"group": "Jobs & Functions", "pages": [f'pentas/jobs/{x["id"]}' for x in taxonomy["jobs"]]}
    lifecycle = {"group": "Lifecycle Stages", "pages": [f'pentas/lifecycle/{x["id"]}' for x in taxonomy["lifecycle_stages"]]}
    audiences = {"group": "Audience Guides", "pages": [f'pentas/audiences/{x["id"]}' for x in taxonomy["audiences"]]}
    penta_tab["groups"] = [existing[0], operational, layers, jobs, lifecycle, audiences] + existing[1:] if existing else [operational, layers, jobs, lifecycle, audiences]
    return docs


def load_quality_module():
    path = ROOT / "scripts/pentadocs_quality.py"
    spec = importlib.util.spec_from_file_location("pentadocs_quality_operational", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load PentaDocs quality engine")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    census = load_json(CENSUS)
    taxonomy = load_json(TAXONOMY)
    records = [r for r in census.get("records", []) if isinstance(r, dict)]
    knowledge = [build_record(r, taxonomy) for r in records]
    indexes = taxonomy_indexes(taxonomy)
    valid = {k: set(v) for k, v in ((key, indexes[key].keys()) for key in indexes)}
    for item in knowledge:
        for key, bucket in (("layers", "layers"), ("jobs", "jobs"), ("lifecycle_stages", "lifecycle_stages"), ("audiences", "audiences")):
            unknown = set(item[key]) - valid[bucket]
            if unknown:
                raise ValueError(f"unknown {key} for {item['identity']}: {sorted(unknown)}")
        if item["namespace_state"] == "canonical" and (not item["layers"] or not item["jobs"]):
            raise ValueError(f"canonical identity missing operational classification: {item['identity']}")
        if item["namespace_state"] != "canonical" and item["execution_eligible_by_registry"]:
            raise ValueError(f"candidate execution promotion detected: {item['identity']}")
    manifest = {
        "schema_version": "1.0.0",
        "manifest_id": "crownthrive.penta.agent-knowledge.v1",
        "authority_invariant": taxonomy["authority_invariant"],
        "record_count": len(knowledge),
        "routing_contract": {
            "primary_filters": ["jobs", "layers", "namespace_state", "audiences"],
            "execution_gate": ["namespace_state=canonical", "execution_eligible_by_registry=true", "current readiness", "current authority", "certified provider binding when applicable", "readback/evidence target"],
            "fail_closed": True,
        },
        "records": knowledge,
    }
    full = {
        "schema_version": "1.0.0",
        "registry_id": "crownthrive.penta.operational-knowledge.v1",
        "generated_from": ["data/penta/namespace-census.v1.json", "data/penta/operational-taxonomy.v1.json"],
        "authority_invariant": taxonomy["authority_invariant"],
        "counts": {
            "identities": len(knowledge),
            "canonical": sum(k["namespace_state"] == "canonical" for k in knowledge),
            "noncanonical": sum(k["namespace_state"] != "canonical" for k in knowledge),
            "layers": len(taxonomy["layers"]),
            "jobs": len(taxonomy["jobs"]),
            "lifecycle_stages": len(taxonomy["lifecycle_stages"]),
            "audiences": len(taxonomy["audiences"]),
        },
        "records": knowledge,
    }
    return records, taxonomy, full, manifest["records"]


def apply() -> dict[str, Any]:
    records, taxonomy, full, agent_records = build()
    indexes = taxonomy_indexes(taxonomy)
    dump_json(KNOWLEDGE, full)
    agent_manifest = {
        "schema_version": "1.0.0",
        "manifest_id": "crownthrive.penta.agent-knowledge.v1",
        "authority_invariant": taxonomy["authority_invariant"],
        "record_count": len(agent_records),
        "routing_contract": {
            "primary_filters": ["jobs", "layers", "namespace_state", "audiences"],
            "execution_gate": ["canonical identity", "registry execution eligibility", "current readiness", "current authority", "certified binding", "readback/evidence"],
            "fail_closed": True,
        },
        "records": agent_records,
    }
    dump_json(AGENT_MANIFEST, agent_manifest)
    AGENT_JSONL.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in agent_records), encoding="utf-8")

    by_identity = {str(k["identity"]): k for k in agent_records}
    for record in records:
        path = ROOT / (str(record["docs_path"]) + ".mdx")
        if not path.exists():
            raise ValueError(f"dedicated Penta page missing: {path.relative_to(ROOT)}")
        text = strip_block(path.read_text(encoding="utf-8"), BEGIN, END)
        path.write_text(text.rstrip() + "\n" + operational_section(by_identity[str(record["name"])], indexes), encoding="utf-8")

    hubs = render_taxonomy_hubs(records, agent_records, taxonomy)
    for rel, content in hubs.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    portal = ROOT / "pentas.mdx"
    portal_text = strip_block(portal.read_text(encoding="utf-8"), PORTAL_BEGIN, PORTAL_END)
    portal_text += f"""\n{PORTAL_BEGIN}\n\n## Operational knowledge system\n\nThe portal also supports task-first and architecture-first discovery: [operational knowledge](/pentas/operational), [layers](/pentas/layers), [jobs/functions](/pentas/jobs), [developer guide](/pentas/development), [agent ingestion](/pentas/agents), and [runbooks](/pentas/runbooks). Human pages and machine manifests derive from the same 406-identity namespace projection.\n\n{PORTAL_END}\n"""
    portal.write_text(portal_text, encoding="utf-8")

    docs = build_navigation(load_json(DOCS_CONFIG), taxonomy)
    DOCS_CONFIG.write_text(json.dumps(docs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    quality = load_quality_module()
    receipt = quality.apply_repository(ROOT)
    errors, stats = quality.validate_repository(ROOT)
    if errors:
        raise ValueError("PentaDocs quality failed after operational projection: " + " | ".join(errors[:20]))
    return {"status":"APPLIED","identities":len(agent_records),"layers":len(taxonomy["layers"]),"jobs":len(taxonomy["jobs"]),"quality":receipt,"quality_stats":stats}


def nav_pages(docs: dict[str, Any]) -> list[str]:
    pages: list[str] = []
    for tab in docs.get("navigation", {}).get("tabs", []):
        if not isinstance(tab, dict) or tab.get("tab") != "Pentas":
            continue
        for group in tab.get("groups", []):
            if isinstance(group, dict): pages.extend(str(p) for p in group.get("pages", []) if isinstance(p, str))
    return pages


def check() -> dict[str, Any]:
    records, taxonomy, full_expected, agent_expected = build()
    errors: list[str] = []
    if not KNOWLEDGE.exists() or load_json(KNOWLEDGE) != full_expected:
        errors.append("operational knowledge manifest drift")
    if not AGENT_MANIFEST.exists():
        errors.append("agent manifest missing")
    else:
        actual_agent = load_json(AGENT_MANIFEST)
        if actual_agent.get("records") != agent_expected or actual_agent.get("record_count") != len(agent_expected):
            errors.append("agent manifest drift")
    if not AGENT_JSONL.exists():
        errors.append("agent JSONL missing")
    else:
        lines = [json.loads(line) for line in AGENT_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
        if lines != agent_expected:
            errors.append("agent JSONL drift")

    for record in records:
        path = ROOT / (str(record["docs_path"]) + ".mdx")
        if not path.exists():
            errors.append(f"missing Penta page {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            errors.append(f"operational section multiplicity {path.relative_to(ROOT)}")

    hub_paths = [
        "pentas/operational.mdx", "pentas/layers.mdx", "pentas/jobs.mdx", "pentas/lifecycle.mdx", "pentas/audiences.mdx",
        "pentas/development.mdx", "pentas/quickstarts.mdx", "pentas/agents.mdx", "pentas/integrations.mdx", "pentas/runbooks.mdx",
    ] + [f'pentas/layers/{x["id"]}.mdx' for x in taxonomy["layers"]] + [f'pentas/jobs/{x["id"]}.mdx' for x in taxonomy["jobs"]] + [f'pentas/lifecycle/{x["id"]}.mdx' for x in taxonomy["lifecycle_stages"]] + [f'pentas/audiences/{x["id"]}.mdx' for x in taxonomy["audiences"]]
    for rel in hub_paths:
        if not (ROOT / rel).exists(): errors.append(f"missing operational docs surface {rel}")

    pages = nav_pages(load_json(DOCS_CONFIG))
    for rel in hub_paths:
        nav = rel[:-4]
        if pages.count(nav) != 1: errors.append(f"operational navigation multiplicity {nav}={pages.count(nav)}")
    for item in agent_expected:
        if item["namespace_state"] == "canonical" and (not item["layers"] or not item["jobs"]):
            errors.append(f"canonical missing classification {item['identity']}")
        if item["namespace_state"] != "canonical" and item["execution_eligible_by_registry"]:
            errors.append(f"candidate authority promotion {item['identity']}")

    quality = load_quality_module()
    q_errors, q_stats = quality.validate_repository(ROOT)
    errors.extend(f"PentaDocs: {x}" for x in q_errors)
    if errors:
        raise SystemExit("Penta operational knowledge drift:\n" + "\n".join(errors[:100]))
    return {"status":"PASS","identities":len(agent_expected),"layers":len(taxonomy["layers"]),"jobs":len(taxonomy["jobs"]),"quality_stats":q_stats}


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = apply() if args.apply else check()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
