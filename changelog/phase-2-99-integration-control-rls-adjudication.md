# Phase 2.99 — Integration-Control RLS Adjudication and Remediation Evidence

**Date:** 2026-08-19  
**State:** remediation applied and revalidated; independent repository/security acceptance still required  
**Roadmap:** `CT-ADR-ROADMAP-010 / ten_phase_v1`  
**Governance:** `CT-ADR-GOV-011`  
**Phase state:** Phase 2 / 2.99; Phase 3 remains `blocked_pending_phase_2_99_hard_exit`

## Purpose

This packet preserves the original live evidence that blocked automatic promotion of PR #64 and records the subsequent founder-authorized production hardening. The remediation tightened the database boundary without widening client privileges, exposing credentials, changing provider write gates, weakening a validator, or deleting audit evidence.

The RLS finding is now **remediated at the Supabase control-plane level**. That does not by itself merge PR #64, open Phase 3, or replace the independent Security & Privacy / Operations-SRE / A-B-C-D-S governance checks.

## Pre-remediation evidence

The connected CrownThrive Supabase project contained six base tables in the private `integration_control` schema:

- `services`
- `endpoint_catalog`
- `request_budget`
- `gates`
- `request_audit`
- `mcp_tools`

Before remediation, all six reported `relrowsecurity = false`. Separate privilege inspection established that the condition was a real defense-in-depth gap but **not demonstrated anonymous or ordinary authenticated exposure**:

| Principal | Schema `USAGE` | Table CRUD |
| --- | --- | --- |
| `anon` | denied | denied |
| `authenticated` | denied | denied |
| `service_role` | server-side runtime | allowed |

The service role already held the intended CRUD permissions and `BYPASSRLS`; `anon` and `authenticated` did not have schema usage or table grants. The governed runtime RPC surface remained service-role-only and used fixed `SECURITY DEFINER` search paths.

## Founder-authorized remediation executed

The founder explicitly authorized implementation of the remaining hardening work in the active Phase 2.99 closure cycle. The production remediation therefore proceeded under the D3 human-reserved authority boundary rather than agent quorum substituting for human authorization.

Two tracked Supabase migrations were applied:

1. `enable_rls_integration_control_defense_in_depth`
   - enabled Row Level Security on all six `integration_control` base tables;
   - did **not** enable `FORCE ROW LEVEL SECURITY`;
   - did not grant `anon` or `authenticated` any schema/table access;
   - preserved the existing service-role server-side boundary.

2. `add_service_role_rls_policies_integration_control`
   - created explicit `service_role`-only `FOR ALL` policies on each of the six tables;
   - added no client-role policy;
   - did not broaden any existing table grant;
   - made the intended server-only RLS policy explicit and removable by normal migration rollback.

No credential was rotated, reconstructed, printed, committed, emailed, or logged. No Collab Portal write gate, CrownThrive IO write gate, MCP provider-write gate, payment state, rights state, customer state, or Phase 9 token/crypto capability was changed.

## Post-remediation database evidence

A fresh table-state inspection confirms all six base tables now report:

```text
relrowsecurity = true
relforcerowsecurity = false
```

The pre-existing privilege boundary remains intact:

```text
anon            schema usage: false   table access: denied
authenticated   schema usage: false   table access: denied
service_role    existing server-side CRUD retained
```

The explicit service-role policies do not grant access by themselves; PostgreSQL table privileges and schema usage remain separately required. No policy was created for `anon` or `authenticated`.

## Runtime smoke and original-control rerun

The original concern was not merely whether an RLS flag could be turned on; the hardening had to preserve the real control-plane runtime.

After the migrations, a bounded service-role smoke test executed the existing governed RPC path inside a rolled-back transaction:

- `integration_control_snapshot()` returned a JSON object;
- `integration_rate_check(...)` returned `allowed=true` with the expected rate-control structure;
- the test did not invoke a provider mutation and did not persist a synthetic audit event.

This demonstrates that the service-role/RPC path remained operational after RLS activation rather than relying on assumption.

The Supabase security advisor was then rerun. The first RLS-enabled pass correctly reported informational `rls_enabled_no_policy` notices. The second migration added explicit service-role-only policies, after which the security advisor returned:

```text
security lints: 0
```

This is the rerun of the original control family, not a replacement or suppression of the finding.

## Machine control-plane reconciliation

The governed Supabase gate:

`crownthrive_api_control / integration_control_rls_defense_in_depth`

was changed from `blocked` to `passed` with sanitized evidence reference:

`supabase_rls_enabled_service_role_policies_smoke_and_advisor_clean_2026-08-19`

The gate reason records that RLS is enabled on all six base tables, client roles still lack schema/table grants, the service-role smoke passed, and the security advisor is clean.

## Acceptance predicates — current result

| Predicate | Result |
| --- | --- |
| RLS enabled on all six base tables | **PASS** |
| `anon` schema/table access remains denied | **PASS** |
| `authenticated` schema/table access remains denied | **PASS** |
| No permissive client policy added | **PASS** |
| service-role runtime demonstrated after change | **PASS** |
| governed RPC model preserved | **PASS** |
| original security-advisor control rerun | **PASS** |
| unresolved Supabase security lints after policy reconciliation | **0** |
| credential exposure | **NONE OBSERVED / FORBIDDEN** |
| provider writes enabled by this change | **NO** |
| independent Agent S / Operations-SRE repository acceptance | **PENDING** |
| sovereign PR #64 exact-head quorum after fresh review | **PENDING** |

The production RLS remediation is therefore technically complete, while the repository/governance acceptance sequence remains fail-closed until independent reviewers consume the new evidence.

## Rollback / recovery

The production change is fully migration-addressable and contains no data rewrite. If a runtime regression attributable to these policies is demonstrated, the rollback path is:

1. preserve incident/audit evidence;
2. disable/remove only the explicit service-role policies and/or RLS state through a reviewed migration;
3. do **not** add client grants as a shortcut;
4. rerun the same service-role snapshot/rate-check smoke;
5. rerun the Supabase security advisor and full institutional/security validation;
6. independently verify before closing the incident.

Because `service_role` already had the intended table CRUD and bypass capability before the change, the remediation did not introduce a new customer-facing authorization dependency.

## Effect on active packets

PR #64 remains the owner of the Node 24 runtime/supply-chain and fail-closed GitHub-main perimeter bootstrap. Its previous Agent S block was based in part on this unresolved RLS finding. The underlying Supabase finding is now remediated, so **Agent S and Agent D must perform a fresh exact-head review rather than carrying the old RLS block forward automatically**.

PR #65 remains sequenced behind #64. Issue #83 still governs activation and verification of the provider-side GitHub `main` protection target after the #64 substrate becomes canonical. This RLS remediation does not remove that repository-perimeter gate.

PR #66 remains a documentation/evidence packet. It does not become sovereign authorization for any other D2/D3 action.

## Phase 3–10 propagation

This remediation establishes the database default for later API/MCP, CHLOM/dS-CaaS, identity, rights, analytics, licensing, AI/ML, automation and institutional services:

> private control-plane tables use RLS as defense in depth even when schema/table ACLs already deny client roles; policies must preserve least privilege, and a green security state may never be obtained by broadening client access or breaking the governed service path.

The result should be inherited by later Phase 3–10 database-backed services and validated through their own threat models.

This packet **does not open Phase 3**. Phase 3 remains `blocked_pending_phase_2_99_hard_exit` until every remaining Phase 2.99 hard-exit predicate passes.

## Collab and notification state

Collab Portal remains fail-closed until its seven canonical predicates pass simultaneously. Current live state has the credential, authenticated project metadata, pinned institutional project UID, and authenticated exact-project read passed; the approved field map, bounded write/readback, and webhook sender/delivery integrity remain incomplete.

No private fallback address or credential is recorded here. No PASS SUCCESS Gmail is due merely because this evidence packet changed; normal material-merge notification rules remain applicable after an authoritative merge.

## Exact next review

Agent S should now re-inspect the live RLS flags, client ACLs, service-role policies, Supabase security advisor, service-role smoke evidence, PR #64 exact head, and current provider-security evidence. If no other critical/high finding remains, replace the prior RLS-based block with a fresh exact-head disposition. Agent D should independently verify the same evidence before any governed promotion decision.