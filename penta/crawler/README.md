# PentaCrawler Mesh Protocol v3

**Stable service:** `penta.crawler`  
**Candidate runtime contract:** `ct.penta.crawler.systemwide.v3`  
**Candidate component version:** `3.0.0`  
**Institutional phase:** Phase 3 — Execute  
**Source state:** implemented candidate; not production-promoted by this source change  
**Authority ceiling:** D2 autonomous / D3 human-reserved  
**Lineage:** current-main rebuild of the valid intent from closed/unmerged PR #589 under current-main reconciliation issue #695

## Purpose

PentaCrawler is CrownThrive's bounded discovery and evidence crawler. Version 3 extends the existing communications research runtime into a systemwide registered-estate observer that can:

- roam the registered Penta estate without arbitrary private-network crawling;
- maintain a server-side protocol cookie for each registered Penta;
- inspect durable registry/runtime evidence for stale, degraded, missing-runtime and related fault signals;
- create incidents, flags and semantic tags for broken or degraded systems;
- raise PentaDiscovery cases;
- hand actionable cases into the existing PentaHelp metaprotocol;
- hand unknown/new-system discovery signals to PentaCensus, which remains the census/canonical discovery authority;
- carry information through content-addressed `Pentas` packets across the mesh;
- accept bounded oracle-adjudicated cookie mutations without allowing an oracle to rewrite institutional identity, authority or history;
- retain the existing bounded public-business communications research lane for PentaMarketer.

PentaCrawler is an observer, evidence collector and router. It does not become CrownThrive's authority merely because it can see or reach something.

## The protocol stack

### 1. Penta Protocol — `ct.penta.protocol.v1`

Every Penta is treated as a protocol participant with a stable system identity, explicit authority ceiling, runtime/evidence state and interoperable message behavior. The Penta Protocol does not collapse component version, maturity, certification, provider-write authority or institutional phase into one flag.

### 2. PentaCookie — `ct.penta.cookie.v1`

A PentaCookie is a **server-side per-Penta protocol capsule**. It is not a browser cookie, advertising cookie or end-user tracking identifier.

A cookie carries four deliberately separated concerns:

- immutable/stable identity claims derived from the canonical Penta system registry at installation time;
- bounded observed operational state from authorized observers such as PentaCrawler, PentaCensus, PentaSELF and PentaContext;
- oracle state that may change only through the oracle mutation contract;
- mutation policy, revision and sequence metadata.

Each cookie has a SHA-256 current revision and monotonic mutation sequence. Mutation history is append-only. Existing cookies cannot be hard-deleted through the protocol; retirement/hold is explicit.

New non-retired Penta registry entries receive a cookie automatically through the registry trigger. Existing Pentas are backfilled incrementally during crawler cycles to avoid one giant migration or a new scheduler clock.

### 3. Pentas Packet — `ct.pentas.packet.v1`

A **Pentas** is the bounded packet envelope Pentas use to send information through the mesh.

Each packet binds:

- packet type;
- source Penta system key;
- source cookie ID and exact source-cookie revision;
- target kind/reference and route lane;
- risk and authority class;
- correlation/causation IDs;
- priority, TTL and hop budget;
- JSON payload plus SHA-256 payload digest;
- content address (`sha256:<digest>`);
- optional signature reference/state;
- optional origin node reference;
- network epoch;
- idempotent dedupe key;
- lifecycle state.

The packet envelope is immutable after creation. Delivery/routing changes append hash-chained receipts and advance only permitted lifecycle fields. D3 packets may carry information but must declare `human_reserved`; they cannot use this protocol to execute D3 work.

Packet types currently include heartbeat, discovery, help, health, fault, tag/remediation, oracle observation/mutation proposal, mesh acknowledgement and governance escalation messages.

### 4. PentaDiscovery — `ct.penta.discovery.v1`

PentaDiscovery is a discovery/triage **protocol**, not a replacement census authority.

It receives `discovery.raise` packets or direct bounded discovery raises, normalizes them and routes them according to the signal:

- `unknown_system` and `discovery_requested` go to **PentaCensus** for census/canonical identity reconciliation;
- broken, blocked, degraded, stale, missing-dependency, missing-credential, missing-software and explicit help signals go to **PentaHelp**;
- D3 cases are raised into PentaHelp but remain held/waiting for human-reserved authority.

The implementation can exist before PentaCensus finishes namespace canonicalization. Its registry metadata therefore keeps namespace canonicalization explicit rather than pretending source creation alone established final institutional identity.

### 5. PentaCrawler — `ct.penta.crawler.systemwide.v3`

`penta_crawler_roam_v1()` performs bounded registered-estate roaming. It chooses systems fairly by oldest PentaCookie `last_seen_at`, refreshes their observed cookie state and raises signals for deterministic conditions currently including:

- `runtime_missing` — a production Penta has no `runtime_ref`;
- `stale_verification` — a production Penta has no verification timestamp or the timestamp is older than 24 hours;
- `declared_degraded` — registry metadata explicitly reports degraded/failed/error/blocked/hold state in recognized operational fields.

A raised fault is deduplicated by a SHA-256 fingerprint, written to the existing incident plane, flagged `penta-crawler:broken`, and tagged:

- `penta:discovered`;
- `penta:needs-help`;
- `penta:crawler-observed`.

The same event creates a PentaDiscovery case, which can then be routed to PentaHelp or PentaCensus.

## PentaHelp handoff

PentaCrawler does not recreate a competing remediation engine. PentaDiscovery calls the existing `penta_help.raise_v1` contract and preserves the existing PentaHelp lifecycle:

`ASK → TRIAGE → HELP → TEST_OR_BUILD → INDEPENDENT_CERTIFY → LIAISE → RESOLVE_OR_ESCALATE`

Resolution modes are selected deterministically from the discovery signal, for example:

- missing software → `build_software`;
- missing credential → `credential_reconcile`;
- stale evidence → `restore_evidence`;
- blocked/missing dependency → `provider_route`;
- other bounded breakage → `self_repair`.

PentaHelp continues to own remediation orchestration and escalation semantics.

## Oracle mutation contract

Oracle mutation applies only to the cookie's `oracle_state`. An oracle cannot mutate stable identity claims, observed evidence, the system registry, CHLOM authority, credentials, rights, money, provider permissions or D3 state through this API.

`penta_cookie_mutate_v1()` requires all of the following:

1. exact current cookie revision (`expected_revision`);
2. a unique idempotency key bound to a semantic mutation fingerprint;
3. a resolved CHLOM oracle adjudication;
4. an allow/approve/pass/accept/apply disposition;
5. `auto_resolve_eligible=true`;
6. no founder/professional requirement;
7. non-D3 adjudication/risk;
8. confidence at or above the cookie policy floor (default `0.80`);
9. disagreement at or below the cookie policy maximum (default `0.20`);
10. at least two distinct active/accepted/verified/final oracle positions;
11. patch keys constrained to the approved oracle-state vocabulary.

Every successful mutation creates an append-only mutation record with prior/new revision, sequence, patch digest, actor, adjudication ID, evidence refs and semantic fingerprint.

That is the bridge between oracle adaptability and PentaSerialized-style anti-erasure discipline: an accepted current value may evolve, but prior institutional state does not disappear silently.

## Security boundary

"Roam all" means **roam the registered CrownThrive estate through exact contracts plus bounded authorized public-web research**. It does not mean scan arbitrary networks, bypass access controls or acquire unrestricted root access.

The Edge Function enforces:

- POST-only custom service authorization compatible with the current communications control token;
- request size limit;
- HTTP/S only;
- no URL credentials;
- default HTTP/S ports only;
- private/local/link-local/metadata/multicast/reserved target rejection;
- A/AAAA DNS resolution and private-address rejection before fetch;
- redirect revalidation and redirect limits;
- fetch timeout and response-size limit;
- text-only content types;
- robots-aware public research;
- no raw webpage archival;
- single-pass entity decoding to prevent double-unescape behavior;
- bounded markup/anchor parsing;
- safe error codes without raw provider response bodies or stack traces;
- no raw credential forwarding;
- no consequential provider writes;
- no D3 execution.

The communications lane remains limited to public-business contact evidence and preserves the prior prospect's public email rather than destructively replacing it.

## Mesh flow

```text
Penta registry / PentaCensus
        |
        +--> PentaCookie install / revision lineage
        |
Penta --+--> Pentas packet -----------------------+
        |                                         |
        |                                  PentaDiscovery
        |                                  /            \
        |                         unknown/new          actionable
        |                            |                    |
        |                        PentaCensus          PentaHelp
        |                                                 |
PentaCrawler roam --> observe/tag/fault --> Discovery ----+
        |
        +--> bounded public research --> PentaMarketer evidence

CHLOM Oracles --> adjudication/quorum --> cookie oracle_state mutation
                                         |
                                  append-only mutation lineage
```

## Decentralization-ready, not decentralization-by-claim

The Phase 3 implementation uses ThriveBase/Supabase as the durable operational substrate. The packet and cookie contracts deliberately avoid making that provider part of the stable identity.

The protocol already reserves the fields needed to move transport outward over time:

- content-addressed packet identity;
- stable source Penta identity;
- exact source-cookie revision;
- optional public-key/signature references;
- origin-node reference;
- network epoch;
- correlation/causation lineage;
- TTL/hop controls;
- hash-chained receipts;
- idempotent replay behavior.

A future transport may use a message bus, peer-to-peer layer, replicated log, decentralized identity/VC mechanism, cryptographic timestamp/anchor or poly-chain adapter where justified. Transport decentralization must not turn a provider, chain, validator or oracle into CrownThrive authority. CHLOM remains the authority contract, and restricted evidence/private data must not be forced onto public infrastructure.

No token, public chain, decentralized settlement or autonomous economic authority is activated by this version.

## Runtime actions

The `penta-crawler` Edge Function exposes four authenticated actions:

- `status` — read bounded systemwide crawler/protocol counts;
- `roam` — run registered-estate cookie/backfill/discovery work;
- `communications` — run the existing bounded PentaMarketer public-business research lane without scheduling delivery;
- `tick` — compose registered-estate roaming with the existing communications plan/scheduler under the already-established cadence.

`tick` creates **zero new external scheduler slots**.

## Deployment and promotion sequence

This source change deliberately separates build from production promotion:

1. Merge the current-main PR only after applicable repository, security, database and governance gates pass.
2. Apply the exact accepted migrations to ThriveBase.
3. Deploy the exact accepted `penta-crawler` Edge Function.
4. Verify function digest/version and run authorization, SSRF, payload-normalization, cookie-install, packet, discovery, PentaHelp handoff and D3 fail-closed canaries.
5. Run incremental cookie backfill and read back counts/lineage.
6. Bind invocation to the existing PentaCensus/communications temporal fabric; add no duplicate external clock.
7. Independently re-read incidents, tags, PentaHelp requests, packet receipts, CHLOM oracle mutation behavior and existing communications behavior.
8. Only then promote the `penta.crawler` system registry from its current production version to `3.0.0` with exact deployment/readback evidence.
9. Let PentaCensus/governance separately canonicalize the PentaDiscovery namespace when its identity evidence is accepted.

Source existence, a successful migration, an Edge Function deployment or an HTTP 2xx does not independently establish production certification.

## Rollback / containment

If v3 canaries fail:

- disable the new runtime routes or hold the corresponding protocol registry rows;
- restore the prior independently known-good `penta-crawler` Edge Function version;
- leave cookie-mutation and packet-receipt ledgers intact for evidence;
- stop new routing while preserving packets/cases for reconciliation;
- correct forward through a governed migration rather than erasing event history.

## Explicit non-authorities

PentaCrawler/PentaDiscovery/Pentas/PentaCookie do not by themselves create:

- credentials or secret access;
- provider-wide write authority;
- rights/licenses/ownership;
- financial authority or money movement;
- legal/regulatory sufficiency;
- D3/sovereign authority;
- canonical census identity without PentaCensus/governance reconciliation;
- production certification without independent readback.
