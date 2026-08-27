# D3 Founder Production Approval Window v1

- **Window ID:** `ct.d3.founder-production-window.20260827.v1`
- **Directive ID:** `ct-founder-directive-d3-commercial-production-20260827-v1`
- **Campaign:** `ct.penta.flow-control.20260826.v1`
- **Risk class:** `D3`
**State:** active only while the server clock is inside the recorded interval and no revocation exists

## Executive outcome

The Founder-human approval predicate is prospectively pre-approved for exact CrownThrive D3 production candidates during the existing nonrenewing fourteen-day window:

- starts: `2026-08-27T01:23:52.144189Z`;
- expires: `2026-09-10T01:23:52.144189Z`;
- automatic renewal: prohibited;
- historical extension of the earlier campaign: none.

This removes repeated Founder prompts for in-scope exact candidates. It does not turn a candidate into a release or convert missing evidence into PASS.

## Exact scope

Eligible action classes are:

- `production_release`;
- `commercial_release`;
- `monetization_activation`;
- `production_gap_closure`;
- `production_hardening`;
- `provider_activation`.

Every consumption binds one subject, target system, action class, exact version, content SHA-256, requesting principal and, where applicable, governed release ID. Receipts are append-only and cannot be reused for another snapshot.

## Mandatory release dimensions

The release gate remains fail-closed until the exact candidate has current evidence for:

- exact snapshot;
- technical tests;
- security;
- independent verification;
- rollback and readback;
- production readiness;
- commercial readiness;
- monetization readiness;
- observability;
- post-release readback.

Requested effects add cumulative gates:

| Requested effect | Additional evidence required |
| --- | --- |
| Provider write | Operation-level provider-write certification |
| Payment, settlement or money movement | Exact money-movement authority |
| Rights disposition or license grant | Exact rights authority |
| Credential mutation | Approved credential custody and operation scope |
| Contractual or legal commitment | Authorized signatory/legal authority |
| Personal-data effect | Applicable privacy/compliance evidence |

## Runtime binding

`penta_runtime.consume_d3_founder_approval_v1` issues one exact-candidate human-approval receipt. `integration_control.apply_d3_founder_approval_window_v1` binds that receipt to a D3 row in `integration_control.governed_releases`. New D3 governed releases are auto-bound while the window is active.

The release-table guard requires the ten baseline certification dimensions and the applicable effect-specific dimensions. An accepted or published D3 release must carry a matching, unrevoked receipt and must have been accepted inside the window. A release accepted during the window retains its exact approval after expiry; a candidate not accepted before expiry returns to HOLD.

## Authority boundary

The window creates `human_approval_predicate_only`.

It does not create or substitute:

- independent evidence or verifier identity;
- technical, security or production proof;
- provider capability or provider-write certification;
- credentials or secret custody;
- rights, ownership or a license grant;
- contract or legal-signatory authority;
- pricing, payment, settlement, treasury or money-movement authority;
- privacy or regulatory sufficiency;
- destructive mutation authority;
- release, merge or deployment proof.

The existing flow-control HOLD remains effective until the independent-verifier and rollback/readback evidence for its exact candidate exists.

## Revocation and rollback

`penta_runtime.revoke_d3_founder_approval_window_v1` is authority-reducing. It appends a revocation, prevents new consumption, denies pending linked releases, rolls back linked published dynamic-feed releases through the governed rollback path, and preserves the directive, window, receipts and release history.

The migration rollback is therefore a revocation, not a destructive schema or evidence deletion.

## Verification

The deterministic companion evaluator is `runtime/penta_d3_approval.py`. It reports human approval and release eligibility separately. Its positive path requires every base and effect-specific gate to match the candidate's exact version and content hash, and the independent verifier must differ from the producer.

Passing the evaluator proves only the supplied exact evidence contract. Production deployment and provider readback remain separately recorded.
