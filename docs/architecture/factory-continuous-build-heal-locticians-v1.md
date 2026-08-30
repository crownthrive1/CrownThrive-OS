# PentaFactory Continuous Build, Heal, Verify, and Locticians Feed v1

## Purpose

This control loop makes factory production a continuing operating obligation rather than a one-time certification event. Every registered factory must remain callable, production-active, packet-addressable, self-testing, independently certifiable, and evidence-producing. The same loop must continuously move governed editorial and digital-product work into Locticians.

The loop runs inside CrownThrive COS/ThriveBase. It is not a calendar reminder and does not require an open ChatGPT session.

## Permanent schedule

```text
job:     ct-penta-factory-continuous-build-heal-locticians-v1
cron:    25,55 * * * *
runtime: public.penta_factory_continuous_build_heal_cycle_v1()
status:  public.penta_factory_continuous_build_heal_status_v1()
```

The desired-state scheduler registry has automatic restoration enabled for the continuous loop and all Locticians digital-product clocks.

## Every-cycle sequence

```text
factory fleet census
→ universal supervisor
→ PentaPlanner repair when a factory drifts
→ verify fresh all-factory production canary
→ rerun canary when stale, failed, or count-mismatched
→ heal one Locticians editorial package
→ run editorial dispatch and due verification
→ verify Stripe checkout truth
→ orchestrate Locticians digital products
→ run governed nurture and QA
→ monitor native Locticians provider state
→ refresh convergence certification when required
→ update every factory registry record
→ append DAIL evidence
```

## Factory production canary

The all-factory canary remains active every six hours:

```text
job:  ct-penta-factory-production-canary-v1
cron: 17 */6 * * *
```

Every factory must:

```text
produce a bounded test artifact
→ self-check
→ self-attest
→ submit signed Pentas evidence
→ pass independent PentaCertify verification
```

A factory does not retain a stale green state after a failed test. It becomes degraded or held and is routed to PentaPlanner, the universal supervisor, PentaSELF, PentaWire, or the Hold Closure Factory.

## Locticians editorial feed

The editorial lane processes at least one eligible package per continuous cycle. The governed path is:

```text
rights-cleared image
→ public asset verification
→ content/link/CTA normalization
→ independent package audit
→ bounded provider update
→ exact provider readback
→ publish or schedule
→ DAIL receipt
```

A provider revision is never a blind retry. It requires a previous verified receipt, a current provider-before readback, an approved replacement SHA-256, a known provider SHA-256, and a bounded attempt ceiling.

## Locticians digital-product feed

The restored clocks are:

| Job | Schedule | Responsibility |
|---|---|---|
| `ct-stripe-payment-link-sync-v4` | `1 */6 * * *` | Read-only Stripe product/payment-link truth |
| `ct-locticians-digital-products-checkout-v1` | `7 */2 * * *` | Checkout and entitlement verification |
| `ct-locticians-digital-products-orchestration-v1` | `9,19,29,39,49,59 * * * *` | Listing, scheduling, provider publication, and verification |
| `ct-locticians-digital-products-nurture-v1` | `11,26,41,56 * * * *` | Opt-in nurture, listing QA, and refresh work |

A product with missing or contradictory checkout, entitlement, release, media-rights, or provider evidence remains held or quarantined. The control plane does not move money.

## State semantics

`pass` means all factories are ready, the factory canary passes, and the Locticians editorial and commerce feeds have no active release hold.

`partial` means the factory estate and canary are healthy, but one or more Locticians items still require governed audit, checkout repair, release reconciliation, or quarantine closure.

`hold` means a factory, canary, independent certification, or mandatory convergence control failed.

## Authority boundaries

- D0–D2: bounded autonomous work.
- D3: human-reserved.
- Money movement: not granted.
- Credential export: prohibited.
- Provider deletion: prohibited.
- Automatic top-level persona creation: disabled.
- Ambiguous provider mutation: hold and reconcile; no blind retry.
