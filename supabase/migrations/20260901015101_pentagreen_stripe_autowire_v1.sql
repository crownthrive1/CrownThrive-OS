-- Historical production-applied Stripe autowire v1.
-- Superseded for portable clock reconciliation by 202609010152xx v2 below.

create or replace function integration_control.pentagreen_stripe_autowire_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  r record;
  v_result jsonb;
  v_seen integer:=0;
  v_queued integer:=0;
  v_reused integer:=0;
  v_skipped integer:=0;
  v_outputs jsonb:='[]'::jsonb;
  v_ready_states text[]:=array['ready','verified','pass','passed','approved','complete','completed','active','bound','reconciled','certified'];
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;

  for r in
    select p.*
    from integration_control.pentagreen_mesh_product_profiles_v1 p
    where p.direct_checkout_desired=true
      and lower(coalesce(p.desired_state,''))='enabled'
      and (p.stripe_product_id is null or p.stripe_price_id is null)
      and lower(coalesce(p.rights_state,''))=any(v_ready_states)
      and lower(coalesce(p.fulfillment_state,''))=any(v_ready_states)
      and lower(coalesce(p.quality_state,''))=any(v_ready_states)
      and lower(coalesce(p.route_state,''))=any(v_ready_states)
      and lower(coalesce(p.custody_state,''))=any(v_ready_states)
      and lower(coalesce(p.docs_state,''))=any(v_ready_states)
    order by coalesce(p.quality_score,0) desc,p.updated_at,p.sku
    limit greatest(1,least(coalesce(p_limit,100),500))
  loop
    v_seen:=v_seen+1;
    begin
      v_result:=integration_control.pentagreen_stripe_prepare_monetization_v1(
        'penta_sku',r.sku,'PRODUCT_PRICE','product_price',
        jsonb_strip_nulls(jsonb_build_object(
          'offer_code',r.offer_code,
          'sku',r.sku,
          'product_type',r.product_type,
          'catalog_version',r.catalog_version,
          'existing_stripe_product_id',r.stripe_product_id,
          'existing_stripe_price_id',r.stripe_price_id,
          'license_class',r.license_class,
          'format_profile_id',r.format_profile_id,
          'pricing_authority','PentaPrice',
          'catalog_authority','PentaCatalog/PentaSKU',
          'checkout_authority','PentaCheckout',
          'economic_authority','PentaGreen',
          'pricing_mode','derive_from_pentaprice_or_existing_governed_price',
          'direct_checkout_desired',r.direct_checkout_desired,
          'credit_checkout_desired',r.credit_checkout_desired,
          'source_profile_metadata',r.metadata,
          'autowire','pentagreen_stripe_autowire_v1')),
        'COMMERCE_PRIMARY',40,'founder_directive_stripe_os_monetization_2026-08-31');
      if v_result->>'state'='QUEUED' then v_queued:=v_queued+1;
      elsif v_result->>'state'='REUSE' then v_reused:=v_reused+1;
      else v_skipped:=v_skipped+1; end if;
      v_outputs:=v_outputs||jsonb_build_array(jsonb_build_object('sku',r.sku,'state',v_result->>'state','request_id',v_result->>'request_id','work_id',v_result->>'work_id'));
    exception when others then
      v_skipped:=v_skipped+1;
      v_outputs:=v_outputs||jsonb_build_array(jsonb_build_object('sku',r.sku,'state','HOLD','error_code',sqlstate));
    end;
  end loop;

  return jsonb_build_object('state','PASS','eligible_seen',v_seen,'queued',v_queued,'reused',v_reused,'skipped',v_skipped,'outputs',v_outputs,'new_scheduler_created',false,'money_movement',false,'authority_created',false,'observed_at',now());
end
$fn$;

create or replace function integration_control.thriveevergreen_commerce_mesh_cycle_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'integration_control','public'
as $fn$
declare
  v_id uuid:=gen_random_uuid();
  a jsonb; b jsonb; c jsonb; d jsonb; s jsonb; e jsonb;
begin
  insert into integration_control.thriveevergreen_mesh_cycle_receipts_v1(cycle_id) values(v_id);
  a:=integration_control.thriveevergreen_mesh_seed_catalog_v1();
  b:=integration_control.thriveevergreen_mesh_reconcile_routes_v1();
  c:=integration_control.thriveevergreen_mesh_enqueue_gaps_v1();
  d:=integration_control.thriveevergreen_mesh_reconcile_replicas_v1();
  e:=integration_control.pentagreen_stripe_autowire_v1(100);
  s:=public.thriveevergreen_commerce_mesh_status_v1()||jsonb_build_object('stripe_autowire',e,'stripe_mesh','ct.binding.pentagreen-stripe-mesh.v3');
  update integration_control.thriveevergreen_mesh_cycle_receipts_v1
     set cycle_completed_at=now(),seed_result=a,route_result=b,queue_result=c,replica_result=d,status_snapshot=s,result_state='pass'
   where cycle_id=v_id;
  return jsonb_build_object('cycle_id',v_id,'state','pass','seed',a,'routes',b,'queue',c,'replicas',d,'stripe_autowire',e,'status',s);
exception when others then
  update integration_control.thriveevergreen_mesh_cycle_receipts_v1 set cycle_completed_at=now(),result_state='error',status_snapshot=jsonb_build_object('error',sqlerrm) where cycle_id=v_id;
  raise;
end
$fn$;

revoke all on function integration_control.pentagreen_stripe_autowire_v1(integer) from public,anon,authenticated;
grant execute on function integration_control.pentagreen_stripe_autowire_v1(integer) to service_role;

-- Production history used the then-current job id. The portable semantic clock
-- reconciliation is carried in the succeeding v2 migration.
select cron.unschedule(jobid) from cron.job where jobid=146 and active=true;
select cron.schedule('ct-pentagreen-commerce-mesh-cycle-v1','5-50/15 * * * *','select integration_control.thriveevergreen_commerce_mesh_cycle_v1();');
