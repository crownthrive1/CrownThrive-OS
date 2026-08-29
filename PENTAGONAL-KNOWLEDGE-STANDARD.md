# Pentagonal Knowledge & Penta Reference Standard

**Standard ID:** `ct.standard.penta.pentagonal-knowledge.v1`  
**Version:** `1.0.0`  
**Applies to:** CrownThrive OS Penta doctrine, PentaDocs reference surfaces, machine-ingestion records, developer/operator guides, and the Pentagonal paper series  
**Authority ceiling:** documentation, terminology, architecture reference, discovery and routing metadata only

## 1. Purpose

This standard defines the governed reference model for explaining what a **Penta** is, how the **Pentagonal Architecture** is organized, how humans and agents discover the correct Penta, and how terminology, dictionaries, indexes, papers and machine-ingestion records remain synchronized with canonical CrownThrive OS sources.

It supplements `PENTA-PORTAL-STANDARD.md`. It does not replace CHLOM, DAIL, CIE, PentaStatus, provider evidence, canonical registries, runtime contracts, release evidence, applicable law, rights records or reserved human authority.

## 2. Canonical Penta definition

A **Penta** is a stable, named, contract-bounded institutional capability in PentaOS.

A Penta may be implemented as a:

- deterministic service;
- control or governance boundary;
- registry or knowledge component;
- agent or agent layer;
- workflow/state machine;
- tool, skill or script package;
- API/MCP/event/transport adapter;
- factory/build/release component;
- observability, evidence or continuity component;
- provider-backed capability; or
- governed composite of bounded components.

A Penta is **not synonymous with an LLM or autonomous agent**. Agentic execution is one implementation form.

A Penta name does not itself grant runtime maturity, execution eligibility, credentials, provider permission, legal authority, rights authority, financial authority, release authority, certification, production status or D3/human-reserved authority.

## 3. Pentagonal Architecture

The canonical Penta component registry already declares five foundational axes:

1. **Truth** — identity, architecture, contracts, schemas, semantics, provenance and verified state representations.
2. **Authority** — decision rights, policy, consent, rights, security, legal/economic/risk bounds and capability constraints.
3. **Execution** — bounded work performed by software, agents, workflows, factories, tools, models and operational services.
4. **Interoperation** — routing, protocols, bindings, transports, events, adapters, dependency contracts and governed handoffs.
5. **Continuity** — evidence, lineage, reconciliation, recovery, supersession, succession, history and exact-baseline inheritance.

These axes are architectural responsibility boundaries. Axis membership never creates permission, readiness, certification or production state.

### Five-question architecture test

Every material Penta design should answer:

- **Truth:** What is the governing identity/contract/state assertion?
- **Authority:** Who or what may decide or act, in what exact scope?
- **Execution:** What performs the bounded work?
- **Interoperation:** How do bounded components exchange work/data/events/evidence?
- **Continuity:** How will evidence, history, recovery, reconciliation and succession survive?

An unanswered high-consequence question is an explicit HOLD or architecture defect.

## 4. Orthogonal operating coordinates

Pentagonal axes do not replace the operational taxonomy. Each Penta is also discoverable through independent coordinates:

- **Family** — institutional home.
- **Architectural layer** — technical/operational stack placement.
- **Job/function** — normalized work class for task routing.
- **Lifecycle stage** — when the Penta participates.
- **Audience** — who consumes/operates the contract.

Required invariant:

> Family is not layer. Layer is not job. Job is not lifecycle. Audience is not authority. Pentagonal axis is not production state.

Classification provenance must remain visible when assignments are inferred, family-derived, registry-backed or pending.

## 5. Minimum Penta anatomy

A mature Penta record should resolve, proportionate to the capability:

1. stable identity;
2. canonical machine key;
3. charter/role;
4. scope and explicit non-authorities;
5. family;
6. applicable Pentagonal axis where registered;
7. architectural layer(s);
8. job/function(s);
9. lifecycle participation;
10. audiences;
11. versioned interfaces/contracts;
12. input/output/event/state/data semantics;
13. authority and risk boundaries;
14. dependency graph;
15. provider bindings where applicable;
16. security/privacy/rights/economic constraints;
17. readiness and PentaStatus contract;
18. observability and evidence freshness;
19. retry/idempotency/reconciliation semantics;
20. incident/recovery/rollback or forward-fix path;
21. DAIL-compatible evidence/readback path;
22. owner/escalation;
23. version/migration/deprecation/supersession rules;
24. machine-ingestion record; and
25. human documentation/reference.

Missing fields remain explicit rather than being invented from naming conventions.

## 6. Identity and canonicalization

A newly discovered `Penta*` name is not automatically canonical.

Noncanonical/candidate identities are preserved so history and discovery are not lost, but they remain fail-closed for independent runtime/provider writes. A governed disposition may later classify a candidate as:

- a distinct canonical Penta;
- an alias;
- a primitive;
- a subcomponent;
- a compatibility name;
- a superseded/retired reference; or
- another governed classification.

Stable institutional identity survives display-name, provider, route, environment and version changes.

## 7. State-separation invariant

The following must never be collapsed:

`DOCUMENTED ≠ ROUTABLE ≠ EXECUTION-ELIGIBLE ≠ AUTHORIZED ≠ TESTED ≠ CERTIFIED ≠ RELEASED ≠ PRODUCTION`

Likewise, institutional phase, component version, lifecycle, implementation state, readiness, evidence level, provider-write scope, legal/rights state, economic state, deployment and documentation state remain independently represented.

A rendered page proves that a page rendered. A successful provider request proves that exact request/response. A merged PR proves source acceptance. None of these events silently proves every other state dimension.

## 8. Terminology system

PentaScribe is the canonical semantic-continuity component for terminology discovery and glossary/dictionary/index/FAQ compilation.

The Pentagonal reference suite SHALL provide:

- **Glossary** — concise foundational human definitions.
- **Dictionary** — complete generated terminology records with aliases, class, definition, related terms, source references, machine rule and record hash.
- **Deep Index** — cross-index across Penta namespace, axes, families, layers, jobs, lifecycle, audiences, terminology and papers.
- **FAQ** — common conceptual and operational distinctions.
- **Paper Series** — durable doctrine/architecture/engineering references.
- **Machine manifest** — structured reference source for agents.
- **JSONL** — indexing/RAG/streaming-friendly reference records.

Aliases and superseded terminology must be preserved; terminology updates must not silently rewrite historical meaning.

## 9. Paper suite

The version-1 Pentagonal Paper Series SHALL include at least:

1. Penta Doctrine;
2. Pentagonal Architecture;
3. Penta Identity & Namespace;
4. Penta Authority, Evidence & State;
5. Penta Development Contract;
6. Penta Agent Ingestion & Routing;
7. Penta Interoperation & Handoffs;
8. Penta Lifecycle, Reliability & Recovery;
9. Penta Documentation & Semantic Continuity; and
10. Penta Operating Model.

Each paper must state its thesis, bounded implications, machine/implementation consequences and links back to governing machine/reference records.

Papers are architectural/documentation references, not substitutes for live runtime/authority/provider evidence.

## 10. Developer boot sequence

Before material Penta development:

1. read Pentagonal Architecture and Penta Anatomy;
2. identify the correct canonical Penta through job/layer/family discovery;
3. load the target operational machine record;
4. inspect canonical source contracts and dependency topology;
5. resolve authority, security, rights/privacy/economic and provider constraints;
6. define versioned inputs/outputs/events/errors/state/idempotency/evidence/rollback contracts;
7. test happy, denied and degraded paths;
8. certify/release at the exact tested head/artifact;
9. perform post-deployment/provider readback; and
10. reconcile docs/manifests/status with the released reality.

One-off undocumented point-to-point integrations should be replaced by governed PentaRoute/PentaMCP/PentaEvent/PentaHook/PentaStream/PentaBind contracts where applicable.

## 11. Agent ingestion contract

Agents and Pentas must not use prose scraping as their primary routing contract.

Required read order:

1. `data/penta/pentagonal-reference.v1.json`;
2. `data/penta/agent-knowledge.v1.json`;
3. target-specific canonical machine/API/MCP/event/data contract;
4. current PentaStatus/readiness;
5. current authority trace;
6. dependency health;
7. applicable provider binding;
8. idempotency/retry policy; and
9. expected readback/evidence destination.

### Agent routing algorithm

1. normalize intent into job/function IDs;
2. use layer/family filters where useful;
3. prefer canonical identities;
4. reject noncanonical independent execution;
5. verify execution eligibility;
6. verify readiness/authority/dependencies/bindings;
7. choose the narrowest canonical interface;
8. preserve correlation, authority and evidence context;
9. execute only bounded authorized actions;
10. read back actual state; and
11. route ambiguity/failure to docs/search/govern/observe/recover rather than guessing.

## 12. Handoff envelope

Cross-Penta handoffs should preserve:

- task/correlation ID;
- origin identity;
- target identity;
- requested job;
- authority reference/context;
- risk/data classification as applicable;
- dependency assumptions;
- idempotency/replay context;
- expected output/readback;
- evidence destination;
- originating version/contract context; and
- escalation/timeout semantics.

Transport capability is not authority.

## 13. Evidence and readback

Material actions require bounded evidence. Evidence should identify:

- subject;
- assertion;
- scope/environment;
- timestamp/effective period;
- source/provider;
- actor/authority context;
- request/action identity;
- target result/readback;
- correlation/idempotency context; and
- evidence/DAIL location where applicable.

Ambiguous material writes must be read back/reconciled before blind retry unless idempotency/replay safety is explicitly proven.

## 14. Reliability and continuity

Every production-capable Penta should identify:

- timeout semantics;
- retry policy;
- idempotency model;
- dependency failure behavior;
- provider refusal behavior;
- stale-evidence behavior;
- partial-write handling;
- reconciliation path;
- rollback/forward-fix path;
- incident severity/blast-radius model;
- recovery owner/escalation;
- evidence/closure criteria; and
- continuity/supersession rules.

Fail closed when authority, evidence, security, rights, critical dependency, recovery or rollback predicates are missing for a consequential action.

## 15. Machine reference schema

`data/penta/pentagonal-reference.v1.json` is the generated semantic/architecture reference manifest.

It must include at minimum:

- canonical Penta definition;
- five Pentagonal axes and registered core components;
- operating dimensions;
- agent ingestion contract;
- terminology records;
- paper registry;
- reference routes;
- counts; and
- manifest hash.

Every terminology record should include:

- term;
- slug;
- class;
- definition;
- aliases;
- related terms;
- machine/operating rule;
- source references; and
- deterministic record hash.

`data/penta/pentagonal-reference.v1.jsonl` provides one term/paper record per line for retrieval/indexing/streaming use.

## 16. Generated PentaDocs routes

The Pentagonal reference generator maintains:

- `/pentas/pentagonal`
- `/pentas/anatomy`
- `/pentas/axes`
- `/pentas/axes/{truth|authority|execution|interoperation|continuity}`
- `/pentas/glossary`
- `/pentas/dictionary`
- `/pentas/index`
- `/pentas/faq`
- `/pentas/papers`
- `/pentas/papers/{paper-id}`

It also injects deterministic read-order blocks into:

- `/pentas`
- `/pentas/development`
- `/pentas/agents`

## 17. Validation and generation

The deterministic generator is:

`python scripts/pentagonal_reference_suite.py --apply`

The fail-closed verification command is:

`python scripts/pentagonal_reference_suite.py --check`

The PentaDocs workflow must run the generator before final documentation validation, run its test suite, and include its generated manifest/JSONL/pages/profile/navigation changes in the deterministic projection commit.

## 18. Source precedence

This standard is downstream from the controlling source hierarchy.

If this document conflicts with a more authoritative current governing record, the governing record controls and this reference suite must be reconciled. A stale dictionary or paper is documentation drift; it is not an excuse to overwrite canonical reality.

## 19. Completion criteria

The Pentagonal reference suite is converged only when:

- all five registry axes match the reference manifest;
- the Penta definition is machine and human accessible;
- glossary and dictionary are generated from current sources;
- deep index includes the current Penta namespace;
- all required papers exist;
- agent and developer read orders are wired;
- every reference route appears exactly once in PentaDocs navigation;
- JSON and JSONL are deterministic;
- current manifest hashes appear in generated reference pages;
- PentaDocs quality validation passes; and
- repository tests and exact-source validation pass.

A passing documentation suite certifies documentation consistency only. It does not independently certify runtime, deployment, provider, security, legal, rights, financial or production state.
