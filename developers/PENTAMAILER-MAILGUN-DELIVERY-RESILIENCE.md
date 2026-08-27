# PentaMailer — Mailgun Delivery Resilience

This contract governs the CrownThrive response to an accepted Mailgun account or domain probation event. It protects delivery continuity without retry storms, silent message loss, or premature claims that the provider is enabled.

## Accepted policy

- Policy ID: `ct.pentamailer.policy.mailgun-delivery-resilience.v1`
- Version: `1.0.0`
- Authority: `ct-founder-directive-pentamail-provider-probation-20260826-v1`
- Decision: `ACCEPTED`
- Current accepted offending trigger: `db-trigger:public.ct_factory_adapter_certification_queue:trg_os_v2_notify_provider_cert_state_v1`
- Origin scheduler evidence: `pg_cron:ct-penta-self-v1`
- Fail-closed legacy relay alias: `mailgun-relay:notifications`

OS V2 now propagates the stable causal `trigger_ref` on each notification. Unrelated notifications retain `os-v2:notification`; they do not inherit the causal trigger's 72-hour probation. The relay alias remains a compatibility fallback if an older caller cannot supply a per-message identity.

This is an accepted governance and source-custody contract. The containment database and Edge Functions are deployed; provider-enabled state and controlled release remain pending until the post-hold Mailgun readback succeeds.

## Evidence and authority boundary

Automatic classification activates only from authenticated Mailgun evidence:

1. a provider HTTP response returned through the certified Mailgun adapter;
2. an authenticated Mailgun account or domain readback; or
3. a signed Mailgun webhook or provider notice with verified provenance.

A founder-accepted provider claim may activate protective containment, but it is not provider-authenticated evidence and cannot clear the hold. The incident currently in force came from the notice supplied in the founder work session and is recorded as `founder_accepted_notice`. A fresh, ordered, authenticated Mailgun sending-queue readback is mandatory after the minimum hold. A CrownThrive local rate-limit response, unattributed upstream failure, unauthorized operator assertion, heuristic, or model inference is not automatic Mailgun probation evidence. Evidence stores only the sanitized status, stable references, timestamps, and response digest required for audit. Raw credentials, raw provider response bodies, and unnecessary provider payloads are prohibited.

## Hold and probation sequence

| Stage | Required behavior |
| --- | --- |
| Accepted incident | Record its provenance class and identify the bounded `trigger_ref`. |
| Global route hold | Hold the complete Mailgun send route for at least 10,800 seconds (three hours). Preserve queued work and make no Mailgun send calls. |
| Trigger probation | Place the offending database trigger on probation for 259,200 seconds (72 hours), propagate that exact identity to its notifications, and retain `mailgun-relay:notifications` as a fail-closed legacy fallback. |
| Provider verification | After the minimum hold, obtain a fresh authenticated Mailgun readback proving the provider is enabled. Time alone never clears the hold. |
| Controlled release | Authorize no more than two messages per dispatcher invocation, two route-wide authorizations per rolling 60 seconds, and ten global authorizations per rolling hour. |
| Completion | End trigger probation only after 72 hours without a later accepted incident; retain the full evidence history. |

A later accepted incident extends both the global hold and the offending trigger's probation from the later observation. No sender lane, worker, priority, or trigger may bypass either rolling limiter.

While the causal trigger is on probation, its source events remain auditable but are coalesced into one queued digest delayed until probation ends. The system does not turn thousands of source changes into thousands of individual messages. Unrelated notification identities do not inherit this trigger probation.

## Attempt accounting

Messages deferred by the global hold or trigger gate remain queued. Entering, remaining in, or being rechecked during the hold does not consume a delivery attempt. Once release gates permit work, an atomic authorization reservation consumes conservative rate capacity before the provider-start gate; abandoned reservations are not refunded. A delivery attempt begins only when the provider-start record is linearized. A 30-second timeout or any otherwise ambiguous provider result moves the message to `reconciliation_required` and is never retried blindly.

Every outbox send uses a stable `penta-outbox:<message_id>` request key. Provider attempt identity is an immutable UUID, and the provider response is retained only as a SHA-256 digest plus bounded status/reason context. A Mailgun 2xx response means provider acceptance, not recipient delivery.

## Evidence and continuity

The policy requires append-only events for provider detection, route hold activation and release, and trigger probation start and end. Each record resolves the policy version, provider status, sanitized response digest, trigger, hold/probation deadlines, affected queue count, provider-enabled readback reference, release batch, and global quota reservation.

The existing PentaMail outbox receipt chain remains authoritative for individual message state transitions. Provider-level evidence complements that chain; it does not overwrite it.

Historical receipt verification found 26 preserved order forks. No historical receipt was rewritten or deleted. The correction and anchor-hardening migrations establish a serialized append-only epoch bound by composite foreign key to an immutable receipt/hash anchor. Its readback is `verified`, the anchor is verified, and the epoch contains three receipts with zero post-epoch forks.

The private notification recipient is resolved from the governed database preference. Public source contains only the institutional `contact@crownthrive.com` address; it does not embed the private recipient.

## Deployment readback

As of `2026-08-27T01:16:07.423670Z`:

- the production Mailgun route is held until at least `2026-08-27T03:11:55.823575Z`;
- the causal database trigger is on probation until `2026-08-30T00:11:55.823575Z`; `mailgun-relay:notifications` remains only the legacy fail-closed alias;
- five PentaMail outbox messages are preserved in `held` with zero delivery attempts;
- one queued probation digest preserves 2,464 coalesced events with zero attempts; 484 new source events were observed after governed coalescing began;
- Mailgun relay-control version 12, PentaMail version 5, and OS V2 runtime version 8 were read back active;
- the active source and queue prove exact causal identity custody and digest deferral, but no causal provider-call path was exercised during probation;
- there were zero provider attempt starts, outcomes, and rate reservations in the live snapshot;
- no Mailgun provider request was recorded after the emergency circuit became active; and
- Mailgun enabled readback and controlled release remain pending until after the hold boundary.

Rollback-only transactional verification proved that a later disabled readback clears stale enablement, the first two route authorizations in a rolling minute pass, the third is denied, a provider start linearized before an incident may finish, and a start linearized after incident acceptance is denied. The simulation persisted no production rows.

## Rollback

Rollback is authority-reducing and fail-closed:

1. return the Mailgun route to `PROVIDER_HOLD`;
2. preserve every queued message, incident, probation record, and audit-chain entry;
3. restore only an exact prior source or deployment version;
4. record a rollback receipt; and
5. prove post-rollback provider and queue state by readback.

Rollback must never delete evidence, conceal attempts, reset history, or force an unverified release.

## Source references

- `runtime/penta-provider-control-plane/mailgun-delivery-resilience.v1.json`
- `developers/manifests/pentamailer-mailgun-delivery-resilience.v1.json`
- `developers/manifests/pentamailer-mailgun-deployment-receipt.v1.json`
- `PENTAMAIL.md`
