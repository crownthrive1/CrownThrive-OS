# PentaStatus™

**Role:** CrownThrive self-status, introspection, readiness, and owner-reporting authority  
**Portal:** `/io/pentas/status`  
**Delivery rail:** PentaMail™  
**Documentation authority:** PentaDocs™

## Mission

PentaStatus continuously converts Penta and CrownThrive runtime evidence into normalized operational truth for the owner and authorized operators. Every independently running Penta SHALL publish a bounded status adapter to PentaStatus.

PentaStatus owns report semantics and aggregation. PentaMail may deliver reports but does not determine health truth.

## Universal status envelope

Each status producer SHALL expose: canonical Penta ID/name; version/build; lifecycle state; overall state; heartbeat/readback time; last successful execution/readback; dependency health; queue/backlog state; recent errors; incident state/severity; configuration drift; provider readiness; credential/certificate readiness without secret material; data freshness; documentation freshness; cost/resource indicators; security/compliance/audit flags; SLO/SLA indicators; open action items; escalation owner; CrownThrive IO portal reference; PentaDocs reference.

## Normalized states

`NORMAL`, `DEGRADED`, `BLOCKED`, `FAIL_CLOSED`, `INCIDENT`, `MAINTENANCE`, `DISABLED`, `UNKNOWN`.

`UNKNOWN` is not healthy. Missing or stale evidence SHALL not be converted to a green state.

## Owner reports

PentaStatus produces four default report classes:

- Immediate material-event alert for critical incidents, security/compliance failures, authority violations, failed production readbacks, or fail-closed transitions.
- Daily owner digest of changes, degradations, blockers, aging actions, incidents, provider issues, release activity, and material cost/resource signals.
- Weekly Penta Family institutional health/readiness report covering every registered Penta and required portal/documentation/status controls.
- Monthly audit/readiness report covering access, releases, lifecycle/supersession, documentation freshness, dependencies, provider certification, security/compliance, cost posture, and unresolved institutional gaps.

## Portal surfaces

Overview; Family Status; Per-Penta Drilldown; Incidents; Dependencies; Releases; Credentials/Certification Readiness; Data Freshness; Docs Freshness; Costs; Action Queue; Audit; Report History; Delivery Evidence; Integrations; Access; Docs.

## Status truth rules

1. Provider readback outranks intent or deployment requests.
2. Current production evidence outranks historical documentation.
3. A missing heartbeat produces stale/unknown state according to the subsystem contract.
4. Failed required dependency or authority can force `BLOCKED` or `FAIL_CLOSED` even when a process is technically running.
5. Status aggregation SHALL retain the underlying evidence references and timestamps.
6. PentaStatus may classify and report; it may not manufacture execution authority.
7. Reports must distinguish confirmed fact, inferred condition, pending validation, and unavailable evidence.

## PentaMail integration

PentaStatus emits authorized report envelopes to PentaMail. Delivery evidence returns to PentaStatus so the system can state whether a report was queued, accepted, delivered, deferred, bounced, or failed. Report delivery state is tracked separately from system health state.

## Incident behavior

For a material state transition PentaStatus SHALL: record the prior/new state; preserve evidence references; identify affected dependencies; calculate blast-radius candidates; classify severity; create/escalate the action; request PentaMail delivery if required; and continue bounded readback until recovery or supersession.

## Documentation pack

PentaStatus maintains: Owner Guide; Status Producer Guide; Status Envelope Schema; State Classification Guide; Alerting/Reporting Guide; Dependency/Blast-Radius Guide; Incident Runbook; Security/Permissions; Data/Audit Model; API/Integration Guide; PentaMail Delivery Guide; Releases/Changelog; FAQ/Glossary.
