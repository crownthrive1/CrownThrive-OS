-- Make the Stripe catalog crosswalk deterministic.
-- Custody copies and product-specific Stripe credentials are not independent
-- candidates for platform-catalog reads. Select the canonical platform alias only.

do $patch$
declare
  v_def text;
  v_old text := 'select count(*),max(decrypted_secret) into v_secret_count,v_secret from vault.decrypted_secrets where lower(name) like ''%stripe%'' and decrypted_secret like ''sk_live_%'';';
  v_new text := 'select count(*),max(decrypted_secret) into v_secret_count,v_secret from vault.decrypted_secrets where name=''stripe_server_api_key'' and decrypted_secret like ''sk_live_%'';';
begin
  select pg_get_functiondef('integration_control.stripe_catalog_crosswalk_refresh_v2()'::regprocedure)
  into v_def;
  if position(v_old in v_def)=0 then
    raise exception 'stripe_crosswalk_expected_source_not_found';
  end if;
  execute replace(v_def,v_old,v_new);
end
$patch$;

comment on function integration_control.stripe_catalog_crosswalk_refresh_v2() is
'Provider catalog crosswalk using canonical Stripe platform credential alias stripe_server_api_key. Distinct product-specific and custody-copy keys are intentionally excluded from credential selection.';

select integration_control.scheduler_desired_job_upsert_v2(
  'ct-stripe-catalog-crosswalk-refresh-v3',
  '47 5 * * *',
  'select integration_control.stripe_catalog_crosswalk_refresh_v2();',
  2026082904,
  'ct.stripe.catalog-crosswalk.v3',
  jsonb_build_object(
    'owner','PentaGreen/PentaStatus/PentaCertify',
    'rollback_policy','monotonic',
    'money_movement',false,
    'checkout_activation',false,
    'provider_write','read_only_catalog',
    'authority_created',false
  )
);
select cron.unschedule(jobid) from cron.job where jobname='ct-stripe-catalog-crosswalk-refresh-v3';
select cron.schedule(
  'ct-stripe-catalog-crosswalk-refresh-v3',
  '47 5 * * *',
  'select integration_control.stripe_catalog_crosswalk_refresh_v2();'
);
select integration_control.scheduler_permanence_reconcile_v2();

-- Read-only convergence must be explicit: unmatched rows remain held, never omitted.
select integration_control.stripe_catalog_crosswalk_refresh_v2();
