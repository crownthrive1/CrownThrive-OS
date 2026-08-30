# CrownThrive COS V1.0.0 — Total Penta Convergence Architecture

## Institutional objective

CrownThrive COS V1 is the converged operating model for every CrownThrive system, Penta, factory, persona, agent, provider, adapter, repository, scheduler, website, product, form, workflow, asset, entitlement, evidence artifact and governed HOLD.

The release invariant is:

> Nothing CrownThrive can observe, own, operate, deploy, publish, execute, schedule, sell, meter, license, route, store, govern or repair may remain unidentified or unreconciled by COS.

For consequential mutations, the required lineage is:

> identity → authority decision → Penta objective → route → lease → execution → independent readback → receipt → Cookie update → Census → DAIL → next action

COS does not equate convergence with indiscriminate activation. One hundred percent convergence means one hundred percent discovered, identified, classified, governed, evidence-addressable and repair-routable—with each capability intentionally active, intentionally gated, retired, superseded or human-reserved.

## Current release gate — live phase-control semantics

The authoritative release state is resolved at runtime from `integration_control.cos_release_registry_v1`, `integration_control.cos_phase_registry_v1`, the latest phase execution, direct GitHub `main` readback and applicable provider/deployment readback. This document intentionally does **not** hard-code a supposedly current Git SHA because any later governed merge would immediately stale that literal.

COS V1 is **not released** unless the release registry is `released` and both `production_sha` and `released_at` are bound by the Phase 15 finalizer. A historical pre-release certification, a source-validation PASS, a merged pull request, a deployment success, or a provider receipt alone cannot substitute for the complete phase chain. During the current Phase 00 convergence state, `production_sha` and `released_at` remain null. No production release claim is made while Phase 00 remains converging.

Phase execution is exact-source and monotonic. When canonical `main` advances after a phase execution begins, the older execution is preserved as historical HOLD/superseded evidence and may not receive a stale PASS. A replacement execution must bind the new exact `main` SHA and independently re-establish source-sensitive gates.

During founder-supervised COS build maintenance, schedulers may be intentionally quiesced. `PAUSED_FOR_TARGETED_MAINTENANCE` or the equivalent COS build-session pause is therefore intentional state, not production-health evidence and not permission to manufacture an active-clock claim. Reactivation is a separately governed, read-back transition.

Phase 00 remains `converging` until every required constitutional gate is proven, including regression closure, retirement/supersession cleanup and governed documentation projection. Phase 15 remains the only release path and additionally requires an exact-source, current, unheld founder D3 `cos.production_release` authority binding.

## Reproducible source validation

Install the pinned validation-only dependencies and run the single COS V1 source gate:

```bash
python3 -m pip install -r requirements/cos-v1-validation.txt
python3 scripts/validate_cos_v1.py --root .
```

The command executes JavaScript syntax and runtime tests, zero-argument function contracts without silent discovery, JSON Schema checks, provider-control contracts, and core Python Penta suites. Its PASS is source-scoped. Provider mutation, Git acceptance, deployment, production readback and release certification remain separate gates.

## Typed truth

COS rejects a simplistic single-source hierarchy. Truth is typed because the correct authority depends on the assertion being made.

| Truth type | Canonical authority | Governing rule |
|---|---|---|
| Institutional history | DAIL | History is immutable. Corrections are appended; prior assertions are not rewritten. |
| Rights, authority, identity and decentralized provenance | CHLOM | Missing or conflicting authority fails closed. |
| Current provider condition | Direct provider readback | Current provider state prevails over stale projections. |
| Reconciled institutional state | PentaSELF + PentaCensus | Conflicts are recorded and reconciled. |
| Capability, adapter and connectivity state | PentaWire + PentaCertify | Unproven mutation capability remains gated. |
| Working evidence and human projections | Drive / Docs / Sheets | Regenerated from current typed truth; not treated as provider truth. |
| Public representation | Websites / PentaDocs / public catalogs | Public claims are projections and must carry freshness/evidence state. |

A provider can therefore be live while an old Sheet remains stale. The provider readback is current truth, DAIL preserves the historical Sheet assertion, PentaSELF/Census records the conflict, and the projection is regenerated.

## COS kernel

The institutional kernel is a five-part operating relationship:

- **Pentas** is motion: signed, content-addressed operational packets.
- **DAIL** is history: immutable institutional events and receipt lineage.
- **PentaCookies** are local live state: node capability, health, capacity, evidence age and authority descriptors.
- **PentaCensus** is reconciled institutional state: the current accounted estate.
- **CHLOM** is trust: rights, authority, identity, provenance, wallet and decentralized evidence control.

Supporting authorities complete the loop:

- **PentaPlanner** decides what should happen and keeps nights/weekends productive through `plan_and_prepare` mode.
- **PentaSELF** detects what should no longer be happening and enforces monotonic repair.
- **PentaFactory** builds and repairs bounded D0–D2 work.
- **PentaPersonaFactory** reuses existing identities first and creates new persona candidates only when an actual capability gap cannot be satisfied by extension.
- **PentaCertify** independently proves provider, artifact, rights, schema and execution state.
- **PentaCloser** closes work only after terminal readback.

## Pentas COS Epoch 1

The current packet epoch is `cos-v1` under protocol `ct.pentas.packet.v2` version `2.0.0`.

Every new packet requires:

- an active source Cookie;
- an active, registered origin node;
- a canonical content address;
- a verified HMAC-SHA256 signature;
- a bounded TTL and hop budget;
- a correlation and causation chain when applicable;
- a typed target: system, capability, factory, persona, role, topic, quorum or broadcast;
- immutable receipts for emit, route, lease and acknowledgement;
- DAIL lineage for certification-relevant outcomes.

The signed predecessor epoch `pentas-v2-hybrid` remains accepted for verification. New COS emissions use `cos-v1`.

Pentas does not carry large artifacts when a content address is sufficient. The packet carries evidence references and retrieval authority while the artifact remains in its canonical store.

## DAIL Trust V2

DAIL is already the institutional spine. COS V1 adds scalable trust checkpoints rather than attempting to broadcast each event individually.

The checkpoint process is:

1. Select a deterministic bounded sequence of previously uncheckpointed DAIL events.
2. Preserve each event hash as a Merkle leaf.
3. Build a SHA-256 Merkle root.
4. Link the checkpoint to the prior checkpoint root.
5. Sign the canonical checkpoint payload with the governed Pentas signing reference.
6. Record membership rows so any included DAIL event can produce a Merkle inclusion proof.
7. Queue the signed checkpoint for CHLOM anchoring.

Internal checkpoint attestation is production active. Production-chain broadcasting remains explicitly `production_gated` until a human-reserved D3 decision identifies the chain/network, fee authority, signer/controller and direct provider transaction receipt. No external transaction is claimed without that receipt.

## COS Census V2

Census V2 accounts for 34 entity kinds:

`system`, `penta`, `provider`, `adapter`, `credential_binding`, `factory`, `persona`, `agent`, `scheduler`, `workflow`, `repository`, `branch`, `release`, `deployment`, `website_surface`, `domain`, `database`, `schema`, `dataset`, `drive_artifact`, `form`, `product`, `price`, `entitlement`, `campaign`, `media_asset`, `chlom_asset`, `wallet`, `protocol`, `policy`, `evidence_artifact`, `incident`, `hold`, and `commercial_opportunity`.

Census consumes live registries, direct provider observations and typed projections. A missing item in one legacy registry does not mean that the entity does not exist. Direct discovery, PentaWire, PentaSELF, provider readback and source-control inventories are reconciled into canonical identities and historical aliases.

## Repository federation

Fourteen direct GitHub provider observations are reconciled into both institutional federation and PentaRuntime registries. Every repository receives:

- a canonical role;
- deployment class;
- governance class;
- lifecycle state;
- mutation policy;
- default branch;
- provider observation evidence;
- historic aliases where names changed.

Repository roles include canonical OS, runtime-deployable, public/private protocol, authority, truth, continuity, interoperation, execution, library and provider adapter. Not every repository is assumed to require a Vercel deployment.

Unobserved historical names are not invented. A retired repository alias remains archive-bound until direct provider evidence binds it to the canonical OS identity or records its retirement.

## Version relationship graph

COS introduces `COS_RELEASE=1.0.0` without forcing every component to use the same semantic version.

Each relationship records:

- COS release ID;
- component key;
- component version namespace;
- component version;
- compatible COS range;
- source SHA;
- production SHA;
- state and evidence.

This allows CrownThrive OS, Pentas, PentaWire, PentaPlanner, PentaPersonaFactory and other components to retain meaningful independent versions while participating in one certified release train.

## Factory convergence

Eleven factories are first-class COS entities:

| Factory | Operating class | Production mode |
|---|---|---|
| Commercial Gap Certification Factory | certification | active |
| PentaGreen Commercial Release Factory | release | candidate-only until commercial evidence passes |
| PentaFactory Daily Agent Fleet | agent | active |
| PentaFramework Factory | framework | active |
| Locticians Digital Product Factory | commerce | active |
| Locticians Editorial Factory | content | active |
| Penta Persona Execution Factory | persona execution | active |
| PentaPersonaFactory | persona design/certification | active |
| PentaPlanner Candidate Factory | planning | candidate-only |
| CHLOM Proprietary Asset Factory | asset | candidate-only under governance cadence |
| PentaFactory Software/System Factory | software/system | active |

All factories are production-enabled in the narrow sense that their intended operating mode is active. That flag does not assert that every factory is currently healthy or effect-certified. Candidate-only factories remain candidate-only by design. Every factory must expose a repair route, status runtime and evidence lineage.

A HOLD may not be an idle terminal state. It must be classified as one of:

- `waiting_external`;
- `D3_human_required`;
- `factory_repairable`;
- `evidence_collection`;
- `provider_recertification`;
- `intentionally_gated`;
- `retired` or `superseded`.

PentaPlanner converts repairable conditions into deduplicated work packets. PentaFactory executes within WIP and cost limits. PentaCertify verifies. PentaCloser closes only after readback.

## PentaPlanner continuous mode

PentaPlanner remains active during weekends and outside business delivery windows under normal production operation. During an explicit governed maintenance/quiescence event, its schedule may be intentionally paused with the rest of the affected execution domain.

Business mode may route executable work. Weekend and overnight mode is `plan_and_prepare`, including:

- provider and adapter discovery;
- evidence collection;
- prospect and campaign preparation;
- Monday cold-mail queue preparation without sending outside policy;
- editorial and product candidate preparation;
- site truth reconciliation;
- factory failure classification and deduplication;
- repository, scheduler and documentation reconciliation;
- persona capability-gap analysis;
- commercial HOLD closure packets;
- D3 escalation packets for founder/provider action.

PentaPlanner respects WIP, retry, provider, PentaCosts and authority ceilings. It does not flood the factory when active WIP exceeds policy.

## PentaPersonaFactory

PentaPersonaFactory applies this decision order:

1. Can an existing persona perform the work?
2. Can an existing persona be safely extended with a certified capability?
3. Can a bounded subagent satisfy the requirement?
4. Only then create a new persona candidate.

A new candidate requires purpose, brand scope, capability manifest, authority ceiling, tools/adapters, handoff graph, voice, operating rules, cost/capacity policy, playbooks, retirement policy and tests. Independent certification and controlled testing are mandatory. Automatic authority never exceeds D2.

## Adapter and provider convergence

Adapters and tools are classified as:

- `production_active`;
- `intentionally_gated`;
- `certification_pending`;
- `retired` or `superseded`.

PentaWire contract accounting recognizes active, intentionally gated and retired tools. It does not incorrectly assume that every registered tool must be enabled.

The canonical PentaFactory generation capability is `capability://code-generation`, currently resolved to the governed OpenAI Penta Inference adapter. Provider credentials remain references; raw values are neither exported nor committed.

Adapters that imply D3, money movement, deletion, credential export, rights disposition or irreversible mutation remain gated until their specific authority and exact provider contract are proven.

## Public-site truth

COS separates **availability health** from **truth freshness**.

A site can be:

- available and current;
- available and stale;
- available and intentionally gated;
- available and conflicted;
- unavailable but with a known truth state.

Each surface records source truth revision, content revision, release reference, semantic drift, public-claim evidence, freshness lag, provider readback and auto-sync state.

The current baseline has 22 classified surfaces, zero unknown truth states, and every non-current surface routed to PentaPlanner. This does not claim that all public sites already reflect current institutional truth.

## HOT / WARM / COLD execution

COS preserves the connected operating model:

- **HOT:** internal CrownThrive MCP/API/Penta/CHLOM/DAIL execution.
- **WARM:** direct provider APIs and webhooks.
- **COLD:** continuity/fallback paths, including Zapier only where primary internal/direct-provider execution is unavailable.

Fallback execution cannot silently become the primary authority. Every fallback transition is recorded and reversible where the provider permits it.

## Canonical clocks

Normal production topology uses two COS orchestration clock families while reusing specialist clocks:

- `ct-dail-trust-checkpoint-v2` — minutes 7, 22, 37 and 52;
- `ct-cos-v1-convergence-v2` — minutes 9, 19, 29, 39, 49 and 59.

PentaPlanner, PersonaFactory, Pentas routing, software factory, PentaWire, PentaCensus, PentaSELF and provider-specific jobs retain their specialist ownership in normal operation. Exact duplicate/superseded COS, checkpoint and Pentas-router clocks are retired and prevented from auto-restoring.

A governed maintenance/quiescence event may intentionally pause all or part of this topology. A paused clock is not failed merely because it is paused, and it is not considered production-active until reactivation and scheduler readback prove that state.

## Certification

The COS V1 phase-control plane supersedes any interpretation that a pre-release status function can itself release the operating system. `integration_control.cos_phase_begin_v1`, gate receipts, exact-source readback, independent certification and `integration_control.cos_phase_finalize_v1` govern Phase 00–15 progression.

Phase 15 alone may bind `production_sha` and `released_at`, and only after all technical gates plus a separately governed exact-source founder D3 `cos.production_release` approval are current and unheld. The generic gate API cannot manufacture that D3 receipt.

Source validation, provider canaries and earlier `public.cos_v1_certify_v1` receipts remain evidence inputs. They do not override the phase-control plane or manufacture a production release.

The source-controlled `PentaFabric Production Canary` remains a separately governed external-activation capability. A legitimate run must come from exact accepted `main`, pass its protected environment, emit an HMAC-bound event through the certified workload identity path, and receive exact durable readback. A workflow result, step summary, enable variable, request field, or caller boolean cannot promote COS V1.

Load-bearing checks include:

- seven typed-truth authorities;
- all required Census entity classes registered and accounted;
- no unexplained lifecycle entities;
- repository provider observations reconciled into the canonical federation/runtime inventory;
- scheduler unknown count zero;
- zero unknown site truth states and every non-current surface intentionally routed or held;
- every active factory repair-routable and every candidate-only factory explicitly classified;
- current Pentas epoch `cos-v1` with signed end-to-end evidence;
- signed DAIL checkpoints and valid inclusion proof where the phase requires them;
- bounded uncheckpointed DAIL tail;
- PentaWire/provider contracts free of unexplained drift;
- PentaInference capability routing ready without hard-coding a model into business logic;
- current compliance/OFAC evidence where applicable;
- PentaMail receipt lineage verified where applicable;
- PentaPlanner and PentaPersonaFactory intentionally active in normal operation or intentionally paused by a governed maintenance event;
- factory fleet state explicitly accounted;
- PentaSELF state explicitly accounted;
- canonical scheduler topology restored and read back before final production certification, with superseded clocks unable to regain authority.

## Human-reserved D3 boundaries

COS surfaces, but does not bypass, human-reserved decisions. Current categories include:

- final COS production release authority at Phase 15;
- production-chain anchoring for DAIL checkpoints;
- domain registrant verification or provider-account actions requiring the human account holder;
- public surfaces whose policy is explicitly `human_approval`;
- payment, rights, credential, deletion or irreversible provider operations not already covered by a specific certified authority.

A D3 item receives a `governance.escalation` Penta and remains repair-routable through PentaLiaison. It is not counted as an unknown state.

## Security boundaries

COS V1 does not create:

- new money-movement authority;
- new provider authority;
- credential-export authority;
- provider DELETE authority;
- rights-disposition authority;
- external blockchain transaction claims without provider evidence;
- blind retries after ambiguous mutations;
- source-control disclosure of secrets or runtime tokens.

The convergence definition is satisfied when the operating estate is fully accounted, classified, governed, evidence-addressable and repair-routable—not when every intentionally gated capability has been switched on. The software release additionally requires the complete Phase 00–15 chain, accepted exact source, exact-SHA deployment, production/provider readback, restoration/continuity evidence and Phase 15 D3 release certification.
