-- Security-preserving rollback for CHLOM C11 DAIL cold checkpoint resume/privacy hardening v1.
-- Removes only durable-resume wrapper/progress state machinery and returns due generation
-- to the v1 queue function. The hardened lineage-only export remains in place so rollback
-- does not reintroduce provider exposure of DAIL payload bodies.

do $block$
declare v_job bigint;
begin
  select jobid into v_job from cron.job where jobname='ct-dail-cold-checkpoint-due-v1' limit 1;
  if v_job is not null then perform cron.unschedule(v_job); end if;
  perform cron.schedule(
    'ct-dail-cold-checkpoint-due-v1',
    '17 * * * *',
    'select chlom_runtime.enqueue_dail_cold_checkpoint_v1(false);'
  );
end
$block$;

drop function if exists chlom_runtime.enqueue_dail_cold_checkpoint_v2(boolean);
drop function if exists chlom_runtime.record_dail_cold_export_progress_v1(uuid,bigint,integer,text,bigint,text);

-- Deliberately retain the hardened public.dail_cold_checkpoint_export_chunk_v1 definition
-- that excludes payload bodies. The first migration rollback removes that function if the
-- whole C11 capability is reverted.
