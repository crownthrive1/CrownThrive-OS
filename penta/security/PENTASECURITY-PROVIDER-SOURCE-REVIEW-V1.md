# PentaSecurity Provider Source Review v1

Status: **candidate / certification hold**  
Owner: **PentaSecurity**  
Contract: `ct.penta.security.provider-source-review.v1`

## Purpose

Extend the existing canonical PentaSecurity runtime so provider and Supabase Edge artifacts can receive a deterministic, exact-head, read-only security disposition instead of falling through to `HOLD_PROVIDER_OR_UNSUPPORTED_RUNTIME_REQUIRES_SPECIALIST`.

This is an extension of PentaSecurity. It does **not** create a new security authority, Penta family, certifier, provider executor, or CHLOM authority surface.

## Authority boundary

The reviewer may read an exact immutable source object from the canonical public GitHub repository, evaluate a version-pinned policy, hash the source, append a PentaSecurity evidence/decision receipt to canonical DAIL, and retain a bounded append-only receipt.

It may not merge or close a PR, deploy an Edge function, mutate a provider, create/rotate credentials, expose secret material, move money, issue rights or licenses, expand authority, execute D3/sovereign actions, issue CIE approval, or issue independent PentaCertifier certification.

`security_decision=true` is not `independent_certification=true`.

## Exact-head model

`penta_security.review_github_provider_source_v1(policy_key, exact_head_sha)` resolves only:

`https://raw.githubusercontent.com/<version-pinned-repository>/<exact-40-hex-head>/<version-pinned-path>`

It never falls back to `main`, a branch name, a tag, or a caller-provided URL. Repository and path are read from append-only PentaSecurity policy, not from caller input. Raw source is evaluated in-memory and is never written to a receipt or DAIL event. Only the SHA-256 digest, byte count, control outcomes, exact head, policy version and bounded metadata are retained.

## Policy and supersession

`penta_security.provider_source_policies_v1` is append-only. A policy change requires a new `policy_version`; earlier evidence remains bound to the exact policy that produced it. `supersedes_policy_version` provides explicit lineage without rewriting predecessor rows.

The initial policy is scoped to the existing `penta-institutional-pr-terminal-provider` repair lane. It requires the canonical `integration_control` RPC binding, one-time wake requirement, repository allowlist, exact-head enforcement, draft rejection and zero-authority receipt flags. It rejects recurrence of the former default/public closeout RPC binding.

## Threat model

Primary threats and controls:

| Threat | Control |
| --- | --- |
| Mutable branch substitution / TOCTOU | Exact 40-hex commit SHA; raw URL contains immutable head |
| SSRF / arbitrary URL fetch | Host fixed to `raw.githubusercontent.com`; repository/path come from governed policy |
| Path traversal | Policy table constraint rejects absolute/traversal paths |
| Oversized artifact | Version-pinned `max_source_bytes` with fail-closed disposition |
| Required security control removed | Required-literal policy produces HOLD |
| Known unsafe pattern reintroduced | Forbidden-literal policy produces HOLD |
| Secret/source retention in evidence | Raw source is never stored; only digest and bounded outcomes persist |
| Security reviewer used as certifier | Receipt explicitly states `independent_certification=false`; PentaCertifier remains separate |
| Public invocation | RPC is service-role-only; anon/authenticated/public EXECUTE revoked |
| Policy history rewritten | Policy and review receipt rows are append-only |
| Evidence fabrication without chronology | PentaSecurity appends canonical DAIL and exact event-hash readback is mandatory |

## DAIL semantics

A completed review appends `penta.security.provider-source-review.completed.v1` through the canonical CHLOM DAIL append API. This is security decision evidence. DAIL Evidence/Decision/Execution semantics do not imply or define CHLOM token classes.

The retained receipt binds policy, exact source head, SHA-256, disposition and DAIL event ID/hash. Raw provider/source material is not retained by this runtime.

## Release topology

This reviewer only satisfies the PentaSecurity stage when its exact-head PASS receipt is authentic and applicable:

`Build -> security scanning -> threat model -> tests -> PentaSecurity -> CHLOM rights/authority -> applicable CIE -> independent PentaCertifier -> release`

The PentaSecurity provider-source-review implementation itself must travel through that same governed release topology. PentaSecurity may not certify its own implementation.

## Initial dependency

PR #1967 remains the existing owner lane for the institutional terminal-provider schema-binding repair. This reviewer is the bounded missing PentaSecurity capability needed to assess that Edge/provider source without inventing a duplicate provider or weakening ACLs. #1967 remains HOLD until the reviewer itself is independently promoted, then returns an exact-head PASS for the then-current #1967 head, followed by CHLOM/applicable CIE/PentaCertifier gates and governed deployment/readback.

## Security baseline mapping

This control contributes architecture/evidence toward, but does not itself establish external certification for:

- NIST CSF 2.0: Govern, Identify, Protect, Detect;
- NIST SP 800-53 Rev. 5: AC, AU, CM, SA, SI families;
- NIST SP 800-207: explicit verification / no implicit trust;
- NIST SSDF SP 800-218 and SP 800-161r1: source integrity and supply-chain evidence;
- CISA Secure by Design / Secure by Default and Zero Trust Maturity Model;
- OWASP ASVS and API Security Top 10 release controls;
- CIS Controls v8 secure configuration/change control;
- SLSA/SBOM/signed-provenance architecture, where separately implemented;
- SOC 2 Type II and ISO/IEC 27001:2022 control-architecture targets;
- PCI DSS isolation where payment surfaces are in scope;
- NIST Privacy Framework architecture where applicable.

Mappings are implementation architecture only. They are not claims of SOC 2, ISO 27001, PCI, SLSA level, or other third-party certification.

## Rollback

Before production promotion, the rollback point is the protected-main commit immediately preceding this migration. The migration is additive and does not alter existing PentaSecurity receipts. If later superseded, retain policy/receipt lineage and revoke the new RPC rather than deleting historical evidence.
