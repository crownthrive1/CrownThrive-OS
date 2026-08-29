-- Reconcile stale PentaSELF projection problems without erasing historical evidence.
-- Current provider/runtime failures remain open. Only superseded observations are resolved.

create table if not exists integration_control.os_phase_projection_v1 (
  projection_key text primary key,
  canonical_institutional_phase text not null,
  founder_operating_label text not null,
  public_rollout_state text not null,
  production_state text not null,
  source_of_truth text not null,
  metadata jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table integration_control.os_phase_projection_v1 enable row level security;
revoke all on integration_control.os_phase_projection_v1 from public,anon,authenticated;
grant select,insert,update on integration_control.os_phase_projection_v1 to service_role;
drop policy if exists os_phase_projection_service_role_v1 on integration_control.os_phase_projection_v1;
create policy os_phase_projection_service_role_v1 on integration_control.os_phase_projection_v1 for all to service_role using (true) with check (true);

insert into integration_control.os_phase_projection_v1(
 projection_key,canonical_institutional_phase,founder_operating_label,public_rollout_state,production_state,source_of_truth,metadata)
values(
 'crownthrive-os.current','Phase 3 — Execute','Phase 3.5 — convergence and hardening','separate_from_institutional_phase','PRODUCTION ACTIVE — OPERATIONALLY DEGRADED','ThriveBase/CHLOM/DAIL/GitHub/provider readback',
 jsonb_build_object('phase_conflation_forbidden',true,'phase4_not_claimed',true,'updated_by','PentaStatus/PentaScribe/PentaSELF'))
on conflict(projection_key) do update set
 canonical_institutional_phase=excluded.canonical_institutional_phase,
 founder_operating_label=excluded.founder_operating_label,
 public_rollout_state=excluded.public_rollout_state,
 production_state=excluded.production_state,
 source_of_truth=excluded.source_of_truth,
 metadata=integration_control.os_phase_projection_v1.metadata||excluded.metadata,
 observed_at=now(),updated_at=now();

update penta_self.problem_ledger_v1
set state='resolved',resolved_at=coalesce(resolved_at,now()),
    verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object(
      'resolved_by','penta_self_stale_projection_reconciliation_v2',
      'evidence','Locticians campaign/event-ledger reconciliation and production sends were established by merged PRs 745/747/750',
      'stale_projection_retired',true,'verified_at',now()),updated_at=now()
where title='PentaMarketer summary contradicts its event ledger'
  and state not in ('resolved','closed','superseded','cancelled');

update penta_self.problem_ledger_v1
set state='resolved',resolved_at=coalesce(resolved_at,now()),
    verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object(
      'resolved_by','penta_self_stale_projection_reconciliation_v2',
      'failed_head_sha',evidence->>'head_sha',
      'newer_verified_main_sha','3bd2cd33ea6d83e7d93aee15e9757d59bfb6ab20',
      'newer_main_vercel_state','READY production',
      'old_exact_head_no_longer_current',true,'verified_at',now()),updated_at=now()
where title='PentaRelease exact-head workflow failed on current main'
  and coalesce(evidence->>'head_sha','')='a12ce059d68a042665a1f1ec4d5f6e08bd69b478'
  and state not in ('resolved','closed','superseded','cancelled');

update penta_self.problem_ledger_v1
set state='resolved',resolved_at=coalesce(resolved_at,now()),
    verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object(
      'resolved_by','penta_self_stale_projection_reconciliation_v2',
      'canonical_phase','Phase 3 — Execute',
      'founder_operating_label','Phase 3.5 — convergence and hardening',
      'public_rollout_field','separate_from_institutional_phase',
      'projection_key','crownthrive-os.current','verified_at',now()),updated_at=now()
where title='Public rollout language and OS institutional phase remain conflated'
  and state not in ('resolved','closed','superseded','cancelled');

with required_health as (
 select bool_and(x.status='succeeded') as healthy,max(x.start_time) as verified_at
 from (
   select distinct on (j.jobname) j.jobname,d.status,d.start_time
   from cron.job j join cron.job_run_details d on d.jobid=j.jobid
   where j.jobname in ('ct-software-factory-continuity-v5','ct-penta-self-v1','ct-penta-self-continuous-healing-v1','penta-persona-execution-v1')
   order by j.jobname,d.start_time desc
 ) x
)
update penta_self.problem_ledger_v1 p
set state='resolved',resolved_at=coalesce(p.resolved_at,now()),
    verification_evidence=coalesce(p.verification_evidence,'{}'::jsonb)||jsonb_build_object(
      'resolved_by','penta_self_stale_projection_reconciliation_v2',
      'required_runtime_jobs_latest_state','succeeded','verified_at',h.verified_at,
      'raw_secret_material_preserved',false),updated_at=now()
from required_health h
where p.title='PentaFabric problem event' and h.healthy=true
  and p.state not in ('resolved','closed','superseded','cancelled');

select chlom_runtime.append_dail_event(
 'pentaself.stale_projection.reconciled','production_convergence','ct.penta.self.continuous-healing.v1',
 jsonb_build_object('resolved_titles',jsonb_build_array('PentaMarketer summary contradicts its event ledger','PentaRelease exact-head workflow failed on current main','Public rollout language and OS institutional phase remain conflated','PentaFabric problem event'),'phase_projection_key','crownthrive-os.current','stale_failure_overwrite_forbidden',true,'authority_created',false,'observed_at',now()),
 'PentaSELF/PentaStatus/PentaScribe',null,'PentaSELF','2.0.0','pentaself-stale-projection-reconciliation-v2',null,'ct.penta.self.continuous-healing.v1',null,'internal'
);
