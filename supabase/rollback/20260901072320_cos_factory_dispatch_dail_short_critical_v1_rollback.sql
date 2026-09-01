-- Roll back COS factory DAIL ordering repair to the exact predecessor behavior.

CREATE OR REPLACE FUNCTION public.ct_factory_tick()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
declare v_request uuid; v_run uuid; v_ready integer:=0; v_exact jsonb; v_police jsonb; v_wire jsonb;
begin
 begin v_police:=integration_control.penta_police_reconcile_v1(); exception when others then v_police:=jsonb_build_object('state','isolated_penta_police_error','error_class',sqlstate,'factory_tick_preserved',true); end;
 begin v_wire:=integration_control.penta_wire_tick_v1(); exception when others then v_wire:=jsonb_build_object('state','isolated_penta_wire_error','error_class',sqlstate,'factory_tick_preserved',true); end;
 select r.id into v_request from public.ct_factory_build_requests r join public.ct_factory_projects p on p.id=r.project_id where r.status='queued' and p.autonomy_enabled=true order by r.priority asc,r.created_at asc for update skip locked limit 1;
 if v_request is not null then v_run:=public.ct_factory_seed_run(v_request); end if;
 update public.ct_factory_work_units w set status='ready' where w.status='queued' and not exists(select 1 from public.ct_factory_work_units prior where prior.build_run_id=w.build_run_id and prior.ordinal<w.ordinal and prior.status not in ('passed','skipped')); get diagnostics v_ready=row_count;
 begin v_exact:=integration_control.pentafactory_exact_evidence_tick_v1('5d942b82-431b-4ca1-a93a-e0bf852ee8f4'::uuid); exception when others then v_exact:=jsonb_build_object('state','isolated_exact_evidence_error','error_class',sqlstate,'factory_tick_preserved',true); end;
 insert into public.ct_factory_events(event_type,entity_type,payload) values('factory.tick','factory',jsonb_build_object('seeded_run',v_run,'newly_ready',v_ready,'penta_police',v_police,'penta_wire',v_wire,'exact_evidence',v_exact));
 return jsonb_build_object('seeded_run',v_run,'newly_ready',v_ready,'penta_police',v_police,'penta_wire',v_wire,'exact_evidence',v_exact,'at',now());
end $function$;

CREATE OR REPLACE FUNCTION public.ct_factory_dispatch_tick()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_catalog'
AS $function$
declare v_tick jsonb; v_dispatch jsonb; begin v_tick:=public.ct_factory_tick(); v_dispatch:=public.ct_factory_dispatch_worker(8); return jsonb_build_object('tick',v_tick,'dispatch',v_dispatch,'at',now()); end $function$;

COMMENT ON FUNCTION public.ct_factory_tick() IS NULL;
COMMENT ON FUNCTION public.ct_factory_dispatch_tick() IS NULL;
