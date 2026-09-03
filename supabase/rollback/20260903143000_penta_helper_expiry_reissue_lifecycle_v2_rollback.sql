-- Fail-closed rollback for 20260903143000_penta_helper_expiry_reissue_lifecycle_v2.sql.
-- Restores pre-change reconcile/liaison behavior while retaining a disabled reaper identity for lineage.

CREATE OR REPLACE FUNCTION public.penta_helper_reap_expired_requests_v1(p_limit integer DEFAULT 100)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path TO 'pg_catalog'
AS $function$
SELECT jsonb_build_object(
  'state','rollback_hold',
  'reason','PENTA_HELP_EXPIRY_REAPER_DISABLED_BY_ROLLBACK',
  'expired_requests',0,
  'authority_created',false,
  'semantic_result_created',false,
  'at',clock_timestamp()
);
$function$;
REVOKE ALL ON FUNCTION public.penta_helper_reap_expired_requests_v1(integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.penta_helper_reap_expired_requests_v1(integer) TO service_role;

CREATE OR REPLACE FUNCTION public.penta_liaison_route_v1(
  p_request_id uuid,
  p_destination_kind text DEFAULT NULL::text,
  p_destination_ref text DEFAULT NULL::text,
  p_reason text DEFAULT NULL::text,
  p_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'penta_help'
AS $function$
DECLARE r penta_help.requests_v1%rowtype; v_kind text; v_ref text; v_thread uuid; v_mail uuid; v_subject text; v_body text;
BEGIN
  SELECT * INTO r FROM penta_help.requests_v1 WHERE request_id=p_request_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'PENTA_HELP_REQUEST_NOT_FOUND'; END IF;
  v_kind:=coalesce(nullif(p_destination_kind,''),CASE WHEN r.risk_class='D3' OR r.resolution_mode='human_governance' THEN 'founder' WHEN r.blocker_class='provider' THEN 'provider' ELSE 'penta' END);
  v_ref:=coalesce(nullif(p_destination_ref,''),CASE WHEN v_kind='founder' THEN 'PentaMail owner route' WHEN v_kind='provider' THEN coalesce(r.context->>'provider_system',r.source_ref) ELSE CASE r.blocker_class WHEN 'software' THEN 'penta.build' WHEN 'credential' THEN 'penta.credentials' WHEN 'evidence' THEN 'penta.certify' ELSE 'penta.self' END END);
  INSERT INTO penta_help.liaison_threads_v1(request_id,destination_kind,destination_ref,route_key,state,ttyl_at,expires_at,ask,metadata)
  VALUES(r.request_id,v_kind,v_ref,'liaison:'||r.blocker_class,'routed',now()+make_interval(secs=>r.ttyl_seconds),r.expires_at,coalesce(p_reason,r.need),coalesce(p_metadata,'{}'::jsonb)||jsonb_build_object('risk_class',r.risk_class,'authority_required',r.authority_required))
  ON CONFLICT(request_id,destination_kind,destination_ref) DO UPDATE SET ask=excluded.ask,metadata=excluded.metadata,updated_at=now()
  RETURNING thread_id INTO v_thread;
  IF v_kind='founder' OR r.risk_class='D3' OR r.blocker_class IN ('package','governance') THEN
    v_subject:='PentaLiaison: action required — '||r.requester_system_key||' / '||r.blocker_code;
    v_body:='PentaLiaison routed an unresolved dependency.'||E'\n\n'||'Requester: '||r.requester_system_key||E'\n'||'Blocker: '||r.blocker_code||E'\n'||'Need: '||r.need||E'\n'||'Risk: '||r.risk_class||E'\n'||'Authority: '||r.authority_required||E'\n'||'Destination: '||v_ref||E'\n'||'TTL seconds: '||r.ttl_seconds||E'\n'||'TTYL seconds: '||r.ttyl_seconds||E'\n'||'Request ID: '||r.request_id::text||E'\n\n'||'The system remains fail-closed while PentaHelper continues all bounded work it can perform automatically.';
    v_mail:=public.penta_mail_enqueue_with_maker_v1('penta_help_escalation',CASE WHEN r.risk_class='D3' THEN 'HIGH' ELSE 'INFO' END,v_subject,v_body,'penta-liaison:'||r.request_id::text||':'||v_ref,jsonb_build_object('request_id',r.request_id,'thread_id',v_thread,'destination_kind',v_kind,'destination_ref',v_ref,'risk_class',r.risk_class,'authority_required',r.authority_required));
  END IF;
  RETURN jsonb_build_object('state','routed','request_id',r.request_id,'thread_id',v_thread,'destination_kind',v_kind,'destination_ref',v_ref,'mail_message_id',v_mail,'at',now());
END
$function$;
REVOKE ALL ON FUNCTION public.penta_liaison_route_v1(uuid,text,text,text,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.penta_liaison_route_v1(uuid,text,text,text,jsonb) TO service_role;

CREATE OR REPLACE FUNCTION public.penta_helper_reconcile_v1()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'penta_help', 'cron', 'integration_control'
AS $function$
DECLARE v_provider int:=0; v_system int:=0; v_cron int:=0; v_retired int:=0;
BEGIN
 UPDATE penta_help.requests_v1 r SET state='resolved',resolved_at=now(),resolution=r.resolution||jsonb_build_object('reason','provider_certified','at',now()),lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
 FROM public.ct_factory_adapter_certification_queue q
 WHERE r.source_kind='provider_queue' AND r.source_ref=q.surface_id AND r.state NOT IN ('resolved','retired','expired') AND q.certification_state='certified';
 GET DIAGNOSTICS v_provider=ROW_COUNT;
 UPDATE penta_help.requests_v1 r SET state='retired',resolved_at=now(),resolution=r.resolution||jsonb_build_object('reason','provider_retired','at',now()),lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
 FROM public.ct_factory_adapter_certification_queue q
 WHERE r.source_kind='provider_queue' AND r.source_ref=q.surface_id AND r.state NOT IN ('resolved','retired','expired') AND q.candidate_adapter_key LIKE 'retired:%';
 GET DIAGNOSTICS v_retired=ROW_COUNT;
 UPDATE penta_help.requests_v1 r SET state='resolved',resolved_at=now(),resolution=r.resolution||jsonb_build_object('reason','system_production','at',now()),lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
 FROM public.penta_system_registry s
 WHERE r.source_kind='system_maturity' AND r.source_ref=s.system_key AND r.state NOT IN ('resolved','retired','expired') AND s.maturity='production';
 GET DIAGNOSTICS v_system=ROW_COUNT;
 WITH latest AS (SELECT DISTINCT ON(d.jobid) d.jobid,d.status,d.start_time FROM cron.job_run_details d ORDER BY d.jobid,d.start_time DESC)
 UPDATE penta_help.requests_v1 r SET state='resolved',resolved_at=now(),resolution=r.resolution||jsonb_build_object('reason','cron_recovered','at',now()),lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
 FROM cron.job j JOIN latest l USING(jobid)
 WHERE r.source_kind='cron' AND r.source_ref=j.jobname AND r.state NOT IN ('resolved','retired','expired') AND l.status='succeeded' AND l.start_time>=r.created_at;
 GET DIAGNOSTICS v_cron=ROW_COUNT;
 RETURN jsonb_build_object('state','reconciled','provider_resolved',v_provider,'provider_retired',v_retired,'systems_resolved',v_system,'cron_resolved',v_cron,'at',now());
END
$function$;
REVOKE ALL ON FUNCTION public.penta_helper_reconcile_v1() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.penta_helper_reconcile_v1() TO service_role;
