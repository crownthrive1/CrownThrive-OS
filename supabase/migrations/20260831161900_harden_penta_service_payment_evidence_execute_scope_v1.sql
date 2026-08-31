-- PentaService payment-evidence execution hardening.
-- Production containment was applied and independently read back on 2026-08-31.
-- The RPC is SECURITY DEFINER; caller authorization therefore must be enforced by EXECUTE grants,
-- not by current_user inside the function body.

REVOKE ALL ON FUNCTION crm.penta_service_intake_apply_payment_evidence_v1(
  uuid,text,text,integer,text,text,jsonb,boolean,boolean
) FROM PUBLIC;

REVOKE EXECUTE ON FUNCTION crm.penta_service_intake_apply_payment_evidence_v1(
  uuid,text,text,integer,text,text,jsonb,boolean,boolean
) FROM anon;

REVOKE EXECUTE ON FUNCTION crm.penta_service_intake_apply_payment_evidence_v1(
  uuid,text,text,integer,text,text,jsonb,boolean,boolean
) FROM authenticated;

GRANT EXECUTE ON FUNCTION crm.penta_service_intake_apply_payment_evidence_v1(
  uuid,text,text,integer,text,text,jsonb,boolean,boolean
) TO service_role;
