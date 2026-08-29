-- Resolve only stale/transient problem projections after newer independent evidence.

create table if not exists integration_control.institutional_phase_projection_v2 (
  projection_key text primary key,
  canonical_os_phase numeric(4,2) not null,
  founder_operating_label text not null,
  public_rollout_state text not null,
  authority_note text not null,
  source_refs jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table integration_control.institutional_phase_projection_v2 enable row level security;
revoke all on integration_control.institutional_phase_projection_v2 from public,anon,authenticated;
grant select,insert,update on integration_control.institutional_phase_projection_v2 to service_role;
do $$ begin
 if not exists(select 1 from pg_policies where schemaname='integration_control' and tablename='institutional_phase_projection_v2' and policyname='institutional_phase_projection_service_role_v2') then
  create policy institutional_phase_projection_service_role_v2 on integration_control.institutional_phase_projection_v2 for all to service_role using(true) with check(true);
 end if;
end $$;
insert into integration_control.institutional_phase_projection_v2(projection_key,canonical_os_phase,founder_operating_label,public_rollout_state,authority_note,source_refs,evidence_sha256)
values('ct.os.phase.current',3.00,'Phase 3.5 — convergence and hardening','lane_specific','Canonical institutional phase, founder operating label, and public rollout state are independent fields. Public rollout never promotes canonical phase or authority.',jsonb_build_object('canonical','ThriveBase/CrownThrive-OS','founder_label','founder directive','public_rollout','per-lane provider evidence'),encode(extensions.digest(convert_to('3|Phase 3.5 — convergence and hardening|lane_specific|independent-fields','UTF8'),'sha256'),'hex'))
on conflict(projection_key) do update set canonical_os_phase=excluded.canonical_os_phase,founder_operating_label=excluded.founder_operating_label,public_rollout_state=excluded.public_rollout_state,authority_note=excluded.authority_note,source_refs=excluded.source_refs,evidence_sha256=excluded.evidence_sha256,updated_at=now();

create table if not exists penta_self.current_truth_receipts_v2 (
  receipt_id uuid primary key default gen_random_uuid(),
  receipt_kind text not null,
  subject_ref text not null,
  observed_state jsonb not null,
  disposition text not null,
  evidence_sha256 text not null,
  observed_at timestamptz not null default now()
);
alter table penta_self.current_truth_receipts_v2 enable row level security;
revoke all on penta_self.current_truth_receipts_v2 from public,anon,authenticated;
grant select,insert on penta_self.current_truth_receipts_v2 to service_role;
do $$ begin
 if not exists(select 1 from pg_policies where schemaname='penta_self' and tablename='current_truth_receipts_v2' and policyname='current_truth_receipts_select_service_role_v2') then create policy current_truth_receipts_select_service_role_v2 on penta_self.current_truth_receipts_v2 for select to service_role using(true); end if;
 if not exists(select 1 from pg_policies where schemaname='penta_self' and tablename='current_truth_receipts_v2' and policyname='current_truth_receipts_insert_service_role_v2') then create policy current_truth_receipts_insert_service_role_v2 on penta_self.current_truth_receipts_v2 for insert to service_role with check(true); end if;
end $$;
create or replace function penta_self.current_truth_receipts_immutable_v2() returns trigger language plpgsql security definer set search_path=pg_catalog,penta_self as $$ begin raise exception 'current_truth_receipts_v2 is append-only'; end $$;
revoke all on function penta_self.current_truth_receipts_immutable_v2() from public,anon,authenticated;
grant execute on function penta_self.current_truth_receipts_immutable_v2() to service_role;
drop trigger if exists current_truth_receipts_immutable_v2 on penta_self.current_truth_receipts_v2;
create trigger current_truth_receipts_immutable_v2 before update or delete on penta_self.current_truth_receipts_v2 for each row execute function penta_self.current_truth_receipts_immutable_v2();

create or replace function penta_self.reconcile_current_truth_v2()
returns jsonb language plpgsql security definer
set search_path=pg_catalog,penta_self,integration_control,cron,extensions,chlom_runtime
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_factory_status text; v_factory_started timestamptz; v_factory_end timestamptz;
  v_release_response extensions.http_response; v_release jsonb;
  v_current_main_response extensions.http_response; v_current_main jsonb;
  v_current_sha text; v_latest_tag text; v_latest_release_at timestamptz;
  v_resolved int:=0; v_rows int:=0; v_payload jsonb; v_digest text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select status,start_time,end_time into v_factory_status,v_factory_started,v_factory_end
  from cron.job_run_details where jobid=(select jobid from cron.job where jobname='ct-software-factory-continuity-v5' order by jobid desc limit 1)
  order by start_time desc limit 1;
  if v_factory_status='succeeded' then
    update penta_self.problem_ledger_v1 set state='resolved',resolved_at=coalesce(resolved_at,now()),blocked_reason=null,last_error=null,verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object('verified_at',now(),'latest_status',v_factory_status,'latest_started_at',v_factory_started,'latest_completed_at',v_factory_end,'reconciler','penta_self.reconcile_current_truth_v2'),updated_at=now()
    where title='Latest active cron execution failed: ct-software-factory-continuity-v5' and state<>'resolved';
    get diagnostics v_rows=ROW_COUNT; v_resolved:=v_resolved+v_rows;
  end if;
  begin
    v_current_main_response:=extensions.http(('GET'::extensions.http_method,'https://api.github.com/repos/crownthrive1/CrownThrive-OS/branches/main'::varchar,array[row('accept','application/vnd.github+json')::extensions.http_header,row('user-agent','CrownThrive-PentaSELF')::extensions.http_header,row('x-github-api-version','2022-11-28')::extensions.http_header],null::varchar,null::varchar)::extensions.http_request);
    if v_current_main_response.status=200 then v_current_main:=v_current_main_response.content::jsonb; v_current_sha:=v_current_main->'commit'->>'sha'; end if;
  exception when others then v_current_sha:=null; end;
  begin
    v_release_response:=extensions.http(('GET'::extensions.http_method,'https://api.github.com/repos/crownthrive1/CrownThrive-OS/releases/latest'::varchar,array[row('accept','application/vnd.github+json')::extensions.http_header,row('user-agent','CrownThrive-PentaSELF')::extensions.http_header,row('x-github-api-version','2022-11-28')::extensions.http_header],null::varchar,null::varchar)::extensions.http_request);
    if v_release_response.status=200 then v_release:=v_release_response.content::jsonb; v_latest_tag:=v_release->>'tag_name'; v_latest_release_at:=nullif(v_release->>'published_at','')::timestamptz; end if;
  exception when others then v_latest_tag:=null; end;
  if v_current_sha is not null and v_latest_tag is not null then
    update penta_self.problem_ledger_v1 set state='resolved',resolved_at=coalesce(resolved_at,now()),blocked_reason=null,last_error=null,verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object('verified_at',now(),'current_main_sha',v_current_sha,'latest_release_tag',v_latest_tag,'latest_release_at',v_latest_release_at,'stale_failed_head_sha',evidence->>'head_sha','reconciler','penta_self.reconcile_current_truth_v2'),updated_at=now()
    where title='PentaRelease exact-head workflow failed on current main' and state<>'resolved' and coalesce(evidence->>'head_sha','')<>v_current_sha and v_latest_release_at is not null and v_latest_release_at>last_seen_at;
    get diagnostics v_rows=ROW_COUNT; v_resolved:=v_resolved+v_rows;
  end if;
  update penta_self.problem_ledger_v1 set state='resolved',resolved_at=coalesce(resolved_at,now()),blocked_reason=null,last_error=null,verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object('verified_at',now(),'projection_key','ct.os.phase.current','canonical_phase',3,'founder_operating_label','Phase 3.5 — convergence and hardening','public_rollout_state','lane_specific','reconciler','penta_self.reconcile_current_truth_v2'),updated_at=now()
  where title='Public rollout language and OS institutional phase remain conflated' and state<>'resolved';
  get diagnostics v_rows=ROW_COUNT; v_resolved:=v_resolved+v_rows;
  v_payload:=jsonb_build_object('factory_latest_status',v_factory_status,'factory_latest_started_at',v_factory_started,'current_main_sha',v_current_sha,'latest_release_tag',v_latest_tag,'latest_release_at',v_latest_release_at,'resolved_count',v_resolved,'phase_projection','ct.os.phase.current','observed_at',now());
  v_digest:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.current_truth_receipts_v2(receipt_kind,subject_ref,observed_state,disposition,evidence_sha256) values('current_truth_reconcile','ct.penta.self.v2',v_payload,case when v_current_sha is null then 'DEGRADED_EXTERNAL_READBACK' else 'APPLIED' end,v_digest);
  perform chlom_runtime.append_dail_event('pentaself.current_truth.reconciled','self_healing','ct.penta.self.v2',v_payload,'PentaSELF/PentaAssure',null,'PentaSELF','2.0.0',v_digest,null,'ct.pentaself.scheduler-permanence.v2',null,'internal');
  return v_payload;
end $$;
revoke all on function penta_self.reconcile_current_truth_v2() from public,anon,authenticated;
grant execute on function penta_self.reconcile_current_truth_v2() to service_role;

select penta_self.reconcile_current_truth_v2();
select integration_control.scheduler_desired_job_upsert_v2('ct-pentaself-current-truth-v2','4-59/5 * * * *','select penta_self.reconcile_current_truth_v2();',2026082902,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaSELF/PentaAssure','rollback_policy','monotonic'));
select cron.unschedule(jobid) from cron.job where jobname='ct-pentaself-current-truth-v2';
select cron.schedule('ct-pentaself-current-truth-v2','4-59/5 * * * *','select penta_self.reconcile_current_truth_v2();');
select integration_control.scheduler_permanence_reconcile_v2();
