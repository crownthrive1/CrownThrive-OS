# PENTA Family Registry & Institutional Standard

**Status:** Canonical institutional standard  
**Owner:** CrownThrive, LLC  
**Control plane:** CrownThrive IO  
**Documentation plane:** PentaDocs  
**Applies to:** Every CrownThrive system, agent, service, protocol, primitive, or institutional component bearing the Penta name.

## Institutional rule

A Penta is not a nickname, loose feature, or undocumented agent. A named Penta is a first-class CrownThrive institutional subsystem and SHALL have:

1. a canonical registry identity and unambiguous mission;
2. a dedicated CrownThrive IO portal route;
3. an operating charter and comprehensive PentaDocs guide;
4. owner/admin/user/runbook/API/security/status/release documentation as applicable;
5. explicit inputs, outputs, dependencies, provider bindings, and data stores;
6. RBAC/ABAC and least-privilege access definitions;
7. a PentaStatus adapter and heartbeat/readback contract;
8. immutable/auditable material-action records;
9. version, release, changelog, rollback, and supersession metadata;
10. incident, escalation, recovery, and continuity procedures;
11. machine-readable lifecycle state and production-readiness evidence;
12. no authority manufacture: a Penta may execute only within authority already granted by CrownThrive/CHLOM governance.

A Penta is **institutionalized** only when the required registry, portal, documentation, access, status, audit, release, and escalation artifacts are present. Naming alone does not satisfy the gate.

## DAIL execution rail

Every Penta-to-Penta `execute` handoff requires both CHLOM and DAIL authority references, an accountable owner, and a material-event plan using either `same_transaction` or `transactional_outbox`. Repository-level `execution_ready` means those gates are represented; it does not mean the external or domain effect has completed. Terminal certification still requires the resulting canonical DAIL receipt and any operation-specific provider readback or rollback evidence.

Analysis, preparation, routing, verification, and preservation messages may circulate without manufacturing a material-event receipt, but any material state transition they later cause enters the same execution rail. Low-risk telemetry may queue only under the explicit unsealed policy and cannot support certification until sealed.

## CrownThrive IO portal contract

Canonical family index: `/io/pentas`  
Canonical per-system route: `/io/pentas/{slug}`

The authenticated CrownThrive IO route is the operator/control surface. The complementary public-safe PentaDocs/status contract uses `/penta/{machine_key_suffix}` as declared by `data/penta/family.registry.json`. Both routes resolve the same canonical machine identity; neither route grants execution authority or promotes maturity.

Every portal SHALL expose, when applicable: **Overview · Operate · Status · Docs · Integrations · Access · Audit · Releases · Incidents · Costs · Dependencies**.

CrownThrive IO is the operating/control surface; PentaDocs is the authoritative documentation surface. A portal may deep-link into PentaDocs but may not replace the documentation record.

## Canonical Penta family

| Penta | Institutional role | Canonical portal |
|---|---|---|
| PentaOS™ | Penta operating-system coordination layer | `/io/pentas/os` |
| PentaVergence™ | convergence of CrownThrive systems, lanes, and execution surfaces | `/io/pentas/vergence` |
| PentaTechture™ | technical/architectural structure and architecture governance | `/io/pentas/techture` |
| PentaPology™ | topology, relationship, dependency, and system-graph authority | `/io/pentas/pology` |
| PentaPlanes™ | control/data/execution/governance plane definitions and boundaries | `/io/pentas/planes` |
| PentaFabric™ | institutional/runtime fabric connecting governed Penta capabilities | `/io/pentas/fabric` |
| PentaMesh™ | interoperable service and execution mesh | `/io/pentas/mesh` |
| Penta Federation™ | federation bindings, events, proofs, and cross-domain state | `/io/pentas/federation` |
| PentaInterOps™ | interoperability contracts across Penta and CrownThrive systems | `/io/pentas/interops` |
| PentaBase™ | canonical Penta interface to ThriveBase/runtime data services | `/io/pentas/base` |
| PentaControl™ | control-runtime and governed execution authority | `/io/pentas/control` |
| PentaOrchestrator™ | cross-system orchestration and dependency-aware execution | `/io/pentas/orchestrator` |
| PentaMation™ | governed automation layer | `/io/pentas/mation` |
| PentaFlows™ | workflow definitions, state machines, transitions, and evidence | `/io/pentas/flows` |
| PentaRoute™ | governed request/routing/orchestration family | `/io/pentas/route` |
| PentaTun™ | bounded runtime execution primitive | `/io/pentas/tun` |
| PentaBeata™ | heartbeat/liveness primitive | `/io/pentas/beata` |
| PentaFetch™ | bounded transport/fetch primitive | `/io/pentas/fetch` |
| PentaGet™ | certified read/request primitive | `/io/pentas/get` |
| PentaHead™ | certified HEAD/request primitive | `/io/pentas/head` |
| PentaOptions™ | certified OPTIONS/request primitive | `/io/pentas/options` |
| PentaPost™ | certified creation/mutation primitive | `/io/pentas/post` |
| PentaPut™ | certified replacement/mutation primitive | `/io/pentas/put` |
| PentaPatch™ | certified partial-mutation primitive | `/io/pentas/patch` |
| PentaDelete™ | certified deletion primitive | `/io/pentas/delete` |
| PentaFlex™ | MCP/API framework and adaptable interface layer | `/io/pentas/flex` |
| PentaMCP™ | MCP runtime/tool-service interface | `/io/pentas/mcp` |
| PentaAgents™ | governed agent registry, execution, and agent lifecycle | `/io/pentas/agents` |
| PentaLLM™ | LLM provider/model governance and runtime bindings | `/io/pentas/llm` |
| PentaMCL™ | machine-learning capability/lifecycle layer | `/io/pentas/mcl` |
| PentaBoxes™ | plugin/component packaging and runtime extension system | `/io/pentas/boxes` |
| PentaSkills™ | governed skill/capability registry and lifecycle | `/io/pentas/skills` |
| PentaTools™ | governed tool registry and execution bindings | `/io/pentas/tools` |
| PentaStars™ | contracts and governed capability/authority agreements | `/io/pentas/stars` |
| PentaRithms™ | algorithms and governed decision/execution logic | `/io/pentas/rithms` |
| PentaSets™ | asset-set registry, packaging, ownership, and lifecycle | `/io/pentas/sets` |
| PentaScripts™ | governed script registry, execution, provenance, and versioning | `/io/pentas/scripts` |
| PentaMaps™ | system/relationship/status visualizations and operational maps | `/io/pentas/maps` |
| PentaBound™ | authority/resource boundary definitions | `/io/pentas/bound` |
| PentaBind™ | governed binding of identities, providers, assets, and capabilities | `/io/pentas/bind` |
| PentaWire™ | governed wiring/integration into the operating mesh | `/io/pentas/wire` |
| PentaCredentials™ | credential references, lifecycle, readiness, binding, and health without secret exposure | `/io/pentas/credentials` |
| PentaBuild™ | builds, packages, versions, and maintains software/adapters/plugins/bindings | `/io/pentas/build` |
| PentaCertify™ | certifies adapters, plugins, integrations, and execution paths using governed evidence | `/io/pentas/certify` |
| PentaNurture™ | maintains and nurses provider/software lifecycle health after build/certification | `/io/pentas/nurture` |
| PentaFactory™ | autonomous governed software/framework production factory | `/io/pentas/factory` |
| PentaSuite™ | RFA-driven agent laboratory/workspace builder with bounded TTL/lease lifecycle | `/io/pentas/suite` |
| PentaRFA™ | governed Request for Agent intake/decision contract | `/io/pentas/rfa` |
| PentaPR™ | pull-request lifecycle control, stacking, nurture, and terminal disposition | `/io/pentas/pr` |
| PentaMerge™ | governed merge execution and merge-readiness authority | `/io/pentas/merge` |
| PentaCloser™ | closes verified gaps/PRs after bounded remediation windows | `/io/pentas/closer` |
| PentaRelease™ | release-aware observe/classify/version/package/publish/readback subsystem | `/io/pentas/release` |
| PentaVersion™ | canonical component/content/policy/schema/version lineage, compatibility, effective-state, and supersession authority | `/io/pentas/version` |
| PentaSerialized™ | append-only serialization, stable identity, anti-overwrite/delete gating, tombstones, lineage, integrity, snapshots, and continuity receipts | `/io/pentas/serialized` |
| PentaFormat™ | canonical format, media type, schema identity, extension, migration, and format-compatibility authority | `/io/pentas/format` |
| PentaSOPs™ | governed SOP registry, procedure versioning, ownership, review, supersession, and operational continuity | `/io/pentas/sops` |
| PentaSLAs™ | governed SLA/SLO registry, effective targets, escalation ownership, measurement lineage, and service-commitment continuity | `/io/pentas/slas` |
| PentaTime™ | canonical scheduling, temporal policy, clock, TTL, deadline, and scheduler authority | `/io/pentas/time` |
| PentaDocs™ | institutional documentation, knowledge, navigation, glossary, and documentation governance | `/io/pentas/docs` |
| PentaContext™ | scoped context ingestion, provenance, redaction, retrieval, retention, and operational-memory plane; context is never authority | `/io/pentas/context` |
| PentaScribe™ | terms, glossaries, indexes, FAQs, dictionary, trademark and institutional record maintenance | `/io/pentas/scribe` |
| PentaMail™ | canonical email communications, delivery, queueing, templates, retries, bounce/complaint handling, and communication audit rail | `/io/pentas/mail` |
| PentaStatus™ | self-status/introspection and owner-reporting authority for Penta/system health and readiness | `/io/pentas/status` |
| PentaConcierge™ | concierge service intake, triage, routing, fulfillment, escalation, and service-history orchestration | `/io/pentas/concierge` |
| PentaMedia™ | media asset binding, operations, scheduling, routing, maintenance, and media-provider health | `/io/pentas/media` |
| PentaStudios™ | studio assets, provider bindings, recording/production routing, and studio operations | `/io/pentas/studios` |
| PentaBooks™ | governed book/manuscript/edition production, packaging, QA, canon, and publishing workflows | `/io/pentas/books` |
| PentaGeneration™ | seven-generation continuity, succession, lineage, handoff, proofs, archives, and stewardship | `/io/pentas/generation` |
| PentaGreen™ | commerce/economic activation authority; optimizes only within existing authority | `/io/pentas/green` |
| PentaCredits™ | credits/economic-value subsystem governed through PentaGreen/CHLOM controls | `/io/pentas/credits` |
| PentaCost™ | cost, resource-consumption, abuse-prevention, and economic-control visibility | `/io/pentas/cost` |
| PentaPay™ | governed compensation/payment workflow coordination, subject to existing financial authority | `/io/pentas/pay` |
| PentaOFAC™ | sanctions/compliance screening and fail-closed risk-control authority | `/io/pentas/ofac` |
| PentaSecure™ | security-control, prevention, detection, response, and security-readiness layer | `/io/pentas/secure` |
| PentaLiency™ | resilience engineering, hardening-plan authority, health-gated remediation, and recovery assurance | `/io/pentas/liency` |
| PentaBlue™ | defensive detection, containment, restore validation, and control-effectiveness assurance | `/io/pentas/blue` |
| PentaRed™ | sandbox-only adversarial simulation inside authorized PentaHoneyPot clone ranges | `/io/pentas/red` |
| PentaHoneyPot™ | ephemeral OS-clone range, Red/Blue duel orchestration, evidence, and teardown | `/io/pentas/honeypot` |
| PentaSnapshot™ | SHA-256 evidence-backed snapshot, manifest, and restore-baseline authority | `/io/pentas/snapshot` |
| PentaRollback™ | approved staged restore, recovery health-gate, and rollback authority | `/io/pentas/rollback` |
| PentaVault™ | governed secret/reference/valuable-asset custody and vault binding layer | `/io/pentas/vault` |
| PentaIP™ | intellectual-property, marks, rights metadata, provenance, and governance | `/io/pentas/ip` |
| PentaBoard™ | highest Penta directive/oversight body beneath applicable CrownThrive/CHLOM authority | `/io/pentas/board` |
| PentaDirectors™ | supervisory policy, SOP, SLA, standards, and organizational-direction layer | `/io/pentas/directors` |
| PentaManagers™ | agent/workforce management and bounded contract/assignment issuance | `/io/pentas/managers` |
| PentaWorkforce OS™ | institutional digital-workforce operating environment | `/io/pentas/workforce` |
| PentaCohorts™ | workforce/agent cohort grouping and lifecycle | `/io/pentas/cohorts` |
| PentaAccelerator™ | bounded acceleration/development lane for workers, agents, and capabilities | `/io/pentas/accelerator` |
| PentaNotes™ | agentic feedback, voting, ramifications, lessons, and institutional feedback record | `/io/pentas/notes` |
| PentaTriage™ | intake severity/priority classification and routing for workforce/system needs | `/io/pentas/triage` |
| PentaHealth™ | workforce/system health and operational-wellness coordination layer | `/io/pentas/health` |
| PentaHR™ | workforce lifecycle, role, policy, personnel, and institutional HR coordination | `/io/pentas/hr` |
| PentaBenefits™ | governed workforce benefit/entitlement coordination | `/io/pentas/benefits` |
| PentaLegal™ | institutional legal workflow, policy review, rights/compliance escalation coordination | `/io/pentas/legal` |
| PentaSELF™ | self-observation/self-model/readback component for governed system awareness | `/io/pentas/self` |

### Registered primitive/capability family

The family also includes registered capability primitives such as **PentaQuery, PentaSearch, PentaRead, PentaList, PentaParse, PentaResolve, PentaTransform, PentaValidate, PentaCache, PentaSync, and PentaIngest**. These SHALL be surfaced under `/io/pentas/primitives` and remain governed by the same identity, documentation, status, audit, and release rules when independently executable.

## Required documentation pack for every Penta

Every PentaDocs entry SHALL include, proportionate to the subsystem: Charter/Overview; User Guide; Owner/Admin Guide; Operations Runbook; API/Integration Guide; Data Model; Security/Permissions; Status/Observability; Incident/Recovery; Release/Changelog; FAQ; Glossary/Terminology; dependencies and provider bindings; deprecation/supersession instructions.

## PentaStatus universal contract

Every independently running Penta SHALL expose a machine-readable status adapter with: canonical ID/name; build/version; lifecycle state; overall state; heartbeat/readback time; dependency health; queue/backlog; error/incident state; configuration drift; credential/certificate readiness without revealing secrets; data freshness; documentation freshness; resource/cost indicators; security/audit flags; SLO/SLA indicators; action items; escalation owner; portal/docs references.

PentaStatus owns the semantics and aggregation of these reports. PentaMail is a delivery rail and MUST NOT redefine status truth.

## Family-wide owner reporting

Default reporting classes:

- **Immediate:** critical incident, security/compliance failure, authority violation, fail-closed transition.
- **Daily:** owner operational digest covering changes, degraded states, blockers, aging actions, and material costs.
- **Weekly:** institutional health/readiness report across the entire Penta family.
- **Monthly:** audit/readiness, lifecycle, access, documentation freshness, dependency, and release posture.

## Governance and lifecycle

Penta systems SHALL fail closed when required authority, credential binding, certification, evidence, or provider readback is unavailable. Historical or superseded materials may inform lineage but do not independently authorize current execution. Provider secrets are referenced through governed vault/credential bindings and are never embedded in documentation, source, portal payloads, or status reports.

## Trademark/mark usage

CrownThrive Penta product and system names are institutional marks of CrownThrive, LLC. Documentation should use the ™ symbol on first prominent use where appropriate; third-party provider names remain the property of their respective owners and must be identified as providers rather than substituted for CrownThrive system names.
