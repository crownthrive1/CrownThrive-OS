# PentaMaker

Status: production v1.0.0

## Purpose

PentaMaker selects the appropriate registered Penta to author or own an institutional artifact before the artifact is transported or published. It is a routing and responsibility-selection plane, not a transport, certification, or authority plane.

## Separation of duties

- **PentaMaker** selects the authoring/owning Penta.
- **PentaReports** authors evidence-backed proof, verification, and after-action reports.
- **PentaNotifs** authors active incident, outage, and recovery notices.
- **State Architecture Report** authors architecture/state status messages.
- **PentaMail** transports the selected Penta's message and records provider delivery evidence.

PentaMaker cannot send mail, manufacture evidence, certify a PASS, approve economic action, or expand the authority of the selected Penta.

## Runtime

`public.penta_maker_select_v1(artifact_type, context)` selects a registered route from `public.penta_maker_routes_v1` and returns the selected system identity, runtime reference, rationale, and a SHA-256 digest of the routing context.

`public.penta_mail_enqueue_with_maker_v1(...)` binds that selection into PentaMail metadata as `origin_penta`, `origin_penta_name`, and `penta_maker` before enqueueing delivery.

## Initial routes

- `proof` -> PentaReports
- `verification` -> PentaReports
- `after_action` -> PentaReports
- `incident` -> PentaNotifs
- `outage` -> PentaNotifs
- `recovery` -> PentaNotifs
- `status` -> State Architecture Report
- unmatched/system -> PentaReports fallback

## Security

The route table has RLS enabled, direct `anon` and `authenticated` table privileges revoked, and explicit fail-closed policies. PentaMaker functions are not executable by `PUBLIC`, `anon`, or `authenticated`; controlled backend/service-role and database runtime paths remain available.
