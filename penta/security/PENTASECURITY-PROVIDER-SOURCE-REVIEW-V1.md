# PentaSecurity Provider Source Review v1

Status: **current-main restack / independent certification required**  
Owner: **PentaSecurity**  
Contract: `ct.penta.security.provider-source-review.v1`  
Preserved predecessor: PR #1995 / `security/penta-security-provider-runtime-review-v2-20260831` / `945e6ff7bd6b5e74c271164cea6fed6488a00f5e`

## Human-readable execution state

Machine fields remain canonical. Parenthetical labels are operator explanations only and create no authority.

- `native_execution_eligible=true` — **NATIVE-EXECUTABLE (can run its own built-in runtime)**.
- `pm_assignment_eligible=false` while qualification is incomplete — **PM-QUALIFICATION-PENDING (worker role exists; certification/node/cookie gates are not all satisfied)**.
- After every required predicate passes, PentaSecurity may become `pm_assignment_eligible=true` only for `security_review` — **PM-ASSIGNABLE (PentaPM may assign only its approved security-review worker role)**.
- `D0` — **D0 (read/observe only)**.
- `D1` — **D1 (low-risk bounded change)**.
- `D2` — **D2 (production change with guardrails)**.
- `D3` — **D3 (Founder/Human only — never autonomous)**.
- `d3_human_reserved=true` — **D3 HUMAN-RESERVED (Founder/Human only — never autonomous)**.
- `self_certification_allowed=false` — **SEPARATE CERTIFIER REQUIRED (this Penta cannot certify itself)**.

PentaDND intentionally remains **PM-NONASSIGNABLE (PentaPM will not assign it general work)** even though it is native-executable. That preserves guardrail/worker separation.

## Purpose

Extend the existing canonical PentaSecurity runtime so provider and Supabase Edge artifacts can receive a deterministic, exact-head, read-only security disposition instead of falling through to an unsupported-runtime hold. This is an extension of PentaSecurity. It does not create a new security authority, Penta family, certifier, provider executor, or CHLOM authority surface.

## Authority boundary

The reviewer may read an exact immutable source object from the canonical public GitHub repository, evaluate a version-pinned policy, hash the source, append a PentaSecurity evidence/decision receipt to canonical DAIL, and retain a bounded append-only receipt.

It may not merge or close a PR, deploy an Edge function, mutate a provider, create/rotate credentials, expose secret material, move money, issue rights or licenses, expand authority, execute autonomous D3 actions, issue CIE approval, or issue independent PentaCertifier certification.

`security_decision=true` is not `independent_certification=true`.

## Exact-head model

`penta_security.review_github_provider_source_v1(policy_key, exact_head_sha)` resolves only an exact immutable GitHub commit. It never falls back to `main`, a branch name, a tag, or a caller-provided URL. Repository and path are read from append-only PentaSecurity policy, not caller input. Raw source is evaluated in memory and is never written to a receipt or DAIL event. Only its SHA-256, byte count, control outcomes, exact head, policy version, and bounded metadata are retained.

## Policy and supersession

`penta_security.provider_source_policies_v1` is append-only. A policy change requires a new `policy_version`; earlier evidence remains bound to the exact policy that produced it. `supersedes_policy_version` provides explicit lineage without rewriting predecessor rows.

The current restack preserves both predecessor policy versions 1.0.0 and 1.0.1 from #1995. Version 1.0.1 narrows false-positive forbidden-literal matching while retaining the predecessor row.

## Threat model

| Threat | Control |
| --- | --- |
| Mutable branch substitution / TOCTOU | Exact 40-hex commit SHA |
| SSRF / arbitrary URL fetch | Host fixed to `raw.githubusercontent.com`; repository/path come from governed policy |
| Path traversal | Policy constraint rejects absolute/traversal paths |
| Oversized artifact | Version-pinned `max_source_bytes` with fail-closed disposition |
| Required security control removed | Required-literal policy produces HOLD |
| Known unsafe pattern reintroduced | Forbidden-literal policy produces HOLD |
| Secret/source retention in evidence | Raw source is never stored; only digest and bounded outcomes persist |
| Security reviewer used as certifier | Receipt says `independent_certification=false`; PentaCertifier remains separate |
| Public invocation | RPC is service-role-only |
| Policy history rewritten | Policy and review receipts are append-only |
| Evidence fabrication | Canonical DAIL append + exact event-hash readback is mandatory |

## Qualification sequence

PentaSecurity does not become a general-purpose PM worker. Its only new PM role is `security_review`.

The activation sequence is intentionally monotonic:

1. Current-main source restack and transactional tests.
2. Independent PentaCertifier assessment of the exact source subject.
3. Production-source merge through normal gates.
4. Provider migration/readback.
5. PentaSecurity production-maturity projection.
6. Active Pentas v2 node and current state cookie.
7. PentaPM roster refresh.
8. Independent readback must show `security_review`, `pr_eligible=true`, `execution_state=active`, `cookie_current=true`.
9. Only then may Identity Fabric project `pm_execution_eligible=true`.

Founder/Human D3 approval may authorize a D3 decision when the D3 contract requires one, but it never substitutes for steps 1–8.

## Release topology

`Build -> tests/threat model -> PentaSecurity decision -> CHLOM authority/rights -> applicable CIE -> independent PentaCertifier -> release/readback`

PentaSecurity may not certify its own implementation.

## Rollback / supersession posture

The change is additive. Historical #1995 source remains preserved. If superseded later, append a successor policy or revoke the new execution surface; do not delete prior security decisions, source lineage, or DAIL evidence.