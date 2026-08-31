# Penta Institutional Pre-Release Certification Order v2

## Status

Candidate control-plane repair. Source/readiness only until independently certified and released.

## Problem

`integration_control.penta_change_precert_status_v1` currently requires `production_readback_state` to be `pass` or `not_applicable` before independent certification can be issued.

That creates a circular dependency for new production software:

`independent certification -> release/deploy -> production readback`

cannot be satisfied when the precertifier requires:

`production readback -> independent certification`.

The result is a legitimate fail-closed HOLD, but it prevents dependency-ready candidates such as the PentaSecurity provider-source reviewer from reaching the independent-certifier boundary without fabricating a production state.

## Canonical v2 sequence

The v2 contract restores the CrownThrive release topology:

1. Build/source provenance.
2. Security scanning and threat-model validation.
3. Deterministic, negative and adversarial tests.
4. PentaSecurity decision.
5. CHLOM authority/rights decision.
6. Applicable CIE decision.
7. Independent PentaCertifier exact-subject disposition.
8. Governed release/deployment.
9. Exact production/provider readback.
10. Terminal institutional completion.

`PRODUCTION_READBACK` is therefore a **post-release** terminal predicate, not a pre-certification predicate.

## New read-only contracts

### `integration_control.penta_change_precert_status_v2(change_id)`

Pre-release readiness only. It still requires:

- source task completion;
- SHA-256 source digest;
- security PASS/not-applicable;
- rollback PASS/not-applicable;
- D0-D2 authority ceiling and no reserved effects;
- DAIL Evidence, Decision and Execution receipts;
- all four governed PentaDocs/Drive projection readbacks;
- exact PR/head identity when the terminal action requires it;
- zero unresolved D2/D3 non-certifier dependencies.

It deliberately does **not** require production readback and explicitly reports that post-release readback remains mandatory.

### `integration_control.penta_change_postrelease_status_v2(change_id)`

Post-release terminal readiness. It requires:

- active, unexpired independent certification bound to the current source SHA;
- certification activation DAIL receipt/hash;
- production readback PASS;
- four projection readbacks;
- DAIL execution evidence;
- exact PR/head identity when applicable.

Neither function issues certification, deploys, merges, writes providers, changes credentials, moves money, grants rights, changes D3 state or creates authority.

## Separation of duties

This repair does not weaken the independent-certifier boundary.

- PentaSecurity may issue a bounded security decision but may not certify its own implementation.
- Originators/builders/producers may not act as PentaCertifier.
- Repository `SELF_CERTIFIED` artifacts remain zero-authority originator-readiness evidence only.
- Production `public.penta_assure_certify_v1` remains separately governed by the PentaAssure independent-certifier integrity repair.
- D3/human-reserved actions remain outside this contract.

## Threat model

The v2 implementation explicitly prevents these failure modes:

- **pre-deployment production fabrication** — precert no longer asks callers to mark production as already changed;
- **certification bypass** — post-release readiness requires active independent certification;
- **documentation-as-runtime** — projections are readback evidence and do not replace production readback;
- **originator self-certification** — this contract issues no certification;
- **reserved-authority leakage** — D3, money, credentials, rights, legal/professional/final-contract, sovereign-vote and authority-expansion effects remain pre-cert HOLD;
- **public RPC exposure** — anon/authenticated execution is revoked; service-role execution only;
- **silent history rewrite** — existing v1 remains intact for historical compatibility; v2 is additive.

## Standards alignment

This control supports the CrownThrive security baseline by reinforcing:

- NIST CSF 2.0 — Govern, Protect, Detect, Respond, Recover;
- NIST SP 800-53 Rev. 5 — change control, separation of duties, auditability and configuration management;
- NIST SP 800-207 — explicit authorization before protected resource mutation;
- NIST SSDF / SP 800-218 — verified release gates and secure change management;
- NIST SP 800-161r1 — supply-chain/source provenance and release controls;
- CISA Secure by Design / Secure by Default — fail-closed release behavior;
- OWASP ASVS/API controls — least-privilege execution surface;
- SLSA — source/build/provenance before promotion.

These are implementation mappings, not claims of external certification.

## Rollback

Before production apply: close/supersede the candidate branch/PR with protected main unchanged.

After a governed apply: restore the prior function catalog by dropping the additive v2 read-only functions. Existing v1 functions and historical evidence remain untouched.

## Current dependency purpose

This repair removes the circular precert predicate blocking the current PentaSecurity provider-source-review dependency chain. It does not itself authorize the PentaSecurity reviewer, the terminal-provider repair, the privileged-RPC ACL hardening, the mandatory release-topology release, or the CHLOM Continuous Publisher.
