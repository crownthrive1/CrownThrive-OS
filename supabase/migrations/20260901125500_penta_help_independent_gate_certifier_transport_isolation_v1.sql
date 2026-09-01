-- PentaHelp independent-gate PentaCertifier transport isolation v1.
--
-- Root cause: the existing generic Penta v2 factory dispatcher special-cases the canonical
-- `ct.penta.certify` node and may ACK a routed packet as merely
-- `accepted_for_institutional_processing`. That behavior is valid for ordinary institutional
-- packets, but it is NOT a PentaCertifier exact-subject disposition. Routing an
-- `institutional.independent-gate.review.request` directly to that generic node could therefore
-- collapse transport acceptance into terminal packet completion without an independent
-- certificate.
--
-- This migration repairs only the transport address. Independent-gate PentaCertifier work is
-- routed to a distinct bounded `ct.penta.certify-review` node whose endpoint is the existing
-- exact-subject preflight. The node is transport-only and deliberately not a generic factory
-- dispatch target. Preflight/routing NEVER creates PASS, certification, provider write,
-- credentials, money movement, rights, vote/quorum effect, D3, or authority.

DO $transport_isolation$
DECLARE
  v_transport text;
  v_preflight text;
  v_after text;
BEGIN
  IF to_regprocedure('public.penta_help_dispatch_independent_gates_v1(integer)') IS NULL THEN
    RAISE EXCEPTION 'PENTA_HELP_INDEPENDENT_GATE_TRANSPORT_V1_REQUIRED';
  END IF;
  IF to_regprocedure('public.penta_help_independent_gate_review_preflight_v1(uuid,text)') IS NULL THEN
    RAISE EXCEPTION 'PENTA_HELP_INDEPENDENT_GATE_REVIEW_PREFLIGHT_V1_REQUIRED';
  END IF;

  SELECT pg_get_functiondef('public.penta_help_dispatch_independent_gates_v1(integer)'::regprocedure)
    INTO v_transport;
  IF position('then ''ct.penta.certify''' in lower(v_transport)) = 0 THEN
    RAISE EXCEPTION 'PENTA_HELP_CERTIFIER_TRANSPORT_SOURCE_DRIFT';
  END IF;
  v_transport := replace(
    v_transport,
    'then ''ct.penta.certify''',
    'then ''ct.penta.certify-review'''
  );
  EXECUTE v_transport;

  SELECT pg_get_functiondef('public.penta_help_dispatch_independent_gates_v1(integer)'::regprocedure)
    INTO v_after;
  IF position('then ''ct.penta.certify-review''' in lower(v_after)) = 0
     OR position('then ''ct.penta.certify''' in lower(v_after)) > 0 THEN
    RAISE EXCEPTION 'PENTA_HELP_CERTIFIER_TRANSPORT_REWRITE_READBACK_FAILED';
  END IF;

  SELECT pg_get_functiondef('public.penta_help_independent_gate_review_preflight_v1(uuid,text)'::regprocedure)
    INTO v_preflight;
  IF position('''ct.penta.certify''' in lower(v_preflight)) = 0 THEN
    RAISE EXCEPTION 'PENTA_HELP_CERTIFIER_PREFLIGHT_SOURCE_DRIFT';
  END IF;
  v_preflight := replace(
    v_preflight,
    '''ct.penta.certify''',
    '''ct.penta.certify-review'''
  );
  EXECUTE v_preflight;

  SELECT pg_get_functiondef('public.penta_help_independent_gate_review_preflight_v1(uuid,text)'::regprocedure)
    INTO v_after;
  IF position('''ct.penta.certify-review''' in lower(v_after)) = 0
     OR position('''ct.penta.certify''' in lower(v_after)) > 0 THEN
    RAISE EXCEPTION 'PENTA_HELP_CERTIFIER_PREFLIGHT_REWRITE_READBACK_FAILED';
  END IF;
END
$transport_isolation$;

-- Register a distinct exact-review transport address only when absent. It does not replace or
-- mutate the canonical `ct.penta.certify` node. Keeping the identities separate prevents the
-- generic institutional dispatcher from terminally ACKing exact-gate review packets.
INSERT INTO pentas.nodes_v2(
  node_id,display_name,node_class,authority_ceiling,capabilities,topics,endpoint_kind,endpoint_ref,
  health_state,lifecycle_state,queue_depth,metadata)
SELECT
  'ct.penta.certify-review','PentaCertifier Exact-Review Transport','governance','D2',
  array['institutional.independent-gate.review','certification.exact-subject.review.transport']::text[],
  array['certification','independent-review','exact-subject']::text[],
  'internal_sql','public.penta_help_independent_gate_review_preflight_v1(uuid,text)',
  'degraded','active',0,
  jsonb_build_object(
    'contract','ct.penta.help.independent-gate-certifier-transport-isolation.v1',
    'introduced_by','ct.penta.help.independent-gate-certifier-transport-isolation.v1',
    'canonical_owner','penta.certify',
    'transport_only',true,
    'disposition_authority',false,
    'generic_factory_dispatch_allowed',false,
    'terminal_ack_from_transport',false,
    'independent_owner_execution_required',true,
    'authority_created',false,
    'd3_human_reserved',true)
WHERE NOT EXISTS(select 1 from pentas.nodes_v2 where node_id='ct.penta.certify-review');

COMMENT ON FUNCTION public.penta_help_dispatch_independent_gates_v1(integer) IS
'Routes D0-D2 independent-gate requests to isolated exact-review transport nodes. PentaCertifier uses ct.penta.certify-review, never the generic ct.penta.certify institutional dispatcher. Transport never creates a gate disposition.';

COMMENT ON FUNCTION public.penta_help_independent_gate_review_preflight_v1(uuid,text) IS
'Validates exact PentaHelp independent-gate packets for isolated review-node consumption. READY_FOR_INDEPENDENT_REVIEW is transport readiness only and never PASS/certification.';