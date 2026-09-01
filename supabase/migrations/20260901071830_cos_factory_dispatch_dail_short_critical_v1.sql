-- COS V1 sprint repair: keep expensive factory/network work before the final PentaWire DAIL append.
-- Exact predecessor digests are pinned so this fails closed on source/runtime drift.

DO $$
DECLARE
  v_tick_sha text;
  v_dispatch_sha text;
BEGIN
  SELECT encode(digest(pg_get_functiondef('public.ct_factory_tick()'::regprocedure),'sha256'),'hex') INTO v_tick_sha;
  SELECT encode(digest(pg_get_functiondef('public.ct_factory_dispatch_tick()'::regprocedure),'sha256'),'hex') INTO v_dispatch_sha;

  IF v_tick_sha <> 'a81b09ef6c251159636087d00a95885143a6afc79bf7a538f5ddd68cf10fb747' THEN
    RAISE EXCEPTION 'CT_FACTORY_TICK_PREDECESSOR_DIGEST_MISMATCH:%', v_tick_sha;
  END IF;
  IF v_dispatch_sha <> 'f4cd905529ab9c3b65088245ddb57a441a0f86315c67c7c650cb90678928e394' THEN
    RAISE EXCEPTION 'CT_FACTORY_DISPATCH_TICK_PREDECESSOR_DIGEST_MISMATCH:%', v_dispatch_sha;
  END IF;
END
$$;

CREATE OR REPLACE FUNCTION public.ct_factory_tick()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  v_request uuid;
  v_run uuid;
  v_ready integer:=0;
  v_exact jsonb;
  v_police jsonb;
  v_wire jsonb;
BEGIN
  -- Compute/reconcile expensive local work first. PentaWire is intentionally last because
  -- penta_wire_scan_v1() performs the canonical DAIL append near its return boundary.
  BEGIN
    v_police:=integration_control.penta_police_reconcile_v1();
  EXCEPTION WHEN OTHERS THEN
    v_police:=jsonb_build_object('state','isolated_penta_police_error','error_class',sqlstate,'factory_tick_preserved',true);
  END;

  SELECT r.id INTO v_request
  FROM public.ct_factory_build_requests r
  JOIN public.ct_factory_projects p ON p.id=r.project_id
  WHERE r.status='queued' AND p.autonomy_enabled=true
  ORDER BY r.priority ASC,r.created_at ASC
  FOR UPDATE SKIP LOCKED
  LIMIT 1;

  IF v_request IS NOT NULL THEN
    v_run:=public.ct_factory_seed_run(v_request);
  END IF;

  UPDATE public.ct_factory_work_units w
  SET status='ready'
  WHERE w.status='queued'
    AND NOT EXISTS(
      SELECT 1
      FROM public.ct_factory_work_units prior
      WHERE prior.build_run_id=w.build_run_id
        AND prior.ordinal<w.ordinal
        AND prior.status NOT IN ('passed','skipped')
    );
  GET DIAGNOSTICS v_ready=ROW_COUNT;

  BEGIN
    v_exact:=integration_control.pentafactory_exact_evidence_tick_v1('5d942b82-431b-4ca1-a93a-e0bf852ee8f4'::uuid);
  EXCEPTION WHEN OTHERS THEN
    v_exact:=jsonb_build_object('state','isolated_exact_evidence_error','error_class',sqlstate,'factory_tick_preserved',true);
  END;

  -- Final evidence/reconciliation step. penta_wire_scan_v1() appends DAIL at the end of
  -- its own work, leaving only bounded local event/write + return work in this transaction.
  BEGIN
    v_wire:=integration_control.penta_wire_tick_v1();
  EXCEPTION WHEN OTHERS THEN
    v_wire:=jsonb_build_object('state','isolated_penta_wire_error','error_class',sqlstate,'factory_tick_preserved',true);
  END;

  INSERT INTO public.ct_factory_events(event_type,entity_type,payload)
  VALUES('factory.tick','factory',jsonb_build_object(
    'seeded_run',v_run,
    'newly_ready',v_ready,
    'penta_police',v_police,
    'penta_wire',v_wire,
    'exact_evidence',v_exact
  ));

  RETURN jsonb_build_object(
    'seeded_run',v_run,
    'newly_ready',v_ready,
    'penta_police',v_police,
    'penta_wire',v_wire,
    'exact_evidence',v_exact,
    'at',now()
  );
END
$function$;

CREATE OR REPLACE FUNCTION public.ct_factory_dispatch_tick()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_catalog'
AS $function$
DECLARE
  v_tick jsonb;
  v_dispatch jsonb;
BEGIN
  -- Provider/network dispatch happens before any factory-side DAIL append can occur.
  v_dispatch:=public.ct_factory_dispatch_worker(8);
  v_tick:=public.ct_factory_tick();
  RETURN jsonb_build_object('tick',v_tick,'dispatch',v_dispatch,'at',now());
END
$function$;

COMMENT ON FUNCTION public.ct_factory_tick() IS
  'COS sprint v1: expensive factory work precedes final PentaWire DAIL append; preserves factory semantics and fail-isolated sublanes.';
COMMENT ON FUNCTION public.ct_factory_dispatch_tick() IS
  'COS sprint v1: provider dispatch executes before factory reconciliation so no network wait occurs after the known PentaWire DAIL append.';

DO $$
DECLARE
  v_tick_def text:=pg_get_functiondef('public.ct_factory_tick()'::regprocedure);
  v_dispatch_def text:=pg_get_functiondef('public.ct_factory_dispatch_tick()'::regprocedure);
BEGIN
  IF position('pentafactory_exact_evidence_tick_v1' in v_tick_def)=0
     OR position('penta_wire_tick_v1' in v_tick_def)=0
     OR position('pentafactory_exact_evidence_tick_v1' in v_tick_def) >= position('penta_wire_tick_v1' in v_tick_def) THEN
    RAISE EXCEPTION 'CT_FACTORY_TICK_DAIL_ORDER_VERIFY_FAILED';
  END IF;

  IF position('ct_factory_dispatch_worker' in v_dispatch_def)=0
     OR position('ct_factory_tick' in v_dispatch_def)=0
     OR position('ct_factory_dispatch_worker' in v_dispatch_def) >= position('ct_factory_tick' in v_dispatch_def) THEN
    RAISE EXCEPTION 'CT_FACTORY_DISPATCH_PROVIDER_ORDER_VERIFY_FAILED';
  END IF;
END
$$;