-- COS V1 sprint: bound PentaSELF required-job health reads used by public.cos_v1_status_v3.
--
-- Production pre-state:
--   * penta_self.health_snapshot_v1 SHA-256
--       23a1f6c9315b1bd62a5032e3d59ab4895fbf9e9e5434bfc4aa459cdcb69e0f78
--   * unrecovered-required-job predicate scanned cron.job_run_details broadly
--     (~257k rows observed, 18,502 shared blocks read) and action_receipts_v1
--     sequentially (~31k rows), taking ~213 ms in the isolated predicate.
--   * penta_self.health_snapshot_v1 measured ~1.2 s and public.penta_self_status_v1
--     materially dominated COS status latency.
--
-- pg_cron owns cron.job_run_details, so CrownThrive does not ALTER/INDEX that table.
-- Instead, read a bounded newest-runid window through its existing PK, prove that
-- the window covers the complete trailing 30 minutes, derive latest-per-job once,
-- and fail closed (-1) if coverage is ever insufficient. The owned recovery
-- receipt table gets a selective composite index for its anti-join predicate.
-- No history deletion, provider authority, money, rights, credential, or D3 effect.

DO $preflight$
DECLARE
  v_sha text;
BEGIN
  IF to_regclass('cron.job_run_details') IS NULL THEN
    RAISE EXCEPTION 'cron_job_run_details_missing';
  END IF;
  IF to_regclass('penta_self.action_receipts_v1') IS NULL THEN
    RAISE EXCEPTION 'penta_self_action_receipts_v1_missing';
  END IF;

  SELECT encode(extensions.digest(pg_get_functiondef(p.oid),'sha256'),'hex')
    INTO v_sha
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='penta_self' AND p.proname='health_snapshot_v1'
  LIMIT 1;

  IF v_sha IS DISTINCT FROM '23a1f6c9315b1bd62a5032e3d59ab4895fbf9e9e5434bfc4aa459cdcb69e0f78' THEN
    RAISE EXCEPTION 'health_snapshot_v1_predecessor_digest_mismatch:%',coalesce(v_sha,'NULL');
  END IF;
END
$preflight$;

CREATE INDEX IF NOT EXISTS action_receipts_recover_required_job_idx
  ON penta_self.action_receipts_v1
  (action_key, result_state, target_ref, completed_at DESC);

CREATE OR REPLACE FUNCTION penta_self.health_snapshot_v1()
RETURNS jsonb
LANGUAGE plpgsql
STABLE SECURITY DEFINER
SET search_path TO 'pg_catalog', 'penta_self', 'penta_runtime', 'integration_control', 'chlom_runtime', 'cron', 'public'
AS $function$
declare
 v_required int; v_active int; v_missing int; v_unrecovered_fail int; v_degraded_agents int;
 v_failed_tasks int; v_blocked_tasks int; v_historical_failed int; v_open_findings int;
 v_fabric text; v_mesh text; v_queue jsonb;
 v_run_window_complete boolean:=false; v_run_window_rows int:=0;
 v_run_window_oldest_start timestamptz; v_run_window_newest_start timestamptz;
begin
 select count(*) into v_required from penta_self.required_jobs_v1 where auto_repair;
 select count(*) into v_active from penta_self.required_jobs_v1 r join cron.job j on j.jobname=r.jobname where r.auto_repair and j.active and j.schedule=r.expected_schedule and j.command=r.expected_command;
 v_missing:=v_required-v_active;

 with recent as materialized (
   select d.runid,d.jobid,d.status,d.start_time
   from cron.job_run_details d
   order by d.runid desc
   limit 10000
 ), coverage as (
   select min(start_time) oldest_start,max(start_time) newest_start,count(*)::int row_count
   from recent
 ), latest_run as (
   select distinct on (jobid) jobid,status,start_time
   from recent
   where start_time>now()-interval '30 minutes'
   order by jobid,start_time desc nulls last
 ), failures as (
   select count(*)::int cnt
   from penta_self.required_jobs_v1 r
   join cron.job j on j.jobname=r.jobname
   left join latest_run d on d.jobid=j.jobid
   where r.auto_repair
     and d.status is not null
     and d.status not in('succeeded','running')
     and not exists(
       select 1
       from penta_self.action_receipts_v1 a
       where a.action_key='recover_failed_required_job'
         and a.target_ref='cron:'||j.jobname
         and a.result_state='applied'
         and a.completed_at>=d.start_time
     )
 )
 select case when c.oldest_start<=now()-interval '30 minutes' then f.cnt else -1 end,
        coalesce(c.oldest_start<=now()-interval '30 minutes',false),
        c.row_count,c.oldest_start,c.newest_start
 into v_unrecovered_fail,v_run_window_complete,v_run_window_rows,
      v_run_window_oldest_start,v_run_window_newest_start
 from coverage c cross join failures f;

 select count(*) into v_degraded_agents from chlom_runtime.agent_health where health_state in('degraded','failed','critical') and updated_at>now()-interval '1 hour';
 select count(*) filter(where state='failed'),count(*) filter(where state='blocked') into v_failed_tasks,v_blocked_tasks from public.penta_certify_current_tasks_v1();
 select count(*) into v_historical_failed from integration_control.penta_certify_tasks_v3 where state='failed';
 select count(*) into v_open_findings from penta_self.findings_v1 where state in('open','delegated') and detected_at>now()-interval '1 hour';
 select lifecycle_state into v_fabric from penta_runtime.fabrics_v1 where fabric_id='ct.fabric.penta.v1';
 select lifecycle_state into v_mesh from penta_runtime.fabrics_v1 where fabric_id='ct.mesh.penta.v1';
 select jsonb_object_agg(certification_state,cnt) into v_queue from (select certification_state,count(*) cnt from public.ct_factory_adapter_certification_queue group by certification_state)s;
 return jsonb_build_object(
   'phase',3,'production',true,'required_jobs',v_required,'healthy_required_jobs',v_active,'scheduler_gaps',v_missing,
   'unrecovered_required_job_failures_30m',v_unrecovered_fail,
   'required_job_run_window_complete',v_run_window_complete,
   'required_job_run_window_rows',v_run_window_rows,
   'required_job_run_window_oldest_start',v_run_window_oldest_start,
   'required_job_run_window_newest_start',v_run_window_newest_start,
   'degraded_agents_1h',v_degraded_agents,
   'failed_certification_tasks',v_failed_tasks,'blocked_certification_tasks',v_blocked_tasks,
   'historical_failed_certification_attempts',v_historical_failed,
   'certification_task_projection','latest_generation_current_history_preserved',
   'open_or_delegated_findings_1h',v_open_findings,'fabric_state',v_fabric,'mesh_state',v_mesh,
   'provider_certification_queue',coalesce(v_queue,'{}'::jsonb),'authority_manufacture',false,'d3_human_reserved',true,'generated_at',now()
 );
end
$function$;

DO $verify$
DECLARE
  v_sha text;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='penta_self' AND tablename='action_receipts_v1'
      AND indexname='action_receipts_recover_required_job_idx'
  ) THEN
    RAISE EXCEPTION 'action_receipts_recover_required_job_idx_missing';
  END IF;

  SELECT encode(extensions.digest(pg_get_functiondef(p.oid),'sha256'),'hex')
    INTO v_sha
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='penta_self' AND p.proname='health_snapshot_v1'
  LIMIT 1;

  IF v_sha IS NULL OR v_sha='23a1f6c9315b1bd62a5032e3d59ab4895fbf9e9e5434bfc4aa459cdcb69e0f78' THEN
    RAISE EXCEPTION 'health_snapshot_v1_digest_not_advanced';
  END IF;
END
$verify$;

-- Rollback target: predecessor penta_self.health_snapshot_v1 SHA-256
-- 23a1f6c9315b1bd62a5032e3d59ab4895fbf9e9e5434bfc4aa459cdcb69e0f78
-- and DROP INDEX IF EXISTS penta_self.action_receipts_recover_required_job_idx;
