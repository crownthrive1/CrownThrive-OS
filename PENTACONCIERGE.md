# PentaConcierge™

**Role:** CrownThrive concierge-services intake, routing, fulfillment, and escalation authority  
**Portal:** `/io/pentas/concierge`  
**Status authority:** PentaStatus™  
**Communications rail:** PentaMail™  
**Documentation authority:** PentaDocs™

## Mission

PentaConcierge provides one governed service layer for human and system requests that require intake, contextual triage, coordination, handoff, fulfillment, follow-up, SLA tracking, escalation, and service history across CrownThrive.

It is an orchestration/service authority, not an unrestricted executor. Requests that require money movement, rights changes, security changes, provider mutation, legal action, or other governed authority must route through the applicable authorized Penta/system.

## Core capabilities

- multichannel concierge/service request intake;
- requester identity/context and entitlement validation;
- classification, urgency, priority, and requested-outcome capture;
- routing to the correct CrownThrive lane/Penta/provider/human;
- case/request state and SLA tracking;
- appointment/reservation/request coordination where certified integrations exist;
- structured handoffs with full context and evidence links;
- escalation and exception handling;
- follow-up, closure, satisfaction/outcome capture, and institutional learning;
- durable service history and correlation across related requests;
- PentaMail communications and PentaStatus operational telemetry.

## Request lifecycle

`RECEIVED → VALIDATED → TRIAGED → ROUTED → IN_PROGRESS → WAITING_EXTERNAL | WAITING_REQUESTER → FULFILLED → VERIFIED → CLOSED`

Exception states: `BLOCKED`, `ESCALATED`, `DENIED`, `CANCELLED`, `EXPIRED`.

## Required portal surfaces

Overview; New Request; Active Queue; Assigned/Owned; SLA/Deadlines; Escalations; Fulfillment; Requester/Context History; Integrations; Access; Audit; Reports; Status; Releases; Docs.

## Service envelope

Every request SHALL carry: request ID; requester reference; origin/channel; service type; requested outcome; urgency/priority; authority/entitlement context; assigned lane/Penta; SLA/deadline; dependencies; communication preferences; evidence/attachments by reference; correlation IDs; status; next action; escalation path; retention classification.

## Routing rules

PentaConcierge SHALL route work to the system that owns the authority. Examples: email delivery → PentaMail; system health/reporting → PentaStatus; credentials → PentaCredentials; adapter/software work → PentaBuild/PentaCertify/PentaNurture; release → PentaRelease; media operations → PentaMedia/PentaStudios; economic activation → PentaGreen; compliance screening → PentaOFAC; workforce matters → appropriate PentaHR/PentaManagers/PentaDirectors controls.

PentaConcierge may coordinate these systems but must not bypass them.

## Communications

PentaMail is the default governed email rail for acknowledgements, confirmations, updates, escalations, and closure messages. Every outbound communication should correlate to the request/case ID and preserve delivery evidence.

## Status and reporting

PentaConcierge reports to PentaStatus: heartbeat; queue size/age; SLA risk/breaches; blocked/escalated requests; average time in state; provider/dependency health; failed handoffs; unresolved high-priority work; stale requester waits; recent incidents; cost/resource indicators; material configuration drift.

## Security, privacy, and audit

- enforce least privilege and purpose limitation;
- minimize sensitive information in queues and communications;
- store attachments and protected records by governed reference, not uncontrolled duplication;
- log assignments, state changes, escalations, fulfillments, authority decisions, and closure evidence;
- separate requester-visible notes from internal operational/audit notes;
- apply retention and deletion rules according to record classification.

## Documentation pack

PentaConcierge maintains: Requester Guide; Concierge/Operator Guide; Owner/Admin Guide; Service Catalog; Routing Matrix; SLA/Escalation Guide; Integration Guide; Data Model; Security/Permissions; Communications Guide; Status/Observability; Incident/Recovery; Releases/Changelog; FAQ/Glossary.
