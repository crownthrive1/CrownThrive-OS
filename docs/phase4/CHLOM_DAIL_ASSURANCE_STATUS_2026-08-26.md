# CHLOM + DAIL Assurance Status — 2026-08-26

- **Record ID:** `ct.assurance.chlom-dail.2026-08-26`
- **Latest assurance readback:** `2026-08-27`
- **Audience:** engineering, platform assurance, continuity, and governance reviewers
- **Visibility:** public-safe; no credentials, protected payloads, or private recovery material
- **Institutional phase:** **Phase 3 — Execute**
- **Institutional Phase 4 program:** **PREPARATION**
- **DAIL Phase 4 assurance decision:** **HOLD**
- **Infrastructure failover certification:** **NOT CERTIFIED**

## Executive status

CHLOM remains in the institutional Phase 3 namespace, and the institution-wide Phase 4 program remains in `PREPARATION`. The separate DAIL Phase 4 assurance decision is `HOLD` because the current evidence does not prove complete cold restoration or a reversible runtime failover cycle.

The hot status route was observed returning **HTTP 503 before repair**. That observation and the subsequent Edge v3 service-role boundary readback are preserved as historical evidence. Edge v4 is now `ACTIVE`; it was deployed at `2026-08-27T00:03:21.034Z` with bundle SHA-256 `7d49bc1bf19b8cf2ea895b07105a74dcc75b4a9ffc2e2598754b175f33857090`. V4 treats the service-role RPC result as untrusted, fails closed unless every aggregate hot invariant passes, and publishes only an exact nine-field top-level aggregate allowlist. It no longer exposes bindings, source-document or source-table references, vault-policy references, or authority ceilings.

Three consecutive Edge v4 `GET` probes returned **HTTP 200** with the exact allowlist, `production_hot`, 10 of 10 bindings bound, and zero hold or degraded counts. A `POST` probe remained **HTTP 405**. Direct execution of the underlying database function remains revoked from `anon` and `authenticated`; only `service_role` and `postgres` retain execution. The bounded, adversarially hardened hot-route repair is therefore verified.

The separate `chlom-mesh-control` route did not meet that bar. Its legacy RPC contract used a global idempotency key that was not bound to the actor and request digest, and authentication alone did not establish action/target authority. Edge v2 is now `ACTIVE` with JWT verification enabled and bundle SHA-256 `cf7a5768e925fbe969f0a160ef41c1f77d2d83a2c65310f2a8a7142d44a6ee78`. The deployed source is implemented to return a fail-closed hold before parsing or persisting a request or calling the database. Production gateway probes verified anonymous and invalid-token rejection with HTTP 401; no valid-JWT function-level hold response or authenticated action request was exercised or certified. This removes the raw RPC/error projection without claiming a working control-request path.

At `2026-08-27T00:02:09.625541Z`, the post-migration live DAIL integrity check was **PASS** across 2,761 events with zero failures and head `15cb005688665fb9d4c2f709f2c31740d17b5d79f39fb04c09645cd9ddb8b7bb`; the accepted result includes a documented legacy correction. The validated live `dail_events_hash_delimiter_v1_check` constraint rejects pipe characters in the variable text fields used by the pipe-delimited hash input, preventing ambiguous input composition without changing the deployed hash formula. That PASS is bounded to live ledger integrity.

The private Google Drive lineage package passed byte-exact readback and isolated recovery. Checkpoint `89fd5b43-2b65-483c-a700-90c4a8951612` and drill `1746cdda-db6d-4d3a-a747-927c59b00061` record the `ledger_lineage` scope, observed RPO of 419 seconds, observed RTO of 1 second, and successful tamper detection. The verified cold state and assurance ceiling are:

The hardened lineage verifier now requires an independently supplied snapshot SHA-256 and fails closed on malformed timestamps, boundaries, counts, corrections, or limitations. At `2026-08-27T00:08:33.078719Z`, verifier source SHA-256 `27a747da79a69830e86bbd497af30a9add4413ce43b8ba66d7e62bf14cd0cb19` replayed the real snapshot against its external anchor and returned `PASS`. The anchor must come from trusted custody; hashing only an untrusted snapshot is not independent evidence.

`LEDGER_LINEAGE_RECOVERY_VERIFIED` / `BOUNDED_COLD_ASSURANCE_ONLY`

This is not a complete DAIL database, PITR, cold-runtime cutover, or failover certification. Institutional Phase 4 activation remains false, the institution-wide Phase 4 program remains in `PREPARATION`, and the separate DAIL Phase 4 assurance decision remains `HOLD`.

## Current evidence matrix

| Assurance dimension | Current state | Evidence meaning | Boundary |
| --- | --- | --- | --- |
| Institutional generation | `PHASE_3` | CrownThrive remains in the Execute generation. | Phase 4 preparation does not activate Phase 4. |
| Institutional Phase 4 program | `PREPARATION` | The canonical institution-wide gate contract is preparing Phase 4 compatibility while Phase 3 execution remains authoritative. | Preparation is not Phase 4 activation. |
| DAIL Phase 4 assurance decision | `HOLD` | All ten DAIL assurance predicates are required and at least one remains unmet. | The hold cannot be promoted by documentation, routing, or version alone. |
| Hot runtime observation | `EDGE_V4_REPAIRED_AND_VERIFIED` | Pre-repair `503/HOLD`; Edge v4 is active, treats RPC data as untrusted, and fails closed unless all aggregate hot invariants pass. Three consecutive `GET` probes returned 200 with `production_hot`, 10/10 bound, and zero hold/degraded; `POST` returned 405. | This verifies the bounded public status route, not infrastructure failover. |
| Public response minimization | `EXACT_ALLOWLIST_VERIFIED` | The nine top-level fields are `contract`, `service`, `status`, `decision`, `control_plane`, `binding_summary`, `latest_heartbeat`, `public_surface`, and `secret_values_exposed`. | Binding rows and source, vault-policy, and authority-ceiling references are intentionally excluded. |
| Database execution boundary | `LEAST_PRIVILEGE_VERIFIED` | `anon` and `authenticated` cannot execute the underlying status function; `service_role` and `postgres` can. | This does not certify every platform authorization path. |
| Authenticated control request | `HOLD_AUTHORITY_AND_ACTOR_BOUND_IDEMPOTENCY_REQUIRED` | Edge v2 is active and JWT-gated but performs no database call, request parsing, or persistence; anonymous and invalid-token probes return 401. | No authenticated action-request path is certified working until principal scope and actor/request-bound idempotency are independently verified. |
| DAIL live integrity | `PASS` | At `2026-08-27T00:02:09.625541Z`, 2,761 events verified with zero failures and the recorded head, including a documented legacy correction. | It is not a full database backup-restore or cold-runtime certification. |
| DAIL hash-input ambiguity | `LIVE_CONSTRAINT_VALIDATED` | `dail_events_hash_delimiter_v1_check` rejects `|` in the variable text components of the deployed pipe-delimited hash input. | The deployed hash formula is unchanged; this is input-domain hardening, not a new formula or anchor. |
| Cold lineage recovery | `LEDGER_LINEAGE_RECOVERY_VERIFIED` | A private Drive package passed byte-exact readback, isolated materialization, linkage verification, and tamper injection. | Scope is `ledger_lineage`; protected event bodies and the complete database were not restored. |
| Lineage verifier | `EXTERNALLY_ANCHORED_REPLAY_PASS` | The hardened verifier requires an external snapshot SHA-256 and the real snapshot replay passed its metadata, correction, boundary, and linkage checks. | An external hash binds the payload-free artifact but cannot reconstruct or certify excluded event bodies. |
| Cold assurance ceiling | `BOUNDED_COLD_ASSURANCE_ONLY` | The lineage drill measured RPO 419 seconds and RTO 1 second. | Full DAIL database/PITR restore and runtime failover remain uncertified. |

## Complete remaining DAIL Phase 4 predicate set

The bounded hot-route and lineage-recovery proofs close their stated checks only. The canonical DAIL activation contract has ten required predicates, currently records zero as fully met, and combines them with `AND`. The following complete predicate set remains required and may not be inferred from those scoped PASS results.

1. **`dail.phase4.hot-api` — hot API and ledger-operation assurance:** independently read back authenticated append, event readback, chain status, correction append, health, and version; pass the required 10,000-event isolated load, 100-event production-safe canary, duplicate/error, latency, and 24-hour observation thresholds.
2. **`dail.phase4.source-custody` — complete reproducible source custody:** inventory all tables, indexes, constraints, triggers, functions, grants, RLS/FORCE RLS state, schedulers, extensions, and configuration dependencies; reconcile production-to-source digests and reproduce on clean PostgreSQL 17 with independent custody readback.
3. **`dail.phase4.independent-conformance` — independent full-chain conformance:** use a separate verifier implementation and principal to check every source event with zero sequence, hash, previous-link, replay, or correction-lineage failures before and after restore.
4. **`dail.phase4.encrypted-data-export` — encrypted data-bearing cold export:** export all DAIL rows and dependencies under approved authenticated encryption; bind plaintext, ciphertext, schema, count, and head hashes; retain in at least two off-provider failure domains and independently download, decrypt, and read back the result.
5. **`dail.phase4.isolated-pg17-restore` — isolated PostgreSQL 17 data-plane restore:** restore into a fresh network-isolated PostgreSQL 17 target with no source connectivity, then prove exact counts, boundaries, head, chain, schema, privileges/RLS/triggers, append idempotency, corrections, and an independently checkable restore receipt.
6. **`dail.phase4.rpo-rto` — measured recovery objectives:** complete at least three successful data-plane drills within 30 days at RPO no greater than 900 seconds and RTO no greater than 3,600 seconds, with no authority/correction loss or event loss beyond RPO and with independent timing evidence.
7. **`dail.phase4.failover-failback` — fenced failover and failback:** complete at least three primary-outage drills with writer fencing, no split brain, duplicates, or gaps, successful failover append/readback, failback reconciliation, a clean post-failback chain, and a verified abort/rollback path.
8. **`dail.phase4.external-anchoring` — independent external head anchoring:** produce at least 24 consecutive hourly-or-better signed/attested anchors across two independent failure domains, then prove tamper detection and provider-exit readback without exporting raw governed event bodies.
9. **`dail.phase4.ci` — required continuous-integration assurance:** require registry, unit, portable conformance, migration safety, schema/privilege drift, isolated restore, secret, dependency, and static-security checks; obtain three consecutive protected-main passes with no bypass and reproducible retained artifacts.
10. **`dail.phase4.security` — independent security and least-privilege certification:** complete a current threat model and independent review with no open critical/high findings; prove forced RLS, no anonymous/authenticated direct writes, pinned `SECURITY DEFINER` search paths, privilege-escalation and leak negative tests, backup-key separation, and a tested incident pause/recovery runbook.

The 419-second RPO and 1-second RTO are measurements for the bounded `ledger_lineage` drill only; they are not operational full-database recovery objectives or evidence of cold service readiness.

## Post-deploy hardening readback

The accepted post-deploy readback confirmed:

- Edge v4 is `ACTIVE`, deployed at `2026-08-27T00:03:21.034Z`, and its deployed bundle has SHA-256 `7d49bc1bf19b8cf2ea895b07105a74dcc75b4a9ffc2e2598754b175f33857090`;
- three consecutive public `GET` probes returned HTTP 200 with the exact nine-field top-level allowlist, `production_hot`, 10 of 10 bindings bound, and zero hold/degraded counts;
- a public `POST` probe returned HTTP 405;
- service-role RPC data is treated as untrusted, and aggregate-invariant failure produces a fail-closed `503/HOLD` response;
- binding details, source-document and source-table references, vault-policy references, and authority ceilings are absent from the public projection;
- `anon` and `authenticated` direct database-function execution is revoked, while `service_role` and `postgres` retain execution;
- the validated live `dail_events_hash_delimiter_v1_check` rejects ambiguous pipe inputs without changing the deployed hash formula;
- the live DAIL integrity rerun remained `PASS` at `2026-08-27T00:02:09.625541Z` with 2,761 events, zero failures, and head `15cb005688665fb9d4c2f709f2c31740d17b5d79f39fb04c09645cd9ddb8b7bb`;
- the pre-repair HTTP 503 observation remains preserved as the baseline.
- `chlom-mesh-control` Edge v2 is `ACTIVE` and JWT-gated; its deployed source is fail-closed before any body parsing, persistence, or database call, its deployed bundle SHA-256 is `cf7a5768e925fbe969f0a160ef41c1f77d2d83a2c65310f2a8a7142d44a6ee78`, and anonymous/invalid-token gateway probes returned 401. No valid-JWT function-level response was exercised.

This closes the bounded public status-route availability repair only. It does not certify the authenticated control-request route, lift the full-database restoration boundary, lift the infrastructure-failover boundary, advance the institutional Phase 4 program beyond `PREPARATION`, or change the DAIL Phase 4 assurance decision from `HOLD`.

## Routes and source references

- Hot status route: <https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/chlom-mesh-status>
- Held authenticated control route: <https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/chlom-mesh-control>
- Canonical CHLOM public-safe repository: <https://github.com/crownthrive1/chlom-protocol>
- Canonical CrownThrive OS parent: <https://github.com/crownthrive1/CrownThrive-Support>
- Machine-readable failover record: [`developers/manifests/chlom-mesh-failover.v1.json`](../../developers/manifests/chlom-mesh-failover.v1.json)
- Existing bounded production receipt: [`runtime/chlom-mesh-control/PRODUCTION_RECEIPT_2026-08-26_v1.md`](../../runtime/chlom-mesh-control/PRODUCTION_RECEIPT_2026-08-26_v1.md)
- DAIL canonical meaning and boundary: [`chlom/dla-dail-lex.mdx`](../../chlom/dla-dail-lex.mdx)
- Runtime and DAIL evidence contract: [`chlom/pentafabric-continuity-and-runtime-fabric.mdx`](../../chlom/pentafabric-continuity-and-runtime-fabric.mdx)
- Backup and recovery requirements: [`technology/dependency-backup-and-recovery.mdx`](../../technology/dependency-backup-and-recovery.mdx)
- Security and continuity requirements: [`technology/security-privacy-continuity.mdx`](../../technology/security-privacy-continuity.mdx)
- Institutional Phase 4 preparation contract: [`developers/manifests/phase4-gate-contract.v4.json`](../../developers/manifests/phase4-gate-contract.v4.json)

## Promotion rule

The DAIL Phase 4 promotion decision remains `HOLD` while the institutional state remains Phase 3 and the institution-wide Phase 4 program remains in `PREPARATION`. The verified Edge v4 status hardening, Edge v2 control-route fail-closed containment, live integrity and hash-input constraint PASS, and bounded lineage recovery are production evidence within their stated scopes; none independently or collectively establish a working public control-request path, Phase 4 activation, a complete DAIL database/PITR restore, or infrastructure failover certification.
