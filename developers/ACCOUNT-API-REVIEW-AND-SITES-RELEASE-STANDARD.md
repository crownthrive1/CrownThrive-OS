# Account, API, Review, Stripe Connect, and Sites Release Standard

Status: `CANDIDATE — GOVERNED HOLD`

This standard turns the founder direction into one bounded architecture without claiming that held runtimes are already live. It does not authorize credential creation, checkout, money movement, publication, deployment, or audience expansion by itself.

## Population truth

Never collapse unlike populations into one member number. Website users, paying customers, active subscriptions, governance memberships, workforce identities, leads, audience reach, and generated assets are separate typed counts.

At the 2026-09-01 readback, connected evidence supports one verified live user/profile and one active Stripe subscription. It found no held customer account. The 3,139 current governance memberships cover internal governance/workforce identities and are not website customers. The public 125k+ member claim is not supported by the connected account and subscription systems.

## Website account to developer credential

The public API may create a developer account and key when a customer requests access through an approved CrownThrive website, but only through a new authenticated server-side route. The retired bridge key generator remains retired.

The route must:

1. Derive identity and tenant solely from a verified server-side JWT/session.
2. Bind one idempotent developer account to that identity; never accept a caller-selected owner.
3. Require an approved plan and a separately verified entitlement.
4. Create a high-entropy credential once, return plaintext once with `Cache-Control: no-store`, and persist only its prefix and SHA-256 hash.
5. Apply least-privilege scopes, plan key limits, expiry, rotation, and revocation.
6. Append a signed public-bridge receipt, source-control provenance, and DAIL-compatible evidence.
7. Pass anonymous denial, cross-tenant denial, replay, idempotency, concurrency, revocation, quota, webhook, and rollback tests.

Payment success does not create API entitlement, rights, fulfillment, settlement, or payout authority. Those are separate reconciled transitions.

## Deterministic review and four-hour supervision

The existing `ct.schedule.founder-operating-loop.4h.v1` subroute supervises account, activation, publishing, hold, and notification deltas. It remains folded into the existing External Evidence Relay. It must not duplicate minute-level database dispatchers or the Communications Watch mailbox clock.

An item may auto-progress only when all applicable predicates are current and independently verifiable: identity, tenant, consent, terms, product/plan, authority, evidence digest, security, privacy, content integrity, accessibility, rights, tax, licensing, payment/webhook where applicable, entitlement, rollback, and idempotency. A missing predicate is a typed hold, not an implicit pass.

Accessibility (`G03`), rights (`G05`), tax (`G06`), and licensing (`G07`) remain specialist decisions. The current review function cannot create a pass or verify reviewer authority, so it must not auto-approve those gates.

When a review cannot pass, create one deduplicated remediation message candidate with the applicable governed persona. Delivery routes through Communications Watch and PentaMail. Do not send while the active PentaMail `required_job_failure` incident remains critical, consent is absent, the sender identity is unverified, or a human-reserved decision is required.

## Stripe and Stripe Connect

Stripe is the processor and Stripe Connect is required for approved partner/seller lifecycles. They remain distinct lanes:

- platform billing owns customer charges and API subscriptions;
- Connect owns partner/seller identity, Stripe-hosted onboarding, KYC, and provider account status;
- CrownThrive entitlement reconciles the approved product/service access;
- settlement and payout require their own authority and readback.

Connected-account permissions remain limited because a provider connection can expose or mutate another party's account. Least privilege prevents one integration from becoming broad account authority. Stripe-hosted KYC, card, and bank custody reduces CrownThrive's sensitive-data footprint; CrownThrive stores stable provider IDs, status, entitlement references, and Vault aliases instead of raw payment or OAuth secrets.

The four observed Connect accounts must be reconciled to stable registry rows without importing OAuth tokens. Connect webhook ingestion must be certified before partner activation. No payment or payout route is opened by this document.

## PentaMail and persona behavior

PentaMail is the sole governed delivery rail; PentaMailer remains a provider-specific alias where registered. PentaPersona supplies the bounded role and voice, not new sender or approval authority. Each review message requires a stable message ID, thread/dedupe key, consent and suppression check, minimal safe body, provider readback, and an append-only outcome receipt.

## PentaAds custody and monetization

`penta.ads` remains the canonical identity. Proprietary source, packages, and nonsecret ledgers belong in existing restricted Drive custody and private Storage. Secret values alone belong in Vault. Do not place documents, archives, source, or ledgers in Vault.

The current `06c422a3ae0e7cd652a66adb63c02c54687eff3a` v1.2.0 source remains a candidate until exact-head CI, security, license, custody, and release gates pass. After they pass, create one exact source archive, hash it, store identical bytes in restricted Drive and private Storage, read back matching digest and size, register package/rights/file/binding records, and append a DAIL receipt. Do not deploy, license, advertise, or sell the candidate before that evidence exists.

## Default Sites build and release flow

Every future CrownThrive Site build must register a release candidate with the existing project and source identity as part of its build flow. The default sequence is:

1. Resolve the current approved Site project, live deployment, access revision, source head, and working tree.
2. Reuse the existing Site. Never create a replacement when one already exists.
3. Build a read-only candidate and bind its exact source hash, archive hash, migration set, CIE manifest, rollback point, and audience.
4. Run build, migration-ingestion, security, tenant-isolation, authorization-negative, idempotency/concurrency, stress, accessibility, privacy, and release-readback gates.
5. Save and deploy only through a bound native provider adapter after all required gates pass.
6. Publish only to the same already-approved Site and audience. An audience or access change is a separate decision.
7. Read back the saved version, deployment, environment revision, access revision, D1/storage state, public routes, private denials, worker errors, and rollback target.

The current Sites surface adapter emits a governed projection but does not perform a native provider write. Therefore this standard makes registration and gated release preparation automatic; it does not falsely claim that native Sites deployment is already automated.

## Public and internal phase language

Use two explicit labels until the public site is rebuilt:

- **Public ecosystem rollout: Phase 0.** This describes customer-facing consolidation, onboarding, and the incomplete One Seat/SSO experience.
- **Internal institutional controls: Phase 3 — Execute.** This describes governance and operating-control maturity, not public feature completion.

Neither label supersedes the other. Catalog presence and public claims are projections, not evidence of checkout, entitlement, fulfillment, member count, or operational authority.

## Brand candidate

Preserve “Governed Autonomous Automation Operating System” as internal founder-attested descriptor candidate `ct.brand-claim.crownthrive.governed-autonomous-automation-operating-system.v1`.

The recommended public tagline candidate is **“Governed autonomy. Evidence-backed execution.”** with stable ID `ct.brand-tagline.crownthrive.governed-autonomy-evidence-execution.v1`.

Internal registration is not a legal trademark filing. Do not use the registered-trademark symbol unless separate clearance and filing evidence exists.
