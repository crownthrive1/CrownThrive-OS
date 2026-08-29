# CrownThrive COS V1.0.0 — Total Penta Convergence Architecture

## Institutional objective

CrownThrive COS V1 is the converged operating model for every CrownThrive system, Penta, factory, persona, agent, provider, adapter, repository, scheduler, website, product, form, workflow, asset, entitlement, evidence artifact and governed HOLD.

The release invariant is:

> Nothing CrownThrive can observe, own, operate, deploy, publish, execute, schedule, sell, meter, license, route, store, govern or repair may remain unidentified or unreconciled by COS.

For consequential mutations, the required lineage is:

> identity → authority decision → Penta objective → route → lease → execution → independent readback → receipt → Cookie update → Census → DAIL → next action

COS does not equate convergence with indiscriminate activation. One hundred percent convergence means one hundred percent discovered, identified, classified, governed, evidence-addressable and repair-routable—with each capability intentionally active, intentionally gated, retired, superseded or human-reserved.

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

Unobserved historical names are not invented. For example, an unresolved `CrownThrive-Support` reference remains an explicit identity-resolution item until direct provider evidence binds or retires it.

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

All factories are production-enabled in the sense that their intended operating mode is active. Candidate-only factories remain candidate-only by design. Every factory must expose a repair route, status runtime and evidence lineage.

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

PentaPlanner remains active during weekends and outside business delivery windows.

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

COS adds only two orchestration clocks and reuses specialist clocks:

- `ct-dail-trust-checkpoint-v2` — minutes 7, 22, 37 and 52;
- `ct-cos-v1-convergence-v2` — minutes 9, 19, 29, 39, 49 and 59.

PentaPlanner, PersonaFactory, Pentas routing, software factory, PentaWire, PentaCensus, PentaSELF and provider-specific jobs retain their specialist clocks. Exact duplicate/superseded COS, checkpoint and Pentas-router clocks are retired and prevented from auto-restoring.

## Certification

`public.cos_v1_certify_v1` has two stages:

1. **Pre-release certification** binds the source branch SHA and records a PASS/HOLD receipt.
2. **Release readback certification** binds the verified production SHA after merge and promotes the release to `released` only when the runtime remains certifiable.

Load-bearing checks include:

- seven typed-truth authorities;
- all 34 entity kinds registered and populated;
- no unresolved lifecycle entities;
- 14/14 repositories provider-observed, federated and runtime-accounted;
- scheduler unknown count zero;
- zero unknown site truth states and zero unrouted non-current surfaces;
- all factories production-enabled, none offline, every factory repair-routable;
- current Pentas epoch `cos-v1` and full signed end-to-end canary PASS;
- signed DAIL checkpoints and valid Merkle inclusion proof;
- bounded uncheckpointed tail;
- PentaWire PASS with zero provider holds and zero tool-contract drift;
- OpenAI Penta Inference ready;
- current PentaOFAC evidence PASS;
- PentaMail serialized receipt epoch verified;
- PentaPlanner and PentaPersonaFactory production active;
- factory fleet operational;
- PentaSELF production;
- canonical COS clocks active and predecessor clocks absent.

## Human-reserved D3 boundaries

COS surfaces, but does not bypass, human-reserved decisions. Current categories include:

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

The release is complete when the operating estate is fully accounted, classified, governed, evidence-addressable and repair-routable—not when every intentionally gated capability has been switched on.
