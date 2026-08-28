# CrownThrive OS — Pentagonal Full Suite Specification

**Specification ID:** `ct.spec.penta.pentagonal-full-suite.v1`  
**Status:** governed documentation/development specification  
**Scope:** Penta architecture, documentation, agent ingestion, developer/operator guidance, paper corpus, glossary/dictionary/index, lifecycle/runbooks, and future Penta creation requirements  
**Authority ceiling:** documentation, architecture, discovery, routing, development requirements, and knowledge-ingestion semantics only

## 1. Purpose

The **Pentagonal Full Suite** is the complete human-and-machine knowledge layer for CrownThrive OS Penta architecture. It exists so a developer, operator, auditor, approved integrator, autonomous agent, or Penta can answer the same core questions from the same governed source set:

1. What is this Penta?
2. Where does it belong?
3. What jobs does it perform?
4. When should it be used?
5. When must it not be used?
6. What are its inputs, outputs, events, state, and dependencies?
7. What authority is required before execution?
8. How is it invoked safely?
9. How is success verified?
10. What evidence is emitted?
11. How does it fail, retry, reconcile, recover, migrate, and supersede?
12. Which human or machine consumer should read which contract first?

The Full Suite is not a second source of truth. It is a governed projection and ingestion layer derived from canonical registries, contracts, operational knowledge, PentaStatus/readiness, CHLOM authority, DAIL evidence, provider bindings, source code, release state, and applicable institutional records.

## 2. What a Penta is

A **Penta** is a stable, named, contract-bounded institutional capability in PentaOS. A Penta may be deterministic software, a control boundary, a registry, a workflow, an agentic capability, an event/API/MCP adapter, a build/release component, an evidence/observability component, or a governed composite.

A Penta is not automatically an AI agent. It is not automatically executable. It is not automatically authorized. It is not automatically production.

Required state-separation invariant:

`DOCUMENTED ≠ DISCOVERABLE ≠ ROUTABLE ≠ EXECUTION-ELIGIBLE ≠ AUTHORIZED ≠ TESTED ≠ CERTIFIED ≠ RELEASED ≠ PRODUCTION`

## 3. The Pentagonal Architecture

Every material capability is evaluated through five architectural responsibilities:

- **Truth** — identity, contracts, schemas, semantics, provenance, canonical state, and verified assertions.
- **Authority** — policy, rights, consent, permissions, security, legal/economic bounds, risk ceilings, and reserved human authority.
- **Execution** — bounded work performed by services, workflows, agents, factories, tools, models, and runtime components.
- **Interoperation** — routes, APIs, MCP, queues, events, webhooks, streams, bindings, adapters, handoffs, and dependency contracts.
- **Continuity** — evidence, lineage, reconciliation, recovery, rollback/forward-fix, backup, supersession, succession, history, and exact-baseline inheritance.

### Five-question design test

Every new or materially changed Penta must answer:

1. **Truth:** What exact identity, contract, schema, and state assertion governs this capability?
2. **Authority:** Who or what may act, under what grant, risk class, environment, and scope?
3. **Execution:** What component performs the work and what are its bounded side effects?
4. **Interoperation:** How does the Penta receive work and hand results/evidence to other components?
5. **Continuity:** How are history, evidence, retries, reconciliation, recovery, migration, and succession preserved?

Unresolved high-consequence answers are explicit HOLDs.

## 4. Orthogonal operating dimensions

Pentagonal axes are foundational responsibilities. They do not replace operational classification.

Each Penta is also classified by:

- **Family:** institutional home.
- **Layer:** architectural/technical placement.
- **Job/function:** normalized work class.
- **Lifecycle stage:** when it participates.
- **Audience:** who consumes the contract.
- **Namespace state:** canonical, candidate, alias, superseded, retired, or other governed disposition.
- **Maturity/readiness:** current evidence-backed operating state.
- **Risk/authority class:** consequence and permission boundary.

Required distinction:

`axis != family != layer != job != lifecycle != audience != authority != maturity`

## 5. Documentation anatomy required for every Penta

Every canonical Penta guide should carry, proportionate to its function:

### Identity and purpose

- canonical name;
- machine key/stable identity;
- role/charter;
- scope;
- explicit non-authorities;
- aliases, predecessors, successors, and supersession links;
- family and Pentagonal axis context;
- layer(s), job(s), lifecycle stages, and audiences.

### Usage

- when to use;
- when not to use;
- prerequisites;
- quickstart;
- common tasks;
- example invocations;
- anti-patterns;
- troubleshooting decision tree.

### Development

- source locations;
- canonical contracts;
- API/MCP/event/queue/webhook/stream interfaces;
- input/output/error schemas;
- state machine;
- persistence and retention;
- dependency topology;
- provider bindings;
- feature flags/configuration;
- versioning/compatibility/migration rules;
- extension rules;
- local/dev/test workflow.

### Authority and safety

- authentication/authorization model;
- CHLOM/current authority references;
- privacy/data classification;
- rights/licensing constraints;
- economic/payment authority where applicable;
- D3/human-reserved boundaries;
- prohibited actions;
- escalation requirements.

### Reliability and operations

- SLO/SLA/KPI definitions where applicable;
- PentaStatus/readiness contract;
- health and dependency checks;
- timeout semantics;
- retry policy;
- idempotency/replay semantics;
- duplicate handling;
- partial-write handling;
- reconciliation;
- incident classification;
- rollback/forward-fix;
- backup/restore/continuity;
- recovery closure criteria.

### Assurance and release

- test matrix;
- denied/degraded-path tests;
- integration/provider verification;
- certification criteria;
- exact-head/release evidence;
- deployment procedure;
- post-deployment readback;
- documentation/manifest reconciliation.

### Evidence

- required receipts;
- correlation/task IDs;
- evidence destination;
- DAIL-compatible record expectations;
- readback semantics;
- evidence freshness;
- correction/supersession rules.

### Ownership

- owner/operator;
- escalation path;
- incident owner;
- documentation owner;
- deprecation/migration owner.

## 6. Layer-and-job discovery model

A Penta should never be chosen solely because its name sounds relevant. Task routing should begin with normalized work intent.

### Layer-first discovery

Use architectural layers to answer: **where in the stack does this work belong?** Examples include governance/control, identity/security, orchestration, data/knowledge, interoperability/integration, execution/runtime, build/release, observability/assurance, economic/commercial, media/content, continuity/recovery, and experience/application surfaces as defined by the current taxonomy.

### Job-first discovery

Use jobs/functions to answer: **what work must be done?** Jobs may include discover, search, classify, govern, authorize, authenticate, route, fetch, parse, build, test, certify, deploy, operate, observe, reconcile, recover, document, release, settle, or other normalized current taxonomy jobs.

### Routing order

`intent → job(s) → layer(s) → family/context → canonical identity → eligibility → readiness → authority → dependencies/bindings → interface → execution → readback/evidence`

Candidates and unresolved names may assist discovery but remain fail-closed for independent material execution.

## 7. Human read paths

### Developer path

1. Pentagonal Architecture.
2. Penta Anatomy.
3. Target layer/job/family pages.
4. Target canonical Penta guide.
5. Development Contract paper.
6. Interoperation/Handoffs paper.
7. Target source contracts and code.
8. Current authority/readiness/provider evidence.
9. Tests, release, readback, documentation reconciliation.

### Operator path

1. Penta Operating Model.
2. Target Penta guide.
3. Authority/Evidence/State paper.
4. Runbook.
5. Current PentaStatus/readiness/dependency state.
6. Incident/recovery procedure.
7. Evidence/closure requirements.

### Auditor/governance path

1. Penta Doctrine.
2. Authority/Evidence/State.
3. Namespace/identity history.
4. Current canonical source and authority trail.
5. DAIL/readback evidence.
6. Exact-head/release and provider evidence where relevant.
7. Supersession/correction lineage.

## 8. Agent and Penta ingestion contract

Agents must not scrape prose as their primary execution-routing method.

### Required boot order

1. `data/penta/pentagonal-reference.v1.json`.
2. `data/penta/agent-knowledge.v1.json`.
3. `data/penta/operational-knowledge.v1.json` target record.
4. target canonical API/MCP/event/data/state contract.
5. current PentaStatus/readiness.
6. current CHLOM/authority trace.
7. dependency health.
8. applicable provider binding.
9. idempotency/retry policy.
10. expected result/readback/evidence destination.

### Required agent decision procedure

1. Normalize user/system intent into one or more job IDs.
2. Filter candidate targets by layer and family where useful.
3. Prefer canonical identities.
4. Reject independent execution for unresolved candidate identities.
5. Resolve target execution eligibility.
6. Resolve current readiness and dependency health.
7. Resolve current authority and consequence class.
8. Resolve provider binding/environment and credential reference where applicable.
9. Select the narrowest canonical interface.
10. Preserve correlation, authority, dependency, version, and evidence context.
11. Execute only bounded authorized work.
12. Read back actual target/provider state.
13. Emit evidence/receipts.
14. Reconcile ambiguity before unsafe retry.
15. Route unresolved conditions to document/search/govern/observe/recover rather than inventing facts.

## 9. Machine record minimum schema

Each Penta machine record should expose:

- `identity`;
- `machine_key`;
- `namespace_state`;
- `canonical_target` where applicable;
- `family`;
- `pentagonal_axes` where registered/applicable;
- `layers`;
- `jobs`;
- `lifecycle_stages`;
- `audiences`;
- `classification_provenance`;
- `role`;
- `scope`;
- `non_authorities`;
- `when_to_use`;
- `when_not_to_use`;
- `prerequisites`;
- `routing_actions`;
- `forbidden_actions`;
- `dependencies`;
- `interfaces`;
- `data_contracts`;
- `authority_requirements`;
- `provider_bindings`;
- `readiness_projection`;
- `execution_eligibility_projection`;
- `risk_projection`;
- `reliability_contract`;
- `observability_contract`;
- `evidence_contract`;
- `runbooks`;
- `tests`;
- `release_contract`;
- `agent_instructions`;
- `escalation`;
- `freshness`;
- `source_refs`;
- deterministic record hash.

Unknown fields remain explicit and unresolved. They are never invented from names.

## 10. Glossary, dictionary, ontology, and index suite

### Glossary

The glossary is concise and human-oriented. It explains the foundational language required to safely understand Penta architecture.

### Dictionary

The dictionary is the complete term registry. Each term record should carry:

- canonical term;
- slug;
- class;
- definition;
- aliases;
- deprecated/superseded names;
- related terms;
- machine rule;
- source references;
- record hash.

### Ontology

The ontology defines machine-meaningful relationships such as:

- `PENTA_BELONGS_TO_FAMILY`;
- `PENTA_HAS_AXIS`;
- `PENTA_OCCUPIES_LAYER`;
- `PENTA_PERFORMS_JOB`;
- `PENTA_PARTICIPATES_IN_LIFECYCLE`;
- `PENTA_SERVES_AUDIENCE`;
- `PENTA_DEPENDS_ON`;
- `PENTA_HANDS_OFF_TO`;
- `PENTA_SUPERSEDES`;
- `PENTA_ALIASES`;
- `PENTA_REQUIRES_AUTHORITY`;
- `PENTA_USES_PROVIDER_BINDING`;
- `PENTA_EMITS_EVIDENCE_TO`;
- `TERM_ALIASES_TERM`;
- `TERM_SUPERSEDES_TERM`;
- `PAPER_GOVERNS_TOPIC`.

### Deep index

The deep index cross-links:

- every Penta identity;
- all families;
- all layers;
- all jobs;
- all lifecycle stages;
- all audiences;
- all Pentagonal axes;
- all glossary/dictionary terms;
- all papers;
- all runbooks;
- all quickstarts;
- all canonical contracts;
- aliases, candidates, superseded, and retired names.

## 11. Full Pentagonal Paper Library

The first ten papers remain the minimum core. The **Full Suite** expands the paper family so the architecture can be taught, developed, operated, audited, and inherited without relying on oral knowledge.

### Core doctrine and architecture

1. **Penta Doctrine** — what a Penta is and is not.
2. **Pentagonal Architecture** — Truth, Authority, Execution, Interoperation, Continuity.
3. **Penta Identity & Namespace** — canonical identity, candidates, aliases, supersession.
4. **Penta Authority, Evidence & State** — state separation and proof boundaries.
5. **Penta Operating Model** — discover → prepare → execute → verify → recover/evolve.

### Engineering and development

6. **Penta Development Contract** — engineering requirements for every Penta.
7. **Penta Interface & Contract Design** — APIs, MCP, events, schemas, errors, versioning.
8. **Penta Interoperation & Handoffs** — routing, queues, events, transport and context preservation.
9. **Penta Data & State Semantics** — persistence, state machines, retention, consistency.
10. **Penta Dependency & Provider Binding** — dependency graph and provider abstraction.
11. **Penta Testing & Certification** — happy, denied, degraded, chaos, provider, and exact-head evidence.
12. **Penta Release, Migration & Supersession** — versions, deployment, rollback, migration, archival continuity.
13. **Penta Build/Factory Pattern** — PentaFactory/PentaBuild-style repeatable production-grade generation.

### Agentic and autonomous operation

14. **Penta Agent Ingestion & Routing** — deterministic machine discovery and safe target selection.
15. **Penta Agent Execution Boundary** — capability versus authority, D3 and human-reserved actions.
16. **Penta Multi-Agent Handoff Protocol** — context, correlation, evidence and responsibility transfer.
17. **Penta Memory, Context & Institutional Awareness** — what agents may remember, retrieve, and revalidate.
18. **Penta Self-Healing & Autonomous Recovery** — observe, classify, repair, verify, escalate.

### Reliability, security, governance, and evidence

19. **Penta Lifecycle, Reliability & Recovery** — SLOs, retry, reconciliation, recovery, closure.
20. **Penta Observability & PentaStatus** — telemetry, health, evidence freshness, institutional state.
21. **Penta Security, Identity & Credential Boundaries** — authentication, authorization, secrets, least privilege.
22. **Penta Governance & CHLOM Integration** — grants, consequence classes, consent, rights, economic authority.
23. **Penta Evidence, DAIL & Readback** — receipts, lineage, provider readback and bounded proof.
24. **Penta Incident & Blast-Radius Management** — severity, containment, fail-closed response, restoration.
25. **Penta Continuity, Backup & Succession** — inheritable baselines, continuity, supersession, recovery.

### Knowledge, documentation, and ecosystem adoption

26. **Penta Documentation & Semantic Continuity** — PentaScribe/PentaDocs doctrine.
27. **Penta Glossary, Dictionary & Ontology** — governed terminology and machine semantics.
28. **Penta Developer Onboarding** — how a new engineer enters the architecture safely.
29. **Penta Operator Handbook** — repeatable operating procedures.
30. **Penta Auditor & Assurance Handbook** — evidence-first verification.
31. **Penta Partner/Integrator Handbook** — safe external integration without authority leakage.
32. **Penta Quickstart Pattern Library** — common end-to-end tasks by job and layer.
33. **Penta Anti-Patterns & Failure Modes** — dangerous shortcuts and architecture smells.
34. **Penta Architecture Decision Records** — durable ADR conventions and rationale lineage.
35. **Penta Ecosystem Evolution & Seven-Generation Continuity** — preserving meaning and operability across long-lived change.

Every paper must include:

- thesis;
- scope/non-scope;
- governing definitions;
- architecture implications;
- developer implications;
- operator implications;
- agent/machine implications;
- authority/safety implications;
- implementation consequences;
- examples;
- anti-patterns;
- validation criteria;
- source references;
- related papers;
- version/supersession metadata.

## 12. Required development wiring

Documentation is part of implementation completion.

A new canonical Penta is not considered documentation-complete until the implementation pipeline has produced or reconciled:

1. canonical registry identity;
2. family classification;
3. layer classification;
4. job classification;
5. lifecycle classification;
6. audience classification;
7. PentaDocs guide;
8. operational machine record;
9. agent routing record;
10. glossary/dictionary terms or aliases where needed;
11. deep-index entries;
12. source/interface references;
13. tests/runbook/release references;
14. PentaStatus/readiness contract;
15. owner/escalation metadata;
16. deterministic hashes/freshness metadata.

CI should fail closed on canonical identity drift, missing generated documentation, missing machine records, unknown taxonomy IDs, duplicate routes, missing navigation, stale hashes, or invalid references.

## 13. New-Penta creation workflow

`discover/request → candidate identity → canonicalization/governance → registry → taxonomy classification → contracts/code → tests → docs + machine records → certification/release → provider/runtime readback → PentaStatus + DAIL → documentation reconciliation`

No name should bypass candidate/canonicalization simply because it begins with `Penta`.

## 14. Documentation-as-code rules

- Generated documentation must be deterministic.
- Human and machine outputs derive from common registries/taxonomies.
- Machine manifests are primary for routing; prose is explanatory.
- Generated pages carry source/hash/freshness metadata.
- Historical names remain traceable.
- Corrections use preserve + supersede + reconcile.
- Documentation cannot manufacture authority or production state.
- CI validates links, navigation, schema, counts, hashes, and minimum required sections.
- Source precedence remains explicit.

## 15. Runbook pattern

Every operational runbook should provide:

1. trigger/condition;
2. affected Penta(s);
3. severity/risk class;
4. required authority;
5. preflight checks;
6. exact commands/interfaces/actions;
7. idempotency/retry warnings;
8. expected readback;
9. evidence to capture;
10. failure branches;
11. rollback/forward-fix;
12. escalation;
13. closure criteria;
14. follow-up documentation/status reconciliation.

## 16. Quickstart pattern

Every quickstart should explicitly state:

- goal;
- target job;
- target layer;
- canonical Penta;
- prerequisites;
- authority required;
- interface;
- minimal example;
- expected output;
- expected evidence;
- failure path;
- next related guide.

## 17. Anti-patterns

The following are architecture defects unless explicitly governed:

- choosing Pentas by name similarity alone;
- treating a candidate as canonical;
- scraping prose to authorize execution;
- using provider credentials as proof of permission;
- assuming transport reachability means authority;
- blind retry of ambiguous writes;
- undocumented point-to-point integrations;
- conflating test success with certification;
- conflating merge with deployment;
- conflating deployment with provider readback;
- conflating documentation with production;
- deleting superseded history;
- allowing aliases to multiply authority;
- generating docs from stale projections instead of canonical sources;
- omitting denied/degraded-path tests;
- omitting recovery/evidence semantics from production-capable Pentas.

## 18. Full-suite completion gate

The Full Suite is considered converged only when:

- the five Pentagonal axes match the canonical registry;
- every canonical Penta has a generated guide and machine record;
- layer/job/lifecycle/audience classification is complete or explicitly unresolved with provenance;
- candidate/noncanonical identities remain fail-closed;
- glossary/dictionary/index are deterministic and source-linked;
- all core papers exist;
- the expanded paper library has governed registry entries and generation support;
- developer/operator/agent read paths are wired;
- CI validates deterministic regeneration;
- PentaStatus can detect documentation/manifest drift;
- exact source references and hashes are preserved;
- source precedence and authority boundaries remain explicit.

A passing Full Suite certifies documentation and ingestion consistency only. It does not independently certify runtime, deployment, provider, financial, legal, rights, security, or production state.
