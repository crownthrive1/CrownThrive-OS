# PentaSettle Provider Edge v2

## Production Status

PentaSettle Provider Edge v2 is **ACTIVE**, production-bound, and certified for exact-authority external settlement dispatch.

The provider edge is not a generic payment switch. It is a fail-closed boundary between an approved PentaPay obligation and an external Stripe or PayPal write. Every live dispatch requires an exact, single-use settlement authority grant; independent approval; recipient, amount, currency, adapter, and expiry binding; provider idempotency; and successful provider readback before economic finality can be projected into PentaPay, PentaLedger/DAIL, and PentaRelease.

No live payment was executed during certification. Certification used live provider authentication and readback plus zero-value, no-provider-write canaries.

## Canonical Economic Path

```text
PentaMarket
  → PentaTreasury / SmartTreasury
  → PentaCosts
  → PentaRoute
  → metering and reconciliation
  → PentaLedger / DAIL
  → PentaPay
  → PentaSettle exact-authority provider edge
  → provider receipt and readback
  → PentaRelease
```

CHLOM and PentaBound remain the authority, rights, and governance boundary around the entire path.

## Architectural Separation

| Component | Responsibility | Explicit Non-Responsibility |
|---|---|---|
| PentaTreasury / SmartTreasury | Issues execution authority and internal resource permissions. | Does not establish payroll, provider balances, or generic cash authority. |
| PentaCosts | Reserves, meters, prices, and reconciles work. | Does not create a payable or move money. |
| PentaPay | Records a legitimate economic obligation and its approval lineage. | Does not call Stripe, PayPal, or another provider. |
| PentaSettle | Validates exact settlement authority, claims a single dispatch, calls the certified provider adapter, reconciles provider state, and records finality evidence. | Does not inherit money-movement power from generic Penta competence or an execution budget. |
| PentaLedger / DAIL | Preserves immutable economic and settlement truth. | Does not authorize a provider write. |
| PentaRelease | Packages technical, economic, cultural, governance, and settlement evidence into release provenance. | Does not manufacture missing provider finality. |

## Mandatory Invariants

1. **Generic money movement is never inherited.** The Penta edge decision remains fail-closed with `MONEY_MOVEMENT_NOT_INHERITED` unless an exact settlement authority path is satisfied.
2. **Exact ECAC authority is required.** A live grant is bound to one PentaPay entry, adapter, recipient digest, amount, currency, expiry, issuer, independent approver, authority evidence reference, and exact ECAC reference.
3. **Self-approval is prohibited.** The requester/issuer and approver must be different active workforce assignments.
4. **Unattended monetary value is zero.** Every enabled adapter has `max_unattended_value_minor = 0`.
5. **Every authority grant is single-use.** A grant moves through `active → claimed → consumed`; it cannot authorize a second dispatch.
6. **Provider idempotency is mandatory.** Stripe uses an `Idempotency-Key`; PayPal uses deterministic sender batch/item identifiers plus `PayPal-Request-Id`.
7. **Provider acceptance is not finality.** A successful provider write may remain `provider_pending`; PentaPay settlement evidence is recorded only after receipt/reference validation and readback.
8. **Ambiguous outcomes hold.** Timeouts or uncertain post-dispatch outcomes enter a reconciliation HOLD rather than being retried as a blind second payment.
9. **Recipient material remains vault-bound.** The database stores a recipient reference and SHA-256 digest. Recipient material is resolved only after a valid, unexpired internal dispatch claim and is never projected into DAIL or public responses.
10. **Certification cannot move money.** All certification canaries use amount `0`, no exact grant, and `provider_write_performed = false`.

## Provider Adapter Registry

| Adapter | Provider Operation | Recipient Binding | Certification State |
|---|---|---|---|
| `stripe.connect.transfer.v2` | Stripe Connect transfer creation and exact transfer readback | Stripe connected-account identifier | READY |
| `paypal.payouts.penta.v2` | PayPal Payouts batch creation and batch/item readback through the Penta live app | Vault-bound PayPal email, payer ID, or phone | READY |
| `paypal.payouts.ambassador.v2` | PayPal Payouts batch creation and batch/item readback through the Ambassador live app | Vault-bound PayPal email, payer ID, or phone | READY |

The PayPal runtime preserves hot/cold credential routing and may fail over on authentication failure. The Stripe runtime uses the live Connect platform credential and validates the configured connected-account path during certification.

## Runtime State Machine

```text
created
  → authorized
  → dispatch_claimed
  → provider_pending
  → reconcile_claimed
  → settled
```

Fail-closed branches:

```text
created/authorized → cancelled
provider dispatch rejected → failed
provider write with uncertain or non-final outcome → hold
provider write accepted without final item state → provider_pending
provider readback mismatch → hold
```

A settlement reaches `settled` only when all of the following are true:

- the provider write was performed;
- the provider supplied a receipt/reference;
- readback passed;
- the provider state is final and successful;
- the observation evidence has a SHA-256 digest;
- `penta_pay_record_external_settlement_v2` accepted the authority, receipt, readback, and evidence envelope.

## Production Storage Surfaces

The v2 provider edge uses six RLS-protected production surfaces:

1. `penta_runtime.settlement_provider_adapters_v2`
2. `penta_runtime.settlement_authority_grants_v2`
3. `penta_runtime.settlement_intents_v2`
4. `penta_runtime.settlement_attempts_v2`
5. `penta_runtime.settlement_provider_edge_certifications_v2`
6. `penta_runtime.settlement_fabric_certifications_v2`

Settlement attempts, provider-edge certifications, and aggregate fabric certifications are append-only. All six tables are protected by RLS, and direct anonymous/authenticated access is revoked.

## Deployed Provider Edge

- Runtime contract: `ct.penta.settle.provider-edge.v2`
- Supabase Edge Function: `penta-settle-provider-edge`
- Function ID: `affebe57-dcae-4e4e-aa1b-8bfda994be2c`
- Function version: `1`
- State: `ACTIVE`
- Bundle SHA-256: `e833c9c5d4eb31ed7b785d4e10e69090d8c6a11c008bdeeb7126efb6d26b5ed0`
- Public behavior: safe health metadata only
- Internal actions: `health`, `certify`, `dispatch`, `reconcile`
- Provider-write default: `false`
- Raw secret projection: prohibited
- Raw recipient projection: prohibited

The function uses a Vault-held internal token in addition to the Supabase service-role boundary. `verify_jwt = false` is deliberate for this internal machine endpoint; the custom internal token is required for every non-public operation and is compared without returning token material.

## Provider-Edge Certifications

All certifications below used live provider authentication/readback and no provider write.

| Adapter | Certification ID | Evidence SHA-256 | Verdict |
|---|---|---|---|
| Stripe Connect transfer | `bb317468-2ace-4e90-a8d7-585595dd2b22` | `d4a94fc17bfff661387d52cc76acda3a10c74a9f31a76ec016ccb6552983e778` | PASS |
| PayPal Penta payouts | `b49fb8a3-40a3-4ac0-a334-3ecc7d6d75f9` | `610211412aca904eb009f6b207b4495343a2c747b5576f9efb28b3b731bb8d75` | PASS |
| PayPal Ambassador payouts | `299c4756-f30e-4966-a799-a9ad05f45c2d` | `98fe5581348579bade6cff2c7da25a0e77a7d1c92b9e994637862ce3378a0836` | PASS |

The negative and positive canaries proved:

- self-approval is rejected;
- independent approval is accepted;
- generic Penta authority returns `MONEY_MOVEMENT_NOT_INHERITED`;
- zero-value certification cannot perform a provider write;
- exact ECAC is mandatory for a live intent;
- idempotency and readback paths are present;
- provider credentials remain Vault-bound.

## Aggregate PentaSettle Fabric Certification

- Verdict: **PASS**
- Certification ID: `e5748e36-b1ce-4947-a2b2-60ac1ebd16be`
- Certification key: `ct.cert.penta-settle-fabric.v2.20260827230917587`
- Evidence SHA-256: `4cf892959507efadb937e7533fd4da52831313dc52f4f0929cc2f8ea7c430f89`
- Enabled adapters: `3`
- Ready adapters: `3`
- Settlement RLS: `6/6`
- Provider writes during certification: `0`
- Live settlement intents at certification: `0`
- Active exact grants at certification: `0`

## OS 2.0 Release Gate

PentaSettle is now a mandatory hard gate in the OS 2.0 production assessment. A release cannot reach `READY` when:

- any enabled provider adapter lacks a current PASS certification;
- the aggregate PentaSettle fabric certification is absent or expired;
- any of the six settlement tables lacks RLS;
- a canary recorded a provider write;
- a live intent lacks exact authority or independent approval;
- a settled intent lacks provider write, readback, or finality evidence;
- any adapter permits unattended value.

Final complete assessment:

- Release: `OS-2.0.0`
- Status: **CERTIFIED / READY**
- Production certification: `04ef4e03-cf55-499f-b6ed-597610e495b2`
- Pipeline run: `9ecc5c7b-7561-4801-85f2-02afa7673193`
- Blockers: `0`
- Warnings: `0`
- Disabled RLS findings in assessed production domains: `0`
- Economic-fabric RLS: `6/6`
- Settlement-fabric RLS: `6/6`

## Operational Boundary

PentaSettle v2 makes external settlement executable, but it does not make external payment automatic. A provider write can occur only after a positive PentaPay obligation has been approved, an exact settlement authority grant has been issued and independently approved, an intent has been created and authorized, and the internal provider edge has atomically claimed that intent.

At certification closeout, there were no live settlement intents, no active exact grants, and no payment dispatch. The architecture is therefore production-capable and fail-closed rather than production-simulated or indiscriminately live.
