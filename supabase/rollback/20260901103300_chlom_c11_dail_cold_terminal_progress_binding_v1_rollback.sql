-- Security-preserving rollback for CHLOM C11 terminal-progress binding v1.
-- Removes the v3 due wrapper and v2 terminal wrapper, restores service-role access
-- to the already fail-closed v1 completion function, and returns due generation to v2.

do $block$
declare v_job bigint;
begin
  select jobid into v_job from cron.job where jobname='ct-dail-cold-checkpoint-due-v1' limit 1;
  if v_job is not null then perform cron.unschedule(v_job); end if;
  perform cron.schedule(
    'ct-dail-cold-checkpoint-due-v1',
    '17 * * * *',
    'select chlom_runtime.enqueue_dail_cold_checkpoint_v2(false);'
  );
end
$block$;

drop function if exists chlom_runtime.enqueue_dail_cold_checkpoint_v3(boolean);
drop function if exists chlom_runtime.complete_dail_cold_checkpoint_v2(uuid,text,text,text,text,text,bigint,timestamptz,jsonb,jsonb);

grant execute on function chlom_runtime.complete_dail_cold_checkpoint_v1(uuid,text,text,text,text,text,bigint,timestamptz,jsonb,jsonb) to service_role;

-- Historical jobs/evidence are retained. The resume/privacy hardening remains active.
