-- Rollback for CHLOM C11 DAIL cold checkpoint connector protocol v1.
-- Preserves historical checkpoint/backup rows; removes only introduced runtime surfaces
-- and the internal due-generation cron. It does not delete evidence.

do $block$
declare v_job bigint;
begin
  select jobid into v_job from cron.job where jobname='ct-dail-cold-checkpoint-due-v1' limit 1;
  if v_job is not null then perform cron.unschedule(v_job); end if;
end
$block$;

drop function if exists chlom_runtime.complete_dail_cold_checkpoint_v1(uuid,text,text,text,text,text,bigint,timestamptz,jsonb,jsonb);
drop function if exists public.dail_cold_checkpoint_export_chunk_v1(uuid,bigint,integer);
drop function if exists chlom_runtime.enqueue_dail_cold_checkpoint_v1(boolean);
drop function if exists chlom_runtime.record_dail_cold_checkpoint_v2(text,bigint,bigint,text,timestamptz,text,text,text,bigint,text,text,boolean,boolean,boolean,text,text,uuid);

-- Existing chlom_runtime.record_dail_cold_checkpoint_v1, cold checkpoint history,
-- recovery-drill history, generic midnight backup jobs, and External Evidence Relay
-- connector topology remain untouched.
