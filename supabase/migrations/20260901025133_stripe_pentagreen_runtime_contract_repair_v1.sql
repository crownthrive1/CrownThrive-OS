-- Repair the live Commerce Binder against the current ThriveBase schema.
-- This migration is forward-only and includes a rollback-only, no-provider canary.

create or replace function integration_control.pentagreen_stripe_prepare_monetization_v1(
  p_subject_type text,
  p_subject_ref text,
  p_request_type text,
  p_requested_output text,
  p_payload jsonb default '{}'::jsonb,
  p_account_role text default 'COMMERCE_PRIMARY',
  p_priority smallint default 40,
  p_authority_ref text default 'founder_directive_stripe_os_monetization_2026-08-31'
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_idem text;
  v_request uuid:=gen_random_uuid();
  v_work uuid:=gen_random_uuid();
  v_inserted uuid;
  v_existing integration_control.pentagreen_stripe_monetization_requests_v1%rowtype;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if p_authority_ref<>'founder_directive_stripe_os_monetization_2026-08-31' then
    return jsonb_build_object('state','HOLD_AUTHORITY_REF_NOT_RECOGNIZED','authority_created',false,'money_movement',false);
  end if;
  if p_subject_type not in ('penta_offer','penta_sku') or nullif(p_subject_ref,'') is null or length(p_subject_ref)>240 then
    raise exception 'invalid_monetization_subject';
  end if;
  if jsonb_typeof(coalesce(p_payload,'{}'::jsonb))<>'object' or length(coalesce(p_payload,'{}'::jsonb)::text)>16000 then
    raise exception 'invalid_monetization_payload';
  end if;
  if lower(coalesce(p_payload::text,'')) ~ '(refund|payout|bank[_ -]?account|external[_ -]?account|dispute[_ -]?accept|transfer[_ -]?funds|rights[_ -]?grant|application[_ -]?fee|on[_ -]?behalf[_ -]?of|transfer[_ -]?data)' then
    raise exception 'reserved_effect_requires_separate_authority_lane';
  end if;
  if (p_request_type,p_requested_output) not in (
    ('PRODUCT_PRICE','product_price'),
    ('PAYMENT_LINK','payment_link'),
    ('WEBHOOK_BINDING','webhook_binding'),
    ('CATALOG_SYNC','catalog_sync')
  ) then
    return jsonb_build_object('state','HOLD_SPECIALIZED_EXECUTOR_REQUIRED','request_type',p_request_type,'requested_output',p_requested_output,'authority_created',false,'money_movement',false);
  end if;
  if not exists(
    select 1 from integration_control.stripe_os_accounts_v1
    where account_role=p_account_role and livemode=true and provider_state like 'provider_live_verified%'
  ) then return jsonb_build_object('state','HOLD_ACCOUNT_ROLE_NOT_AVAILABLE','account_role',p_account_role,'authority_created',false); end if;
  if not exists(
    select 1 from integration_control.pentagreen_mesh_agent_roles_v1
    where role_id='ct.role.thriveevergreen.commerce-binder' and lifecycle_state='active'
      and provider_write_allowed=true and no_self_approval=true and coalesce(money_movement_allowed,false)=false
  ) then raise exception 'commerce_binder_unavailable'; end if;

  v_idem:=encode(extensions.digest(convert_to(coalesce(p_subject_type,'')||'|'||coalesce(p_subject_ref,'')||'|'||p_request_type||'|'||p_requested_output||'|'||coalesce(p_account_role,'')||'|'||coalesce(p_payload,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex');
  insert into integration_control.pentagreen_stripe_monetization_requests_v1(
    request_id,idempotency_key,request_type,subject_type,subject_ref,requested_output,
    account_role,request_state,authority_ref,work_id,payload
  ) values(
    v_request,v_idem,p_request_type,p_subject_type,p_subject_ref,p_requested_output,
    p_account_role,'queued',p_authority_ref,v_work,coalesce(p_payload,'{}'::jsonb)||jsonb_build_object(
      'stripe_mesh','ct.binding.pentagreen-stripe-mesh.v3','provider_execution_only',true,
      'economic_authority','PentaGreen','no_self_approval',true,'typed_adapter','integration_control.stripe_os_provider_operation_v2'
    )
  ) on conflict(idempotency_key) do nothing returning request_id into v_inserted;

  if v_inserted is not null then
    insert into integration_control.thriveevergreen_mesh_work_queue_v1(
      work_id,work_type,subject_type,subject_ref,role_id,priority,work_state,
      idempotency_key,authority_ref,payload
    ) values(
      v_work,'stripe_monetization',p_subject_type,p_subject_ref,
      'ct.role.thriveevergreen.commerce-binder',greatest(1,least(coalesce(p_priority,40),100)),
      'queued','stripe:'||v_idem,p_authority_ref,
      jsonb_build_object('request_id',v_request,'request_type',p_request_type,'requested_output',p_requested_output,'account_role',p_account_role,'stripe_mesh','ct.binding.pentagreen-stripe-mesh.v3')
    );
    return jsonb_build_object('state','QUEUED','request_id',v_request,'work_id',v_work,'idempotency_key',v_idem,'owner_role','ct.role.thriveevergreen.commerce-binder','authority_created',false,'money_movement',false);
  end if;

  select * into v_existing
  from integration_control.pentagreen_stripe_monetization_requests_v1
  where idempotency_key=v_idem for update;
  if v_existing.request_state in ('hold','failed') and v_existing.work_id is not null and exists(
    select 1 from integration_control.thriveevergreen_mesh_work_queue_v1
    where work_id=v_existing.work_id and attempt_count<3
  ) then
    update integration_control.pentagreen_stripe_monetization_requests_v1
    set request_state='queued',result=jsonb_build_object('state','REQUEUED','prior_state',v_existing.request_state,'requeued_at',clock_timestamp()),updated_at=clock_timestamp()
    where request_id=v_existing.request_id;
    update integration_control.thriveevergreen_mesh_work_queue_v1
    set work_state='queued',available_at=clock_timestamp(),claimed_at=null,claimed_by_replica_id=null,
        completed_at=null,last_error_code=null,updated_at=clock_timestamp()
    where work_id=v_existing.work_id;
    return jsonb_build_object('state','REQUEUED','request_id',v_existing.request_id,'work_id',v_existing.work_id,'idempotency_key',v_idem,'authority_created',false,'money_movement',false);
  end if;
  return jsonb_build_object('state','REUSE','request_id',v_existing.request_id,'work_id',v_existing.work_id,'request_state',v_existing.request_state,'idempotency_key',v_idem,'authority_created',false,'money_movement',false);
end
$fn$;

create or replace function integration_control.pentagreen_stripe_autowire_v1(p_limit integer default 25)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  r record;
  v_result jsonb;
  v_seen integer:=0; v_queued integer:=0; v_reused integer:=0; v_skipped integer:=0; v_errors integer:=0;
  v_type text; v_output text;
  v_ready_states text[]:=array['ready','verified','pass','passed','approved','complete','completed','active','bound','reconciled','certified'];
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  for r in
    select p.*,tr.stripe_tax_code as governed_tax_code
    from integration_control.pentagreen_mesh_product_profiles_v1 p
    join developer_commerce.product_type_registry pt on pt.product_type=p.product_type
    join developer_commerce.tax_profile_registry tr on tr.tax_profile_code=pt.default_tax_profile_code
    where p.direct_checkout_desired=true
      and lower(coalesce(p.desired_state,''))='enabled'
      and pt.enabled_for_sale=true
      and tr.stripe_code_state='provider_code_verified'
      and lower(coalesce(tr.legal_taxability_state,'')) in ('ready','verified','approved','certified','taxable_verified','not_taxable_verified')
      and (
        p.stripe_product_id is null or p.stripe_price_id is null
        or not exists(select 1 from integration_control.stripe_payment_link_inventory_v4 pl where pl.price_id=p.stripe_price_id and pl.active=true)
      )
      and lower(coalesce(p.rights_state,''))=any(v_ready_states)
      and lower(coalesce(p.fulfillment_state,''))=any(v_ready_states)
      and lower(coalesce(p.quality_state,''))=any(v_ready_states)
      and lower(coalesce(p.route_state,''))=any(v_ready_states)
      and lower(coalesce(p.custody_state,''))=any(v_ready_states)
      and lower(coalesce(p.docs_state,''))=any(v_ready_states)
      and coalesce(nullif(p.metadata->>'tax_code',''),tr.stripe_tax_code,'') ~ '^txcd_[0-9]+$'
      and lower(coalesce(p.metadata->>'tax_behavior','')) in ('inclusive','exclusive')
      and nullif(p.metadata->>'stripe_entitlement_handler_ref','') is not null
      and nullif(p.metadata->>'stripe_webhook_binding_key','') is not null
      and lower(coalesce(p.metadata->>'stripe_entitlement_state',''))=any(v_ready_states)
    order by coalesce(p.quality_score,0) desc,p.updated_at,p.offer_code
    limit greatest(1,least(coalesce(p_limit,25),100))
  loop
    v_seen:=v_seen+1;
    if r.stripe_product_id is null or r.stripe_price_id is null then v_type:='PRODUCT_PRICE'; v_output:='product_price';
    else v_type:='PAYMENT_LINK'; v_output:='payment_link'; end if;
    begin
      v_result:=integration_control.pentagreen_stripe_prepare_monetization_v1(
        'penta_offer',r.offer_code,v_type,v_output,
        jsonb_strip_nulls(jsonb_build_object(
          'offer_code',r.offer_code,'sku',r.sku,'product_name',coalesce(r.metadata->>'product_name',r.offer_code,r.sku),
          'product_type',r.product_type,'catalog_version',r.catalog_version,
          'existing_stripe_product_id',r.stripe_product_id,'existing_stripe_price_id',r.stripe_price_id,
          'unit_amount',nullif(r.metadata->>'unit_amount','')::bigint,'currency',lower(coalesce(nullif(r.metadata->>'currency',''),'usd')),
          'billing_mode',lower(coalesce(nullif(r.metadata->>'billing_mode',''),'one_time')),
          'recurring_interval',lower(nullif(r.metadata->>'recurring_interval','')),
          'tax_code',coalesce(nullif(r.metadata->>'tax_code',''),r.governed_tax_code),'tax_behavior',lower(r.metadata->>'tax_behavior'),
          'automatic_tax_enabled',coalesce((r.metadata->>'automatic_tax_enabled')::boolean,false),
          'entitlement_handler_ref',r.metadata->>'stripe_entitlement_handler_ref',
          'webhook_binding_key',r.metadata->>'stripe_webhook_binding_key',
          'license_class',r.license_class,'format_profile_id',r.format_profile_id,
          'pricing_authority','PentaPrice','catalog_authority','PentaCatalog/PentaSKU',
          'checkout_authority','PentaCheckout','economic_authority','PentaGreen',
          'pricing_mode','existing_governed_unit_amount','direct_checkout_desired',r.direct_checkout_desired,
          'credit_checkout_desired',r.credit_checkout_desired,'autowire','pentagreen_stripe_autowire_v1'
        )),'COMMERCE_PRIMARY',40,'founder_directive_stripe_os_monetization_2026-08-31'
      );
      if v_result->>'state'='QUEUED' then v_queued:=v_queued+1;
      elsif v_result->>'state' in ('REUSE','REQUEUED') then v_reused:=v_reused+1;
      else v_skipped:=v_skipped+1; end if;
    exception when others then
      v_errors:=v_errors+1;
    end;
  end loop;
  return jsonb_build_object(
    'state',case when v_errors>0 then 'DEGRADED' when v_seen=0 then 'IDLE' else 'PASS' end,
    'eligible_seen',v_seen,'queued',v_queued,'reused',v_reused,'skipped',v_skipped,'errors',v_errors,
    'new_scheduler_created',false,'money_movement',false,'authority_created',false,'observed_at',clock_timestamp()
  );
end
$fn$;

create or replace function integration_control.pentagreen_stripe_commerce_binder_tick_v1(p_limit integer default 1)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  w record;
  q integration_control.pentagreen_stripe_monetization_requests_v1%rowtype;
  p integration_control.pentagreen_mesh_product_profiles_v1%rowtype;
  v_replica_id text;
  v_prod_id text; v_price_id text; v_link_id text;
  v_unit bigint; v_currency text; v_billing text; v_interval text; v_name text;
  v_tax_code text; v_tax_behavior text; v_handler text; v_webhook text;
  v_r jsonb; v_j jsonb; v_line_items jsonb; v_reason text;
  v_done integer:=0; v_hold integer:=0; v_failed integer:=0; v_retry integer:=0; v_seen integer:=0;
  v_account_ref text; v_object_hash text; v_line_hash text; v_attempt integer; v_provider_status integer;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct.pentagreen.stripe.commerce-binder.v1',0)) then
    return jsonb_build_object('state','SKIPPED_LOCKED','seen',0,'money_movement',false,'observed_at',clock_timestamp());
  end if;
  select replica_id into v_replica_id
  from integration_control.thriveevergreen_mesh_replicas_v1
  where role_id='ct.role.thriveevergreen.commerce-binder' and replica_state='active'
  order by last_heartbeat_at nulls first,replica_no limit 1;
  if v_replica_id is null then return jsonb_build_object('state','HOLD_NO_ACTIVE_REPLICA','seen',0,'money_movement',false); end if;
  update integration_control.thriveevergreen_mesh_replicas_v1
  set last_heartbeat_at=clock_timestamp(),current_assignment_ref='stripe_monetization_tick',updated_at=clock_timestamp()
  where replica_id=v_replica_id;

  for w in
    select * from integration_control.thriveevergreen_mesh_work_queue_v1
    where work_type='stripe_monetization' and role_id='ct.role.thriveevergreen.commerce-binder'
      and work_state='queued' and available_at<=clock_timestamp() and attempt_count<3
    order by priority desc,created_at
    limit greatest(1,least(coalesce(p_limit,1),5))
  loop
    q:=null; p:=null; v_prod_id:=null; v_price_id:=null; v_link_id:=null;
    v_unit:=null; v_currency:=null; v_billing:=null; v_interval:=null; v_name:=null;
    v_tax_code:=null; v_tax_behavior:=null; v_handler:=null; v_webhook:=null;
    v_r:=null; v_j:=null; v_line_items:=null; v_reason:=null; v_account_ref:=null;
    v_object_hash:=null; v_line_hash:=null; v_provider_status:=null;
    v_seen:=v_seen+1; v_attempt:=w.attempt_count+1;

    update integration_control.thriveevergreen_mesh_work_queue_v1
    set work_state='executing',attempt_count=v_attempt,claimed_at=coalesce(claimed_at,clock_timestamp()),
        claimed_by_replica_id=v_replica_id,last_error_code=null,updated_at=clock_timestamp()
    where work_id=w.work_id and work_state='queued';
    if not found then continue; end if;
    select * into q from integration_control.pentagreen_stripe_monetization_requests_v1 where work_id=w.work_id;
    if not found then
      update integration_control.thriveevergreen_mesh_work_queue_v1
      set work_state='failed',last_error_code='stripe_request_missing',updated_at=clock_timestamp()
      where work_id=w.work_id;
      v_failed:=v_failed+1; continue;
    end if;
    update integration_control.pentagreen_stripe_monetization_requests_v1
    set request_state='executing',updated_at=clock_timestamp() where request_id=q.request_id;

    if q.subject_type='penta_offer' then
      select * into p from integration_control.pentagreen_mesh_product_profiles_v1 where offer_code=q.subject_ref order by updated_at desc limit 1;
    else
      select * into p from integration_control.pentagreen_mesh_product_profiles_v1 where sku=q.subject_ref order by updated_at desc limit 1;
    end if;
    if not found and q.request_type in ('PRODUCT_PRICE','PAYMENT_LINK') then v_reason:='penta_product_profile_missing'; end if;

    if v_reason is null and q.request_type in ('PRODUCT_PRICE','PAYMENT_LINK') then
      if lower(coalesce(p.rights_state,'')) not in ('ready','verified','pass','passed','approved','complete','completed','active','bound','reconciled','certified')
        or lower(coalesce(p.fulfillment_state,'')) not in ('ready','verified','pass','passed','approved','complete','completed','active','bound','reconciled','certified')
        or lower(coalesce(p.quality_state,'')) not in ('ready','verified','pass','passed','approved','complete','completed','active','bound','reconciled','certified')
        or lower(coalesce(p.route_state,'')) not in ('ready','verified','pass','passed','approved','complete','completed','active','bound','reconciled','certified')
        or lower(coalesce(p.custody_state,'')) not in ('ready','verified','pass','passed','approved','complete','completed','active','bound','reconciled','certified')
        or lower(coalesce(p.docs_state,'')) not in ('ready','verified','pass','passed','approved','complete','completed','active','bound','reconciled','certified') then
        v_reason:='penta_product_prerequisites_not_ready';
      end if;
      if v_reason is null and not exists(
        select 1
        from developer_commerce.product_type_registry pt
        join developer_commerce.tax_profile_registry tr on tr.tax_profile_code=pt.default_tax_profile_code
        where pt.product_type=p.product_type and pt.enabled_for_sale=true
          and tr.stripe_code_state='provider_code_verified'
          and lower(coalesce(tr.legal_taxability_state,'')) in ('ready','verified','approved','certified','taxable_verified','not_taxable_verified')
      ) then v_reason:='product_type_sale_or_legal_tax_gate_not_ready'; end if;
    end if;

    if v_reason is null and q.request_type='PRODUCT_PRICE' then
      v_unit:=coalesce(nullif(q.payload->>'unit_amount','')::bigint,nullif(p.metadata->>'unit_amount','')::bigint);
      v_currency:=lower(coalesce(nullif(q.payload->>'currency',''),nullif(p.metadata->>'currency',''),'usd'));
      v_billing:=lower(coalesce(nullif(q.payload->>'billing_mode',''),nullif(p.metadata->>'billing_mode',''),'one_time'));
      v_interval:=lower(coalesce(nullif(q.payload->>'recurring_interval',''),nullif(p.metadata->>'recurring_interval','')));
      v_name:=coalesce(nullif(q.payload->>'product_name',''),nullif(p.metadata->>'product_name',''),nullif(p.offer_code,''),nullif(p.sku,''));
      v_tax_code:=coalesce(nullif(q.payload->>'tax_code',''),nullif(p.metadata->>'tax_code',''));
      v_tax_behavior:=lower(coalesce(nullif(q.payload->>'tax_behavior',''),nullif(p.metadata->>'tax_behavior','')));
      v_handler:=coalesce(nullif(q.payload->>'entitlement_handler_ref',''),nullif(p.metadata->>'stripe_entitlement_handler_ref',''));
      v_webhook:=coalesce(nullif(q.payload->>'webhook_binding_key',''),nullif(p.metadata->>'stripe_webhook_binding_key',''));
      if v_unit is null or v_unit<1 or coalesce(v_currency,'') !~ '^[a-z]{3}$' or v_name is null or coalesce(v_tax_code,'') !~ '^txcd_[0-9]+$' or v_tax_behavior is null or v_tax_behavior not in ('inclusive','exclusive') then v_reason:='governed_product_price_tax_contract_missing'; end if;
      if v_reason is null and p.direct_checkout_desired and (v_handler is null or v_webhook is null or lower(coalesce(p.metadata->>'stripe_entitlement_state','')) not in ('ready','verified','active','certified')) then v_reason:='entitlement_webhook_contract_missing'; end if;
      v_prod_id:=coalesce(nullif(q.payload->>'existing_stripe_product_id',''),p.stripe_product_id);
      if v_reason is null and v_prod_id is null then
        v_r:=integration_control.stripe_os_provider_operation_v2(q.request_id,'product.create',null,jsonb_build_object('name',v_name,'sku',p.sku,'offer_code',p.offer_code,'tax_code',v_tax_code));
        if v_r->>'state'<>'PASS' then v_reason:='product_create_'||coalesce(v_r->>'state','failed'); v_provider_status:=nullif(v_r->>'provider_http_status','')::integer;
        else v_prod_id:=v_r#>>'{response,id}'; v_account_ref:=v_r->>'account_ref'; end if;
      end if;
      if v_reason is null then
        v_r:=integration_control.stripe_os_provider_operation_v2(q.request_id,'product.retrieve',v_prod_id,'{}'::jsonb);
        if v_r->>'state'<>'PASS' then v_reason:='product_readback_failed'; v_provider_status:=nullif(v_r->>'provider_http_status','')::integer;
        else
          v_j:=v_r->'response'; v_account_ref:=v_r->>'account_ref';
          v_object_hash:=encode(extensions.digest(convert_to(v_j::text,'UTF8'),'sha256'),'hex');
          insert into integration_control.stripe_catalog_products_v2(provider_product_id,name,active,description,default_price_id,statement_descriptor,tax_code,provider_created_at,metadata,provider_object_sha256,observed_at,updated_at,provider_account_id)
          values(v_prod_id,coalesce(v_j->>'name',v_name),coalesce((v_j->>'active')::boolean,true),v_j->>'description',case when jsonb_typeof(v_j->'default_price')='string' then v_j->>'default_price' else v_j#>>'{default_price,id}' end,v_j->>'statement_descriptor',v_j->>'tax_code',to_timestamp(coalesce(nullif(v_j->>'created','')::bigint,extract(epoch from clock_timestamp())::bigint)),coalesce(v_j->'metadata','{}'::jsonb),v_object_hash,clock_timestamp(),clock_timestamp(),v_account_ref)
          on conflict(provider_product_id) do update set name=excluded.name,active=excluded.active,description=excluded.description,default_price_id=excluded.default_price_id,statement_descriptor=excluded.statement_descriptor,tax_code=excluded.tax_code,provider_created_at=excluded.provider_created_at,metadata=excluded.metadata,provider_object_sha256=excluded.provider_object_sha256,observed_at=excluded.observed_at,updated_at=excluded.updated_at,provider_account_id=excluded.provider_account_id;
        end if;
      end if;
      v_price_id:=coalesce(nullif(q.payload->>'existing_stripe_price_id',''),p.stripe_price_id);
      if v_reason is null and v_price_id is null then
        v_r:=integration_control.stripe_os_provider_operation_v2(q.request_id,'price.create',v_prod_id,jsonb_build_object('unit_amount',v_unit,'currency',v_currency,'billing_mode',v_billing,'recurring_interval',v_interval,'tax_behavior',v_tax_behavior,'sku',p.sku,'offer_code',p.offer_code));
        if v_r->>'state'<>'PASS' then v_reason:='price_create_'||coalesce(v_r->>'state','failed'); v_provider_status:=nullif(v_r->>'provider_http_status','')::integer;
        else v_price_id:=v_r#>>'{response,id}'; v_account_ref:=v_r->>'account_ref'; end if;
      end if;
      if v_reason is null then
        v_r:=integration_control.stripe_os_provider_operation_v2(q.request_id,'price.retrieve',v_price_id,'{}'::jsonb);
        if v_r->>'state'<>'PASS' then v_reason:='price_readback_failed'; v_provider_status:=nullif(v_r->>'provider_http_status','')::integer;
        else
          v_j:=v_r->'response'; v_account_ref:=v_r->>'account_ref';
          v_object_hash:=encode(extensions.digest(convert_to(v_j::text,'UTF8'),'sha256'),'hex');
          insert into integration_control.stripe_catalog_prices_v2(provider_price_id,provider_product_id,active,currency,unit_amount,billing_type,recurring_interval,recurring_interval_count,lookup_key,nickname,provider_created_at,metadata,provider_object_sha256,observed_at,updated_at,provider_account_id)
          values(v_price_id,v_prod_id,coalesce((v_j->>'active')::boolean,true),lower(v_j->>'currency'),nullif(v_j->>'unit_amount','')::bigint,coalesce(v_j->>'type',case when v_j->'recurring' is null then 'one_time' else 'recurring' end),v_j#>>'{recurring,interval}',nullif(v_j#>>'{recurring,interval_count}','')::integer,v_j->>'lookup_key',v_j->>'nickname',to_timestamp(coalesce(nullif(v_j->>'created','')::bigint,extract(epoch from clock_timestamp())::bigint)),coalesce(v_j->'metadata','{}'::jsonb)||jsonb_build_object('tax_behavior',v_j->>'tax_behavior'),v_object_hash,clock_timestamp(),clock_timestamp(),v_account_ref)
          on conflict(provider_price_id) do update set provider_product_id=excluded.provider_product_id,active=excluded.active,currency=excluded.currency,unit_amount=excluded.unit_amount,billing_type=excluded.billing_type,recurring_interval=excluded.recurring_interval,recurring_interval_count=excluded.recurring_interval_count,lookup_key=excluded.lookup_key,nickname=excluded.nickname,provider_created_at=excluded.provider_created_at,metadata=excluded.metadata,provider_object_sha256=excluded.provider_object_sha256,observed_at=excluded.observed_at,updated_at=excluded.updated_at,provider_account_id=excluded.provider_account_id;
          update integration_control.pentagreen_mesh_product_profiles_v1
          set stripe_product_id=v_prod_id,stripe_price_id=v_price_id,
              metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('stripe_mesh','ct.binding.pentagreen-stripe-mesh.v3','stripe_account_ref',v_account_ref,'stripe_bound_at',clock_timestamp(),'tax_code',v_tax_code,'tax_behavior',v_tax_behavior),updated_at=clock_timestamp()
          where offer_code=p.offer_code;
        end if;
      end if;
      if v_reason is null and p.direct_checkout_desired then
        if not exists(
          select 1 from integration_control.stripe_webhook_endpoints_v3 e
          where e.provider_status='enabled' and e.livemode=true and e.metadata->>'ct_binding_key'=v_webhook
            and e.enabled_events @> '["checkout.session.completed","checkout.session.async_payment_succeeded","checkout.session.async_payment_failed","charge.refunded","charge.dispute.created"]'::jsonb
            and exists(select 1 from integration_control.stripe_webhook_provider_receipts_v3 wr where wr.signed_canary_ok=true and wr.observed_at>clock_timestamp()-interval '24 hours' and position(e.provider_endpoint_id in coalesce(wr.provider_endpoint_id,''))>0)
        ) then v_reason:='signed_webhook_event_matrix_not_verified';
        else
          v_r:=integration_control.stripe_os_provider_operation_v2(q.request_id,'payment_link.create',v_price_id,jsonb_build_object('sku',p.sku,'offer_code',p.offer_code,'entitlement_handler_ref',v_handler,'webhook_binding_key',v_webhook,'automatic_tax_enabled',coalesce((q.payload->>'automatic_tax_enabled')::boolean,false)));
          if v_r->>'state'='PASS' then v_link_id:=v_r#>>'{response,id}'; v_account_ref:=v_r->>'account_ref';
          else v_reason:='payment_link_create_'||coalesce(v_r->>'state','failed'); v_provider_status:=nullif(v_r->>'provider_http_status','')::integer; end if;
        end if;
      end if;
    elsif v_reason is null and q.request_type='PAYMENT_LINK' then
      v_prod_id:=coalesce(nullif(q.payload->>'existing_stripe_product_id',''),p.stripe_product_id);
      v_price_id:=coalesce(nullif(q.payload->>'existing_stripe_price_id',''),p.stripe_price_id);
      v_name:=coalesce(nullif(p.metadata->>'product_name',''),p.offer_code,p.sku);
      v_handler:=coalesce(nullif(q.payload->>'entitlement_handler_ref',''),nullif(p.metadata->>'stripe_entitlement_handler_ref',''));
      v_webhook:=coalesce(nullif(q.payload->>'webhook_binding_key',''),nullif(p.metadata->>'stripe_webhook_binding_key',''));
      v_tax_code:=coalesce(nullif(q.payload->>'tax_code',''),nullif(p.metadata->>'tax_code',''));
      v_tax_behavior:=lower(coalesce(nullif(q.payload->>'tax_behavior',''),nullif(p.metadata->>'tax_behavior','')));
      if v_price_id is null or v_handler is null or v_webhook is null or coalesce(v_tax_code,'') !~ '^txcd_[0-9]+$' or v_tax_behavior is null or v_tax_behavior not in ('inclusive','exclusive') then v_reason:='stripe_price_tax_entitlement_binding_missing';
      elsif not exists(
        select 1 from integration_control.stripe_webhook_endpoints_v3 e
        where e.provider_status='enabled' and e.livemode=true and e.metadata->>'ct_binding_key'=v_webhook
          and e.enabled_events @> '["checkout.session.completed","checkout.session.async_payment_succeeded","checkout.session.async_payment_failed","charge.refunded","charge.dispute.created"]'::jsonb
          and exists(select 1 from integration_control.stripe_webhook_provider_receipts_v3 wr where wr.signed_canary_ok=true and wr.observed_at>clock_timestamp()-interval '24 hours' and position(e.provider_endpoint_id in coalesce(wr.provider_endpoint_id,''))>0)
      ) then v_reason:='signed_webhook_event_matrix_not_verified';
      else
        v_r:=integration_control.stripe_os_provider_operation_v2(q.request_id,'payment_link.create',v_price_id,jsonb_build_object('sku',p.sku,'offer_code',p.offer_code,'entitlement_handler_ref',v_handler,'webhook_binding_key',v_webhook,'automatic_tax_enabled',coalesce((q.payload->>'automatic_tax_enabled')::boolean,false)));
        if v_r->>'state'='PASS' then v_link_id:=v_r#>>'{response,id}'; v_account_ref:=v_r->>'account_ref';
        else v_reason:='payment_link_create_'||coalesce(v_r->>'state','failed'); v_provider_status:=nullif(v_r->>'provider_http_status','')::integer; end if;
      end if;
    elsif v_reason is null and q.request_type='WEBHOOK_BINDING' then
      v_r:=integration_control.stripe_webhook_provider_reconcile_v3(true);
      if v_r->>'state'<>'PASS' then v_reason:='webhook_reconcile_'||coalesce(v_r->>'state','failed'); end if;
    elsif v_reason is null and q.request_type='CATALOG_SYNC' then
      perform integration_control.stripe_product_inventory_refresh_v3(100);
    elsif v_reason is null then
      v_reason:='specialized_executor_required';
    end if;

    if v_reason is null and v_link_id is not null then
      v_r:=integration_control.stripe_os_provider_operation_v2(q.request_id,'payment_link.retrieve',v_link_id,'{}'::jsonb);
      if v_r->>'state'<>'PASS' then v_reason:='payment_link_readback_failed'; v_provider_status:=nullif(v_r->>'provider_http_status','')::integer;
      else
        v_j:=v_r->'response'; v_account_ref:=v_r->>'account_ref';
        v_line_items:=jsonb_build_array(jsonb_build_object('price_id',v_price_id,'product_id',v_prod_id,'quantity',1));
        v_object_hash:=encode(extensions.digest(convert_to(v_j::text,'UTF8'),'sha256'),'hex');
        v_line_hash:=encode(extensions.digest(convert_to(v_line_items::text,'UTF8'),'sha256'),'hex');
        insert into integration_control.stripe_payment_link_inventory_v4(payment_link_id,provider_account_id,url,active,product_id,price_id,product_name,product_description,currency,unit_amount,billing_mode,recurring_interval,quantity,provider_created_at,provider_object_sha256,provider_line_items_sha256,metadata,run_id,observed_at,updated_at)
        values(v_link_id,v_account_ref,v_j->>'url',coalesce((v_j->>'active')::boolean,true),v_prod_id,v_price_id,v_name,p.metadata->>'product_description',coalesce(v_currency,p.metadata->>'currency'),coalesce(v_unit,nullif(p.metadata->>'unit_amount','')::bigint),coalesce(v_billing,p.metadata->>'billing_mode','one_time'),coalesce(v_interval,p.metadata->>'recurring_interval'),1,to_timestamp(coalesce(nullif(v_j->>'created','')::bigint,extract(epoch from clock_timestamp())::bigint)),v_object_hash,v_line_hash,coalesce(v_j->'metadata','{}'::jsonb)||jsonb_build_object('line_items',v_line_items,'line_items_readback_state','declared_then_provider_link_readback','entitlement_handler_ref',v_handler,'webhook_binding_key',v_webhook),null,clock_timestamp(),clock_timestamp())
        on conflict(payment_link_id) do update set provider_account_id=excluded.provider_account_id,url=excluded.url,active=excluded.active,product_id=excluded.product_id,price_id=excluded.price_id,product_name=excluded.product_name,product_description=excluded.product_description,currency=excluded.currency,unit_amount=excluded.unit_amount,billing_mode=excluded.billing_mode,recurring_interval=excluded.recurring_interval,quantity=excluded.quantity,provider_created_at=excluded.provider_created_at,provider_object_sha256=excluded.provider_object_sha256,provider_line_items_sha256=excluded.provider_line_items_sha256,metadata=excluded.metadata,run_id=excluded.run_id,observed_at=excluded.observed_at,updated_at=excluded.updated_at;
      end if;
    end if;

    if v_reason is null then
      update integration_control.pentagreen_stripe_monetization_requests_v1
      set request_state='complete',stripe_product_id=coalesce(v_prod_id,stripe_product_id),stripe_price_id=coalesce(v_price_id,stripe_price_id),stripe_payment_link_id=coalesce(v_link_id,stripe_payment_link_id),result=jsonb_build_object('state','PASS','account_ref',v_account_ref,'product_id',v_prod_id,'price_id',v_price_id,'payment_link_id',v_link_id,'money_movement',false,'authority_created',false,'readback_verified',true),updated_at=clock_timestamp()
      where request_id=q.request_id;
      update integration_control.thriveevergreen_mesh_work_queue_v1
      set work_state='verified',completed_at=clock_timestamp(),last_error_code=null,updated_at=clock_timestamp()
      where work_id=w.work_id;
      v_done:=v_done+1;
    elsif v_attempt<3 and (v_provider_status=429 or v_provider_status>=500 or v_reason like '%HOLD_TRANSPORT_ERROR%') then
      update integration_control.pentagreen_stripe_monetization_requests_v1
      set request_state='queued',result=jsonb_build_object('state','RETRY','reason',v_reason,'attempt',v_attempt,'money_movement',false,'authority_created',false),updated_at=clock_timestamp()
      where request_id=q.request_id;
      update integration_control.thriveevergreen_mesh_work_queue_v1
      set work_state='queued',available_at=clock_timestamp()+make_interval(secs=>least(900,30*(2^v_attempt)::integer)),claimed_at=null,claimed_by_replica_id=null,last_error_code=left(v_reason,200),updated_at=clock_timestamp()
      where work_id=w.work_id;
      v_retry:=v_retry+1;
    else
      update integration_control.pentagreen_stripe_monetization_requests_v1
      set request_state='hold',result=jsonb_build_object('state','HOLD','reason',v_reason,'attempt',v_attempt,'money_movement',false,'authority_created',false),updated_at=clock_timestamp()
      where request_id=q.request_id;
      update integration_control.thriveevergreen_mesh_work_queue_v1
      set work_state='blocked',last_error_code=left(v_reason,200),updated_at=clock_timestamp()
      where work_id=w.work_id;
      v_hold:=v_hold+1;
    end if;
  end loop;
  update integration_control.thriveevergreen_mesh_replicas_v1
  set last_heartbeat_at=clock_timestamp(),current_assignment_ref=null,updated_at=clock_timestamp()
  where replica_id=v_replica_id;
  return jsonb_build_object('state',case when v_seen=0 then 'IDLE' when v_failed>0 or v_hold>0 then 'DEGRADED' when v_retry>0 then 'RETRYING' else 'PASS' end,'seen',v_seen,'completed',v_done,'held',v_hold,'retried',v_retry,'failed',v_failed,'replica_id',v_replica_id,'money_movement',false,'new_clock_created',false,'observed_at',clock_timestamp());
end
$fn$;

revoke all on function integration_control.pentagreen_stripe_prepare_monetization_v1(text,text,text,text,jsonb,text,smallint,text) from public,anon,authenticated;
revoke all on function integration_control.pentagreen_stripe_autowire_v1(integer) from public,anon,authenticated;
revoke all on function integration_control.pentagreen_stripe_commerce_binder_tick_v1(integer) from public,anon,authenticated;
grant execute on function integration_control.pentagreen_stripe_prepare_monetization_v1(text,text,text,text,jsonb,text,smallint,text),integration_control.pentagreen_stripe_autowire_v1(integer),integration_control.pentagreen_stripe_commerce_binder_tick_v1(integer) to service_role;

do $ct_canary$
declare
  v_hold_work uuid:=gen_random_uuid(); v_missing_work uuid:=gen_random_uuid(); v_request uuid:=gen_random_uuid();
  v_subject text:='__ct_repair_canary__:'||gen_random_uuid()::text; v_result jsonb; v_asserted boolean:=false; v_message text;
begin
  lock table integration_control.thriveevergreen_mesh_work_queue_v1 in share row exclusive mode;
  lock table integration_control.pentagreen_stripe_monetization_requests_v1 in share row exclusive mode;
  if exists(select 1 from integration_control.thriveevergreen_mesh_work_queue_v1 where work_type='stripe_monetization' and work_state='queued') then raise exception 'canary requires the monetization queue to be paused and drained'; end if;
  if exists(select 1 from integration_control.pentagreen_mesh_product_profiles_v1 where offer_code=v_subject or sku=v_subject) then raise exception 'canary subject collision'; end if;
  begin
    insert into integration_control.thriveevergreen_mesh_work_queue_v1(work_id,work_type,subject_type,subject_ref,role_id,priority,work_state,attempt_count,idempotency_key,authority_ref,payload,created_at,updated_at)
    values(v_hold_work,'stripe_monetization','penta_offer',v_subject,'ct.role.thriveevergreen.commerce-binder',32767,'queued',0,'ct.canary.work.'||v_hold_work::text,'ct.repair.canary','{}'::jsonb,'1900-01-01 00:00:00+00'::timestamptz,clock_timestamp());
    insert into integration_control.pentagreen_stripe_monetization_requests_v1(request_id,idempotency_key,request_type,subject_type,subject_ref,requested_output,account_role,request_state,authority_ref,owner_role_id,work_id,payload,result)
    values(v_request,'ct.canary.request.'||v_request::text,'PRODUCT_PRICE','penta_offer',v_subject,'product_price','COMMERCE_PRIMARY','queued','ct.repair.canary','ct.role.thriveevergreen.commerce-binder',v_hold_work,'{}'::jsonb,'{}'::jsonb);
    insert into integration_control.thriveevergreen_mesh_work_queue_v1(work_id,work_type,subject_type,subject_ref,role_id,priority,work_state,attempt_count,idempotency_key,authority_ref,payload,created_at,updated_at)
    values(v_missing_work,'stripe_monetization','penta_offer',v_subject||':missing-request','ct.role.thriveevergreen.commerce-binder',32767,'queued',0,'ct.canary.work.'||v_missing_work::text,'ct.repair.canary','{}'::jsonb,'1900-01-02 00:00:00+00'::timestamptz,clock_timestamp());
    v_result:=integration_control.pentagreen_stripe_commerce_binder_tick_v1(2);
    if coalesce((v_result->>'seen')::integer,-1)<>2 or coalesce((v_result->>'held')::integer,-1)<>1 or coalesce((v_result->>'failed')::integer,-1)<>1 then raise exception 'unexpected binder canary result: %',v_result; end if;
    if not exists(select 1 from integration_control.thriveevergreen_mesh_work_queue_v1 where work_id=v_hold_work and work_state='blocked' and attempt_count=1 and last_error_code='penta_product_profile_missing') then raise exception 'profile-missing queue assertion failed'; end if;
    if not exists(select 1 from integration_control.pentagreen_stripe_monetization_requests_v1 where request_id=v_request and request_state='hold' and result->>'reason'='penta_product_profile_missing') then raise exception 'profile-missing request assertion failed'; end if;
    if not exists(select 1 from integration_control.thriveevergreen_mesh_work_queue_v1 where work_id=v_missing_work and work_state='failed' and attempt_count=1 and last_error_code='stripe_request_missing') then raise exception 'request-missing queue assertion failed'; end if;
    if exists(select 1 from integration_control.stripe_os_provider_operation_receipts_v2 where request_id=v_request) then raise exception 'no-provider canary unexpectedly reached provider adapter'; end if;
    v_asserted:=true;
    raise exception using errcode='ZX001',message='ct_rollback_sentinel';
  exception when sqlstate 'ZX001' then
    get stacked diagnostics v_message=message_text;
    if v_message<>'ct_rollback_sentinel' or not v_asserted then raise; end if;
  end;
  if exists(select 1 from integration_control.thriveevergreen_mesh_work_queue_v1 where work_id in (v_hold_work,v_missing_work)) or exists(select 1 from integration_control.pentagreen_stripe_monetization_requests_v1 where request_id=v_request) then raise exception 'rollback-only canary leaked synthetic rows'; end if;
end
$ct_canary$;

do $ct_static$
declare v_def text;
begin
  v_def:=pg_get_functiondef('integration_control.pentagreen_stripe_commerce_binder_tick_v1(integer)'::regprocedure);
  if position('q:=null; p:=null; v_prod_id:=null; v_price_id:=null; v_link_id:=null;' in lower(v_def))=0
    or position('attempt_count' in lower(v_def))=0 or position('last_error_code' in lower(v_def))=0
    or position('provider_object_sha256' in lower(v_def))=0 then
    raise exception 'binder static contract assertion failed';
  end if;
end
$ct_static$;
