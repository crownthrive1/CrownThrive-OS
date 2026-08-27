# PentaMail™

**Role:** CrownThrive institutional email communications rail  
**Portal:** `/io/pentas/mail`  
**Status authority:** PentaStatus™  
**Documentation authority:** PentaDocs™

## Mission

PentaMail provides governed email composition, templating, routing, queueing, provider delivery, retry, bounce/complaint handling, message provenance, delivery evidence, and communication audit for CrownThrive systems and authorized operators.

PentaMail is a transport/communications authority. It does not manufacture business authority, governance authority, financial authority, or status truth.

## Core capabilities

- transactional and institutional email delivery;
- approved templates, layouts, identities, sender policies, and communication classes;
- queue priority, throttling, retry/backoff, dead-letter handling, and provider failover where certified;
- delivery lifecycle: requested → authorized → queued → accepted → delivered/deferred/bounced/failed/complained;
- message correlation to originating Penta, workflow, case, request, incident, release, or audit event;
- suppression, unsubscribe, consent, preference, and communication-policy enforcement when applicable;
- attachment/reference governance without exposing protected secrets;
- searchable delivery/audit records with retention policy;
- provider health and credential-readiness integration through PentaCredentials/PentaCertify/PentaNurture;
- status and incident telemetry to PentaStatus.

## Required portal surfaces

Overview; Send/Operate; Queues; Templates; Identities; Delivery Status; Providers; Integrations; Access; Audit; Suppressions/Preferences; Incidents; Releases; Docs.

## Integration contract

Pentas requesting email SHALL pass an authorized communication envelope containing origin Penta, purpose/classification, recipient reference, template/content reference, correlation ID, authority context, priority, retention classification, and idempotency key where applicable.

PentaMail SHALL return a message ID, lifecycle state, provider receipt/readback where available, and normalized failure classification.

## PentaStatus relationship

PentaStatus owns system-health and owner-report semantics. PentaMail transports PentaStatus alerts/digests and returns delivery evidence. A successful email delivery is not proof that the underlying system is healthy.

## Security and controls

- Secrets never appear in templates, logs, status payloads, or documentation.
- Sender identities and provider adapters require governed credential bindings and certification.
- Material sends must be attributable to an authorized human/system origin.
- Retries must be idempotent and bounded to prevent duplicate sends.
- Suppression/complaint rules override ordinary marketing or notification requests where legally or contractually required.
- Administrative actions and template/provider changes are audited.

## Mailgun delivery-resilience policy

Policy `ct.pentamailer.policy.mailgun-delivery-resilience.v1` activates from authoritative Mailgun evidence or a founder-accepted Mailgun notice. The latter can open the protective hold but cannot clear it. An accepted provider-probation event holds the global Mailgun route for at least three hours without consuming queued-message attempts and places the offending trigger on 72-hour probation. The currently accepted origin is `db-trigger:public.ct_factory_adapter_certification_queue:trg_os_v2_notify_provider_cert_state_v1`. Its identity is propagated per notification; unrelated notifications retain `os-v2:notification`, while `mailgun-relay:notifications` remains a fail-closed legacy fallback.

The route may leave HOLD only after the minimum interval and a fresh, ordered, authenticated Mailgun readback proves the provider is enabled. Release is controlled at no more than two messages per dispatcher invocation, two route-wide authorizations per rolling 60 seconds, and ten global authorizations per rolling hour. Capacity is reserved atomically before provider start and abandoned reservations are not refunded. A later accepted incident extends the hold and probation; local rate limits, heuristics, or unsupported operator assertions cannot automatically activate or clear the provider state.

While the causal trigger remains on probation, its source events are preserved and coalesced into one delayed digest rather than expanded into individual provider sends. A stable outbox request key protects idempotency. Once a provider call starts, a timeout or otherwise ambiguous result enters `reconciliation_required` and is not retried blindly. Provider response bodies are reduced to bounded reason data and a SHA-256 digest; the governed private notification recipient is resolved from database preferences and is not embedded in public source.

Queue, provider-incident, trigger-probation, release, and rollback evidence is append-only. Rollback returns the route to HOLD and preserves queued work and history; it never forces an unverified release. See `developers/PENTAMAILER-MAILGUN-DELIVERY-RESILIENCE.md`.

## Status contract

PentaMail reports at minimum: version; lifecycle; heartbeat; queue depth/age; throughput; delivery/failure/defer/bounce/complaint rates; provider health; credential/certification readiness; dead-letter volume; suppression anomalies; recent incidents; material configuration drift; outstanding action items.

## Runbook

Normal operation: accept authorized envelope → validate → resolve template/identity → queue → deliver through certified provider → normalize provider response → persist evidence → publish status/audit event.

Degraded operation: stop or isolate the affected route, preserve queued work, classify the failure, fail over only to a certified/authorized provider, report to PentaStatus, and preserve evidence.

Fail-closed conditions include missing authority, invalid recipient policy, unavailable required credential/certification, unsafe template/content state, or inability to establish required audit provenance.

## Documentation pack

PentaMail maintains: Owner/Admin Guide; Sender/User Guide; Template Guide; Provider Adapter Guide; Queue/Retry Runbook; Deliverability Guide; Security/Permissions; Data/Audit Model; Incident/Recovery; API/Integration Guide; Status/Observability; Releases/Changelog; FAQ/Glossary.
