# PentaService Payment Evidence Execute-Scope Hardening

Date: 2026-08-31

## Defect

`crm.penta_service_intake_apply_payment_evidence_v1(uuid,text,text,integer,text,text,jsonb,boolean,boolean)` is a `SECURITY DEFINER` function. Production privilege readback showed `anon` and `authenticated` could execute it. The function's `current_user` check is not a valid caller-identity boundary under `SECURITY DEFINER`, because execution assumes the function owner's identity.

The RPC can persist payment evidence and, when evidence is verified, change payment/entitlement state and release eligible Go Flipbooks work from `waiting_payment`. Client execution therefore violates the PentaService payment-evidence authority boundary.

## Production containment

Execution was restricted to `service_role` only:

- `anon`: EXECUTE false
- `authenticated`: EXECUTE false
- `service_role`: EXECUTE true

No synthetic payment evidence was created and no entitlement was activated as part of containment.

## DAIL evidence

Canonical DAIL terminal event:

- event id: `ff347b5c-b9f8-4aac-9215-7d74b83ebf30`
- event type: `security.function_execute_scope_hardened`
- entity: `crm.penta_service_intake_apply_payment_evidence_v1`
- authority: `ct.directive.dail.mandatory-evidence-spine.v1`
- event hash: `60a92e6d829d1a96cadb1f44966263ed457228159774f0ecd80284a240af43e3`
- payload SHA-256: `bc49756c30de3cd251bc81b30da289ce2d759c3b74f8897ae84c53416fdd7bcb`

The DAIL payload contains only the function identity, privilege disposition, directive reference and hashes. It contains no credentials, payment instruments or provider evidence bodies.

## Required invariant

Any future migration that replaces this function must preserve service-role-only execution unless a separately governed authenticated authorization contract is introduced and independently certified.
