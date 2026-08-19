# Phase 2.99 — Integration-Control RLS Adjudication

**Date:** 2026-08-19  
**State:** evidence-preserving adjudication packet; no production DDL authorized or applied  
**Roadmap:** `CT-ADR-ROADMAP-010 / ten_phase_v1`  
**Governance:** `CT-ADR-GOV-011`  
**Phase state:** Phase 2 / 2.99; Phase 3 remains `blocked_pending_phase_2_99_hard_exit`

## Purpose

This packet records and reconciles the live security evidence that blocked automatic promotion of the GitHub Actions Node 24 packet. It does not weaken the finding, change production privileges, enable Row Level Security, create a database policy, rotate a credential, or claim that a critical advisory has passed.

The objective is to define the smallest reversible path by which an authorized D3 security decision can resolve the finding without breaking CrownThrive's service-role-only integration control plane.

## Preserved live evidence

A read-only inspection of the connected CrownThrive Supabase project found six tables in the private `integration_control` schema:

- `services`
- `endpoint_catalog`
- `request_budget`
- `gates`
- `request_audit`
- `mcp_tools`

All six currently report `relrowsecurity = false`. The table-inspection surface therefore emits a **critical RLS-disabled advisory**. The advisory remains an unresolved security-hardening finding under `CT-ADR-GOV-011` until it is remediated and independently revalidated or explicitly handled through the reserved D3 authority path.

A separate live privilege query was used to determine whether the advisory also demonstrated current client-role exposure. It did not. For all six tables at the time of inspection:

| Principal | Schema `USAGE` | `SELECT` | `INSERT` | `UPDATE` | `DELETE` |
| --- | --- | --- | --- | --- | --- |
| `anon` | denied | denied | denied | denied | denied |
| `authenticated` | denied | denied | denied | denied | denied |
| `service_role` | service runtime | allowed | allowed | allowed | allowed |

The role inspection additionally confirmed:

- `anon`: `rolbypassrls = false`
- `authenticated`: `rolbypassrls = false`
- `service_role`: `rolbypassrls = true`

No `integration_control` row policy was observed in the policy inventory at inspection time. This means the current boundary is supplied by schema/table ACLs plus the service-role execution path, not by RLS policies.

These observations reconcile two facts that must not be conflated:

1. the RLS-disabled advisory is a real unresolved defense-in-depth finding; and
2. the inspected grants do **not** demonstrate present anonymous or ordinary authenticated CRUD exposure.

The finding therefore remains blocking without being overstated as a proven public data breach.

## Runtime dependency analysis

The active `crownthrive-api-control` Edge Function was inspected without exposing runtime credentials. Its current control path is JWT-gated and uses the service-role credential only for governed internal RPC calls. Provider mutation remains disabled in this function's current API-control mode.

The four database RPCs used by that control path were independently inspected:

- `get_runtime_secret(text)`
- `integration_control_snapshot()`
- `integration_rate_check(text,text,integer,integer)`
- `integration_record_request(...)`

For each inspected RPC:

- owner is `postgres`;
- `SECURITY DEFINER` is enabled;
- `search_path` is explicitly fixed to `pg_catalog` plus the required private schema (`vault` or `integration_control`);
- `anon` has no `EXECUTE` privilege;
- `authenticated` has no `EXECUTE` privilege;
- `service_role` has `EXECUTE` privilege.

This evidence indicates that an RLS migration can be designed around the existing service-role-only boundary rather than by granting client roles broader access. It is **not** authorization to mutate production.

## Risk and authority classification

Changing RLS state, row policies, grants, SECURITY DEFINER behavior, service-role access, production database privileges, or credential-backed runtime behavior is a D3 privileged-security action under `CT-ADR-GOV-011`.

Agent quorum cannot substitute for authorized-human / qualified-security authority for that production mutation. The repository may define, validate, and review the migration plan, but it must not silently apply it as an automated self-heal.

## Least-privilege adjudication design

The authorized remediation path should preserve the current denial posture for `anon` and `authenticated` while proving that the service-role RPC runtime remains functional after RLS is enabled.

The proposed sequence is deliberately reversible:

1. **Snapshot evidence before mutation.** Record current table RLS flags, grants, role `BYPASSRLS` attributes, RPC ownership/security-definer/search-path settings, existing policy inventory, and control-plane smoke-test results. Do not record secrets or raw authorization headers.
2. **Use an authorized isolated test path.** Apply the candidate migration only in a governed non-production environment or other explicitly approved reversible test boundary. Do not create a paid provider branch or alter production merely to satisfy this packet without the required authority/cost decision.
3. **Enable RLS without broadening client privilege.** The target state keeps `anon` and `authenticated` without schema/table CRUD access. Do not add permissive client-role policies merely to make an RLS checker green.
4. **Preserve the service path intentionally.** Verify the expected `service_role` bypass behavior and the existing service-role-only `SECURITY DEFINER` RPC execution model. If provider/runtime semantics differ from the inspected state, fail closed rather than broadening privileges.
5. **Run bounded functional read/write tests.** Prove `integration_control_snapshot` reads, `integration_rate_check` state transitions, and `integration_record_request` audit persistence through the same authorized runtime used by `crownthrive-api-control`. Do not test destructive provider operations.
6. **Rerun the original failed control.** Re-inspect the six table RLS flags and the security advisor surface that produced the critical finding.
7. **Rerun the full security boundary.** Reconfirm anon/auth schema and CRUD denial, service-role-only RPC execution, fixed SECURITY DEFINER search paths, Edge Function JWT enforcement, no new critical/high finding, and no secret exposure.
8. **Rerun institutional and repository security validation.** The original finding, institutional documentation suite, Security Governance, GitHub Actions runtime gate where applicable, and independent specialist verification must all be current.
9. **Exercise rollback proof.** The migration must have a reviewed rollback that restores the known-good RLS/policy/grant state without deleting audit evidence. A rollback test belongs in the isolated test boundary before production authority is requested.
10. **Request D3 authorization for production.** Only after the evidence packet is complete may the production RLS migration be presented for authorized-human / qualified-security approval. Agent quorum remains advisory for this D3 execution decision.

## Hard acceptance predicates

The security finding is not eligible to move from blocking to resolved until all applicable predicates are evidence-backed:

- all six `integration_control` tables are in the approved RLS target state;
- `anon` and ordinary `authenticated` access remains denied unless an explicitly approved future product requirement says otherwise;
- no broad permissive policy is added as a compliance shortcut;
- service-role runtime behavior is demonstrated, not assumed;
- the four governed RPCs remain service-role-only and preserve fixed `search_path` protection;
- `crownthrive-api-control` remains JWT-gated and its governed read/audit flows pass;
- the original RLS advisory/control is rerun and no unresolved critical/high security finding remains;
- rollback is inspectable and test-proven in the authorized reversible path;
- independent Security & Privacy verification is affirmative;
- Operations/SRE verification covers runtime continuity and recovery;
- no credential, private mailbox, authorization header, or runtime secret appears in repository evidence.

## Effect on active packets

PR #64 remains the owner of the GitHub Actions Node 24 runtime/supply-chain packet. This RLS finding is external to its changed-file set, but it is a blocking institutional security predicate for automatic promotion under `CT-ADR-GOV-011`. Green CI is evidence, not sovereign authority.

PR #65 remains sequenced behind PR #64 because it collides with #64 in the agent-sovereign manifest and validator. This RLS adjudication packet intentionally changes neither of those files and therefore does not compete with either owner packet.

Any previous vote bound to an older PR head remains stale by definition. Current votes must remain exact-head-bound.

## Phase 3–10 propagation

Resolving this finding establishes a reusable least-privilege control for later database-backed adapters, MCP/API control planes, CHLOM/dS-CaaS services, automation, analytics, licensing, rights, AI/ML and other institutional services in Phases 3–10. The inherited rule is that compliance controls may tighten runtime access but cannot obtain a green status by creating broader client privileges or by breaking a governed service path.

This packet does not open Phase 3. Phase 3 remains `blocked_pending_phase_2_99_hard_exit` until every remaining Phase 2.99 hard-exit predicate is satisfied.

## Notification and Collab state

No material merge is created by this adjudication record, so no PASS SUCCESS Gmail is due from this packet alone.

Collab Portal remains fail-closed until all seven canonical predicates pass simultaneously: `credential_exact_match`, `project_meta_authenticated`, `institutional_project_uid`, `approved_field_map`, `authenticated_project_read`, `bounded_write_readback`, and `webhook_sender_delivery_integrity`. No private fallback address or credential is recorded here.

## Exact next packet

Agent B should independently review this adjudication packet against the live ACL/RLS/RPC evidence, confirm that it introduces no changed-file collision with PR #64 or #65, and refine only the reversible test/rollback evidence requirements if needed. Do not apply production RLS, grants, policies, privileged database changes, or credential changes. Route the resulting D3 migration decision to authorized-human / qualified-security authority after Security & Privacy plus Operations/SRE verification.