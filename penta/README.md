# PentaOS™ — CrownThrive Technical Namespace

PentaOS is the canonical human-facing technical namespace for the CrownThrive operating system. It does **not** destructively rename stable machine contracts, database objects, provider identifiers, event schemas, or historical artifacts. Instead, it binds them through explicit aliases so existing production paths continue to work while the institution presents one coherent Penta* architecture.

## Five-axis kernel

The Penta prefix is made architectural rather than decorative through five invariant axes:

1. **Truth** — canon, documentation, assets, data, evidence, contracts, IP provenance.
2. **Authority** — governance, security, policy, rights, bounds, approvals, custody.
3. **Execution** — software, agents, algorithms, workflows, tools, scripts, factories.
4. **Interoperation** — APIs, MCP, routing, topology, bindings, wires, federation.
5. **Continuity** — convergence, recovery, versioning, lineage, generation, rollback.

Every Penta component declares at least one primary axis and may participate in multiple axes.

## Canonical component family

| Canonical name | Technical role |
|---|---|
| PentaOS | operating-system umbrella and namespace |
| PentaVergence | convergence, reconciliation, stale-state repair and supersession |
| PentaTechture | architecture definitions, ADRs and system decomposition |
| PentaPology | topology graph, dependencies, routes and reachability |
| PentaPlanes | execution/control/data/knowledge/interface plane abstractions |
| PentaOrchestrator | governed orchestration and sequencing |
| PentaFlows | workflows, state machines and runbooks |
| PentaFlex | API/MCP/adapter framework and interface registry |
| PentaInterOps | interoperability contracts and certification |
| PentaWire | transport, event and connection fabric |
| PentaBind | explicit service/platform/asset/agent bindings |
| PentaBound | policy, authority and capability boundaries |
| PentaSecure | security, trust, identity, secrets-boundary and assurance layer |
| PentaAgents | executable agent layer and agent registry |
| PentaMCL | machine-learning lifecycle, evaluation and advisory models; `PentaML` is an accepted shorthand alias |
| PentaLLM | LLM provider/model/prompt/routing contracts |
| PentaRithms | deterministic and model-assisted algorithm registry |
| PentaBoxes | plugin/capability packages and installable extension containers |
| PentaStars | contracts, schemas, invariants, SLAs and interface guarantees |
| PentaSets | governed assets, datasets, corpora, model assets and creative assets |
| PentaSkills | reusable skill packages |
| PentaTools | executable tools and tool contracts |
| PentaScripts | scripts, maintenance utilities and reproducible operators |
| PentaMaps | architecture diagrams, topology projections, Mermaid/ASCII/Canva-ready visualization specs |
| PentaIP | IP classification, provenance, disclosure, licensing and commercialization controls |
| PentaBase | canonical human name for the ThriveBase data/control-plane substrate |
| PentaFactory | governed software/component production factory |
| PentaDocs | documentation and institutional-knowledge projection |
| PentaScribe | canonical institutional language, semantic continuity, dictionaries/glossaries/indexes/FAQs, term discovery and mark-use evidence control plane |
| PentaSerialized | serialization, lineage, anti-overwrite, anti-silent-delete, recovery and continuity control plane |
| PentaMarketer | governed campaign validation, message packaging, queueing, bounded artifact dispatch and marketing evidence control plane |
| PentaRoute | routing and delivery primitives |
| PentaFederation | repository/platform/system federation |
| PentaFabric | runtime/federation fabric compatibility name |
| PentaGeneration | seven-generation continuity and succession |
| PentaStudios | media production/runtime integration |
| PentaBooks | governed book/canon/publishing production |

## Compatibility rule

`Penta* canonical name -> stable machine contract(s) -> implementation(s) -> evidence`.

A Penta rename may change presentation and registry aliases. It may **not** silently mutate a stable contract that another runtime depends on. Contract replacement requires a versioned successor, compatibility mapping, migration path, readback, rollback, and supersession record.

PentaSerialized is the family-wide continuity enforcement layer for material serialized state. Its canonical identity is `ct.penta.serialized`; its portal contract is `/io/pentas/serialized`; and its institutionalization manifest is `penta/registry/pentaserialized.institutionalization.json`. PentaSerialized does not replace PentaVersion, PentaScribe, PentaSnapshot, PentaRollback, PentaPR, PentaMerge, PentaRelease, or PentaGeneration; it supplies a common append-only lineage and anti-erasure contract those systems can consume.

## Runtime ownership

PentaBase stores the canonical Penta component registry, topology edges, agent registry, convergence jobs and receipts. PentaVergence schedules reconciliation in PentaBase; repository workers merely execute jobs that PentaBase has already authorized and queued.

PentaScribe and PentaMarketer also have a verified repository-native production control-plane lane. PentaScribe continuously reconciles and compiles semantic/IP-use evidence without auto-promoting candidates. PentaMarketer validates and queues campaigns and may emit bounded channel artifacts, while external provider mutation remains independently capability-bound. Their first verified production run is recorded in `data/penta/systems.extensions.pentascribe-marketer.json`; the live contract is documented in `docs/phase3/PENTASCRIBE_PENTAMARKETER_PRODUCTION.md`.

PentaSerialized is institutionalized as a source/control-plane subsystem through its runtime, policy, family/version identity, CrownThrive IO portal descriptor, PentaDocs charter/operations pack, status/audit/release/incident/continuity contracts, and machine-readable institutionalization record. Provider-backed adapters and frontend deployment remain separately certifiable/readback-bound and are never inferred from the institutional source record alone.

The normal cadence is:

- **PentaScribe/PentaMarketer control-plane cycle:** hourly at minute 23 through the governed GitHub Actions provider;
- **PentaSerialized continuity assurance:** defined by `.github/workflows/penta-serialized-assurance.yml`, with PR/push gating and scheduled integrity/self-test cadence; hosted execution is reported only when provider readback exists;
- **continuity convergence:** every 4 hours;
- **deep convergence:** once per local day at 11:00 PM America/New_York, DST-safe through a PentaBase local-time gate;
- provider-worker polling may occur more frequently but performs no convergence work unless a PentaBase job exists.

## Safety and continuity

PentaVergence is preservation-first:

- explicit DRAFT/HOLD or independently gated work is preserved;
- a PR may be automatically closed only when its head contributes no unique change relative to current `main`, or when a recorded supersession proves the replacement;
- an automatic merge requires the governed merge gate to be successful on the exact head, no HOLD marker, no draft state, no failed check, no unresolved base drift and no D3/human-reserved effect;
- force-push, branch deletion, history rewriting and fabricated evidence are prohibited;
- missing capability becomes a build/repair work item rather than an invented PASS.

PentaSerialized strengthens that preservation rule by requiring explicit lineage for serialized mutation and by rejecting blind overwrite, stale state replacement, silent governed deletion, unreceipted protected Git mutation, broken hash lineage, and unsupported history reconstruction.

PentaScribe and PentaMarketer inherit the same preservation rule: discovered terminology stays candidate-only until governed, mark-symbol evidence never manufactures legal registration, and a campaign artifact never manufactures provider publication or spend authority.

PentaOS is therefore a rebrand **and** a versioned institutional ontology: one discoverable family for architecture, execution, interfaces, intelligence, IP and continuity without sacrificing backward compatibility.