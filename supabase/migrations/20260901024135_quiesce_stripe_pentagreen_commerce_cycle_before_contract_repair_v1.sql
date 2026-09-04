
update integration_control.scheduler_desired_jobs_v2
set active=false,
    allow_auto_restore=false,
    generation=greatest(generation,202609010400),
    source_ref='ct.binding.pentagreen-stripe-mesh.v3',
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'quiesced_for','stripe_runtime_contract_repair_v1',
      'quiesced_at',clock_timestamp(),
      'scope','ct-pentagreen-commerce-mesh-cycle-v1',
      'webhook_and_catalog_sync_unaffected',true,
      'authority_created',false
    ),
    updated_at=clock_timestamp()
where jobname='ct-pentagreen-commerce-mesh-cycle-v1';

do $do$
declare r record;
begin
  for r in
    select jobid
    from cron.job
    where jobname='ct-pentagreen-commerce-mesh-cycle-v1'
      and command='select integration_control.thriveevergreen_commerce_mesh_cycle_v1();'
  loop
    perform cron.unschedule(r.jobid);
  end loop;
end
$do$;
