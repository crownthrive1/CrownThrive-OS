-- Rollback for PentaHelp independent-gate PentaCertifier transport isolation v1.
--
-- The old direct `ct.penta.certify` target is safe to restore only before the isolated review
-- address has any dispatch/delivery lineage. Once exact-review packets use the isolated address,
-- preserve that evidence and supersede forward instead of collapsing it back into the generic
-- institutional dispatcher.

DO $rollback$
DECLARE
  v_transport text;
  v_preflight text;
  v_after text;
BEGIN
  IF EXISTS(
    SELECT 1
      FROM penta_help.independent_gate_dispatches_v1 d
     WHERE d.target_node_id='ct.penta.certify-review'
  ) OR EXISTS(
    SELECT 1
      FROM pentas.deliveries_v2 d
     WHERE d.target_node_id='ct.penta.certify-review'
  ) THEN
    RAISE EXCEPTION 'ROLLBACK_REQUIRES_FORWARD_SUPERSESSION_CERTIFIER_REVIEW_LINEAGE_PRESENT';
  END IF;

  DELETE FROM pentas.nodes_v2
   WHERE node_id='ct.penta.certify-review'
     AND metadata->>'introduced_by'='ct.penta.help.independent-gate-certifier-transport-isolation.v1';

  IF to_regprocedure('public.penta_help_dispatch_independent_gates_v1(integer)') IS NOT NULL THEN
    SELECT pg_get_functiondef('public.penta_help_dispatch_independent_gates_v1(integer)'::regprocedure)
      INTO v_transport;
    IF position('then ''ct.penta.certify-review''' in lower(v_transport)) = 0 THEN
      RAISE EXCEPTION 'PENTA_HELP_CERTIFIER_TRANSPORT_ROLLBACK_SOURCE_DRIFT';
    END IF;
    v_transport := replace(
      v_transport,
      'then ''ct.penta.certify-review''',
      'then ''ct.penta.certify'''
    );
    EXECUTE v_transport;
    SELECT pg_get_functiondef('public.penta_help_dispatch_independent_gates_v1(integer)'::regprocedure)
      INTO v_after;
    IF position('then ''ct.penta.certify''' in lower(v_after)) = 0 THEN
      RAISE EXCEPTION 'PENTA_HELP_CERTIFIER_TRANSPORT_ROLLBACK_READBACK_FAILED';
    END IF;
  END IF;

  IF to_regprocedure('public.penta_help_independent_gate_review_preflight_v1(uuid,text)') IS NOT NULL THEN
    SELECT pg_get_functiondef('public.penta_help_independent_gate_review_preflight_v1(uuid,text)'::regprocedure)
      INTO v_preflight;
    IF position('''ct.penta.certify-review''' in lower(v_preflight)) = 0 THEN
      RAISE EXCEPTION 'PENTA_HELP_CERTIFIER_PREFLIGHT_ROLLBACK_SOURCE_DRIFT';
    END IF;
    v_preflight := replace(
      v_preflight,
      '''ct.penta.certify-review''',
      '''ct.penta.certify'''
    );
    EXECUTE v_preflight;
    SELECT pg_get_functiondef('public.penta_help_independent_gate_review_preflight_v1(uuid,text)'::regprocedure)
      INTO v_after;
    IF position('''ct.penta.certify''' in lower(v_after)) = 0 THEN
      RAISE EXCEPTION 'PENTA_HELP_CERTIFIER_PREFLIGHT_ROLLBACK_READBACK_FAILED';
    END IF;
  END IF;
END
$rollback$;