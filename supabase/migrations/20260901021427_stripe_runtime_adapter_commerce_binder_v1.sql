create or replace function integration_control.stripe_os_provider_request_v1(
  p_account_role text,
  p_method text,
  p_path text,
  p_form_body text default null,
  p_idempotency_key text default null
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public','extensions','chlom_runtime'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_account_ref text;
  v_lane record;
  v_secret text;
  v_probe extensions.http_response;
  v_probe_json jsonb;
  v_resp extensions.http_response;
  v_resp_json jsonb;
  v_headers extensions.http_header[];
  v_alias text;
  v_custody_role text;
  v_method extensions.http_method;
  v_digest text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if upper(p_method) not in ('GET','POST') then raise exception 'stripe_adapter_method_not_allowed'; end if;
  if p_path !~ '^/v1/(account$|products($|/)|prices($|/)|payment_links($|/)|checkout/sessions($|/)|customers($|/)|subscriptions($|/)|invoices($|/)|quotes($|/)|webhook_endpoints($|/))' then raise exception 'stripe_adapter_path_not_allowed'; end if;
  if p_path ~ '^/v1/(refunds|transfers|payouts|disputes|accounts/.*/external_accounts)' then raise exception 'reserved_stripe_effect_requires_specialist_lane'; end if;

  select account_ref into v_account_ref
  from integration_control.stripe_os_accounts_v1
  where account_role=p_account_role and livemode=true and provider_state like 'provider_live_verified%'
  order by route_priority limit 1;
  if v_account_ref is null then return jsonb_build_object('state','HOLD_ACCOUNT_ROLE_NOT_AVAILABLE','account_role',p_account_role,'secret_exposed',false); end if;

  for v_lane in
    select * from integration_control.stripe_live_secret_lanes_v1
    where enabled=true
      and platform_failover_eligible=true
      and independent_material=true
      and custody_role in ('HOT','WARM','COLD')
    order by priority
  loop
    begin
      v_secret:=public.get_runtime_secret(v_lane.vault_alias);
      if nullif(v_secret,'') is null then continue; end if;
      v_probe:=chlom_runtime.dail_http_v1((
        'GET'::extensions.http_method,
        'https://api.stripe.com/v1/account'::varchar,
        array[row('Authorization','Bearer '||v_secret)::extensions.http_header,row('Accept','application/json')::extensions.http_header,row('User-Agent','CrownThrive-Stripe-OS-v1')::extensions.http_header],
        null::varchar,null::varchar
      )::extensions.http_request);
      if v_probe.status=200 then
        begin v_probe_json:=v_probe.content::jsonb; exception when others then v_probe_json:='{}'::jsonb; end;
        if v_probe_json->>'id'=v_account_ref then
          v_alias:=v_lane.vault_alias;
          v_custody_role:=v_lane.custody_role;
          exit;
        end if;
      end if;
    exception when others then
      v_secret:=null;
    end;
  end loop;

  if v_alias is null then
    return jsonb_build_object('state','HOLD_NO_VERIFIED_CREDENTIAL_FOR_ACCOUNT','account_role',p_account_role,'account_ref',v_account_ref,'secret_exposed',false);
  end if;

  v_headers:=array[
    row('Authorization','Bearer '||v_secret)::extensions.http_header,
    row('Accept','application/json')::extensions.http_header,
    row('User-Agent','CrownThrive-Stripe-OS-v1')::extensions.http_header
  ]::extensions.http_header[];
  if upper(p_method)='POST' then
    v_headers:=v_headers||array[row('Content-Type','application/x-www-form-urlencoded')::extensions.http_header];
    if nullif(p_idempotency_key,'') is not null then v_headers:=v_headers||array[row('Idempotency-Key',p_idempotency_key)::extensions.http_header]; end if;
  end if;
  v_method:=upper(p_method)::extensions.http_method;
  v_resp:=chlom_runtime.dail_http_v1((
    v_method,
    ('https://api.stripe.com'||p_path)::varchar,
    v_headers,
    case when upper(p_method)='POST' then 'application/x-www-form-urlencoded'::varchar else null::varchar end,
    case when upper(p_method)='POST' then coalesce(p_form_body,'')::varchar else null::varchar end
  )::extensions.http_request);
  begin v_resp_json:=v_resp.content::jsonb; exception when others then v_resp_json:=jsonb_build_object('raw_non_json',left(coalesce(v_resp.content,''),1000)); end;
  v_digest:=encode(extensions.digest(convert_to(jsonb_build_object('account_ref',v_account_ref,'method',upper(p_method),'path',p_path,'status',v_resp.status,'response',v_resp_json)::text,'UTF8'),'sha256'),'hex');
  return jsonb_build_object(
    'state',case when v_resp.status between 200 and 299 then 'PASS' else 'HOLD_PROVIDER_RESPONSE' end,
    'provider_http_status',v_resp.status,
    'account_role',p_account_role,
    'account_ref',v_account_ref,
    'credential_role',v_custody_role,
    'credential_alias_ref',v_alias,
    'response',v_resp_json,
    'evidence_sha256',v_digest,
    'secret_exposed',false,
    'authority_created',false
  );
end
$fn$;

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
  v_type text;
  v_output text;
  v_ready_states text[]:=array['ready','verified','pass','passed','approved','complete','completed','active','bound','reconciled','certified'];
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  for r in
    select p.*,
      exists(select 1 from integration_control.stripe_payment_link_inventory_v4 pl where pl.price_id=p.stripe_price_id and pl.active=true) as active_link_exists
    from integration_control.pentagreen_mesh_product_profiles_v1 p
    where p.direct_checkout_desired=true
      and lower(coalesce(p.desired_state,''))='enabled'
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
    order by coalesce(p.quality_score,0) desc,p.updated_at,p.offer_code
    limit greatest(1,least(coalesce(p_limit,100),500))
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
          'license_class',r.license_class,'format_profile_id',r.format_profile_id,
          'pricing_authority','PentaPrice','catalog_authority','PentaCatalog/PentaSKU','checkout_authority','PentaCheckout','economic_authority','PentaGreen',
          'pricing_mode','existing_governed_unit_amount','direct_checkout_desired',r.direct_checkout_desired,
          'credit_checkout_desired',r.credit_checkout_desired,'autowire','pentagreen_stripe_autowire_v1')),
        'COMMERCE_PRIMARY',40,'founder_directive_stripe_os_monetization_2026-08-31');
      if v_result->>'state'='QUEUED' then v_queued:=v_queued+1;
      elsif v_result->>'state'='REUSE' then v_reused:=v_reused+1;
      else v_skipped:=v_skipped+1; end if;
    exception when others then v_skipped:=v_skipped+1; end;
  end loop;
  return jsonb_build_object('state','PASS','eligible_seen',v_seen,'queued',v_queued,'reused',v_reused,'skipped',v_skipped,'new_scheduler_created',false,'money_movement',false,'authority_created',false,'observed_at',now());
end
$fn$;

create or replace function integration_control.pentagreen_stripe_commerce_binder_tick_v1(p_limit integer default 20)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public','extensions','chlom_runtime'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  w record;
  q integration_control.pentagreen_stripe_monetization_requests_v1%rowtype;
  p integration_control.pentagreen_mesh_product_profiles_v1%rowtype;
  v_prod_id text; v_price_id text; v_link_id text;
  v_unit bigint; v_currency text; v_billing text; v_interval text; v_name text;
  v_r jsonb; v_j jsonb; v_body text; v_reason text;
  v_done integer:=0; v_hold integer:=0; v_failed integer:=0; v_seen integer:=0;
  v_account_ref text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  for w in
    select * from integration_control.thriveevergreen_mesh_work_queue_v1
    where work_type='stripe_monetization' and role_id='ct.role.thriveevergreen.commerce-binder' and work_state='queued'
    order by priority desc,created_at
    for update skip locked
    limit greatest(1,least(coalesce(p_limit,20),100))
  loop
    v_seen:=v_seen+1; v_reason:=null;
    update integration_control.thriveevergreen_mesh_work_queue_v1 set work_state='executing',attempts=attempts+1,claimed_at=coalesce(claimed_at,now()),updated_at=now() where work_id=w.work_id;
    select * into q from integration_control.pentagreen_stripe_monetization_requests_v1 where work_id=w.work_id for update;
    if not found then update integration_control.thriveevergreen_mesh_work_queue_v1 set work_state='failed',last_error='stripe_request_missing',updated_at=now() where work_id=w.work_id; v_failed:=v_failed+1; continue; end if;
    update integration_control.pentagreen_stripe_monetization_requests_v1 set request_state='executing',updated_at=now() where request_id=q.request_id;

    if q.subject_type='penta_offer' then select * into p from integration_control.pentagreen_mesh_product_profiles_v1 where offer_code=q.subject_ref order by updated_at desc limit 1;
    else select * into p from integration_control.pentagreen_mesh_product_profiles_v1 where sku=q.subject_ref order by updated_at desc limit 1; end if;
    if not found and q.request_type in ('PRODUCT_PRICE','PAYMENT_LINK','REPRICE') then v_reason:='penta_product_profile_missing'; end if;

    if v_reason is null and q.request_type in ('PRODUCT_PRICE','REPRICE') then
      v_unit:=coalesce(nullif(q.payload->>'unit_amount','')::bigint,nullif(p.metadata->>'unit_amount','')::bigint);
      v_currency:=lower(coalesce(nullif(q.payload->>'currency',''),nullif(p.metadata->>'currency',''),'usd'));
      v_billing:=lower(coalesce(nullif(q.payload->>'billing_mode',''),nullif(p.metadata->>'billing_mode',''),'one_time'));
      v_interval:=lower(coalesce(nullif(q.payload->>'recurring_interval',''),nullif(p.metadata->>'recurring_interval','')));
      v_name:=coalesce(nullif(q.payload->>'product_name',''),nullif(p.offer_code,''),nullif(p.sku,''));
      if v_unit is null or v_unit<1 or v_currency !~ '^[a-z]{3}$' or v_name is null then v_reason:='governed_price_or_product_identity_missing'; end if;
      v_prod_id:=coalesce(nullif(q.payload->>'existing_stripe_product_id',''),p.stripe_product_id);
      if v_prod_id is null then select stripe_product_id into v_prod_id from integration_control.pentagreen_mesh_product_profiles_v1 where sku=p.sku and stripe_product_id is not null order by updated_at desc limit 1; end if;
      if v_reason is null and v_prod_id is null then
        v_body:='name='||extensions.urlencode(v_name::varchar)||'&metadata%5Bct_sku%5D='||extensions.urlencode(p.sku::varchar)||'&metadata%5Bct_offer_code%5D='||extensions.urlencode(p.offer_code::varchar)||'&metadata%5Bct_economic_authority%5D=PentaGreen';
        v_r:=integration_control.stripe_os_provider_request_v1(q.account_role,'POST','/v1/products',v_body,q.idempotency_key||':product');
        if v_r->>'state'<>'PASS' then v_reason:='product_create_'||coalesce(v_r->>'state','failed'); else v_j:=v_r->'response'; v_prod_id:=v_j->>'id'; v_account_ref:=v_r->>'account_ref'; end if;
      end if;
      if v_reason is null and v_prod_id is not null then
        v_r:=integration_control.stripe_os_provider_request_v1(q.account_role,'GET','/v1/products/'||v_prod_id,null,null);
        if v_r->>'state'<>'PASS' then v_reason:='product_readback_failed'; else
          v_j:=v_r->'response'; v_account_ref:=v_r->>'account_ref';
          insert into integration_control.stripe_catalog_products_v2(provider_product_id,provider_account_id,active,name,description,images,metadata,tax_code,livemode,default_price_id,provider_created_at,raw,source_sha256,observed_at,updated_at)
          values(v_prod_id,v_account_ref,coalesce((v_j->>'active')::boolean,true),coalesce(v_j->>'name',v_name),v_j->>'description',coalesce(v_j->'images','[]'::jsonb),coalesce(v_j->'metadata','{}'::jsonb),nullif(v_j->>'tax_code',''),coalesce((v_j->>'livemode')::boolean,true),case when jsonb_typeof(v_j->'default_price')='string' then v_j->>'default_price' else v_j#>>'{default_price,id}' end,to_timestamp(coalesce(nullif(v_j->>'created','')::bigint,extract(epoch from now())::bigint)),v_j,encode(extensions.digest(convert_to(v_j::text,'UTF8'),'sha256'),'hex'),now(),now())
          on conflict(provider_product_id) do update set active=excluded.active,name=excluded.name,description=excluded.description,images=excluded.images,metadata=excluded.metadata,tax_code=excluded.tax_code,livemode=excluded.livemode,default_price_id=excluded.default_price_id,raw=excluded.raw,source_sha256=excluded.source_sha256,observed_at=now(),updated_at=now();
        end if;
      end if;
      v_price_id:=case when q.request_type='REPRICE' then null else coalesce(nullif(q.payload->>'existing_stripe_price_id',''),p.stripe_price_id) end;
      if v_reason is null and v_price_id is null then
        v_body:='unit_amount='||v_unit::text||'&currency='||extensions.urlencode(v_currency::varchar)||'&product='||extensions.urlencode(v_prod_id::varchar)||'&metadata%5Bct_sku%5D='||extensions.urlencode(p.sku::varchar)||'&metadata%5Bct_offer_code%5D='||extensions.urlencode(p.offer_code::varchar);
        if v_billing='recurring' then if v_interval not in ('day','week','month','year') then v_reason:='recurring_interval_missing_or_invalid'; else v_body:=v_body||'&recurring%5Binterval%5D='||v_interval; end if; end if;
        if v_reason is null then v_r:=integration_control.stripe_os_provider_request_v1(q.account_role,'POST','/v1/prices',v_body,q.idempotency_key||':price'); if v_r->>'state'<>'PASS' then v_reason:='price_create_'||coalesce(v_r->>'state','failed'); else v_price_id:=v_r#>>'{response,id}'; v_account_ref:=v_r->>'account_ref'; end if; end if;
      end if;
      if v_reason is null and v_price_id is not null then
        v_r:=integration_control.stripe_os_provider_request_v1(q.account_role,'GET','/v1/prices/'||v_price_id,null,null);
        if v_r->>'state'<>'PASS' then v_reason:='price_readback_failed'; else
          v_j:=v_r->'response'; v_account_ref:=v_r->>'account_ref';
          insert into integration_control.stripe_catalog_prices_v2(provider_price_id,provider_product_id,provider_account_id,active,currency,unit_amount,billing_type,recurring_interval,recurring_interval_count,lookup_key,nickname,tax_behavior,livemode,provider_created_at,raw,source_sha256,observed_at,updated_at)
          values(v_price_id,v_prod_id,v_account_ref,coalesce((v_j->>'active')::boolean,true),lower(v_j->>'currency'),nullif(v_j->>'unit_amount','')::bigint,coalesce(v_j->>'type',case when v_j->'recurring' is null then 'one_time' else 'recurring' end),v_j#>>'{recurring,interval}',nullif(v_j#>>'{recurring,interval_count}','')::integer,v_j->>'lookup_key',v_j->>'nickname',v_j->>'tax_behavior',coalesce((v_j->>'livemode')::boolean,true),to_timestamp(coalesce(nullif(v_j->>'created','')::bigint,extract(epoch from now())::bigint)),v_j,encode(extensions.digest(convert_to(v_j::text,'UTF8'),'sha256'),'hex'),now(),now())
          on conflict(provider_price_id) do update set active=excluded.active,currency=excluded.currency,unit_amount=excluded.unit_amount,billing_type=excluded.billing_type,recurring_interval=excluded.recurring_interval,recurring_interval_count=excluded.recurring_interval_count,lookup_key=excluded.lookup_key,nickname=excluded.nickname,tax_behavior=excluded.tax_behavior,livemode=excluded.livemode,raw=excluded.raw,source_sha256=excluded.source_sha256,observed_at=now(),updated_at=now();
          update integration_control.pentagreen_mesh_product_profiles_v1 set stripe_product_id=v_prod_id,stripe_price_id=v_price_id,provider_last_verified_at=now(),metadata=metadata||jsonb_build_object('stripe_mesh','ct.binding.pentagreen-stripe-mesh.v3','stripe_account_ref',v_account_ref,'stripe_bound_at',now()),updated_at=now() where offer_code=p.offer_code;
        end if;
      end if;
      if v_reason is null and p.direct_checkout_desired then
        v_body:='line_items%5B0%5D%5Bprice%5D='||extensions.urlencode(v_price_id::varchar)||'&line_items%5B0%5D%5Bquantity%5D=1&metadata%5Bct_sku%5D='||extensions.urlencode(p.sku::varchar)||'&metadata%5Bct_offer_code%5D='||extensions.urlencode(p.offer_code::varchar);
        v_r:=integration_control.stripe_os_provider_request_v1(q.account_role,'POST','/v1/payment_links',v_body,q.idempotency_key||':payment_link');
        if v_r->>'state'='PASS' then v_link_id:=v_r#>>'{response,id}'; else v_reason:='payment_link_create_'||coalesce(v_r->>'state','failed'); end if;
      end if;
    elsif v_reason is null and q.request_type='PAYMENT_LINK' then
      v_prod_id:=coalesce(nullif(q.payload->>'existing_stripe_product_id',''),p.stripe_product_id); v_price_id:=coalesce(nullif(q.payload->>'existing_stripe_price_id',''),p.stripe_price_id);
      if v_price_id is null then v_reason:='stripe_price_binding_missing'; else
        v_body:='line_items%5B0%5D%5Bprice%5D='||extensions.urlencode(v_price_id::varchar)||'&line_items%5B0%5D%5Bquantity%5D=1&metadata%5Bct_sku%5D='||extensions.urlencode(p.sku::varchar)||'&metadata%5Bct_offer_code%5D='||extensions.urlencode(p.offer_code::varchar);
        v_r:=integration_control.stripe_os_provider_request_v1(q.account_role,'POST','/v1/payment_links',v_body,q.idempotency_key||':payment_link'); if v_r->>'state'='PASS' then v_link_id:=v_r#>>'{response,id}'; v_account_ref:=v_r->>'account_ref'; else v_reason:='payment_link_create_'||coalesce(v_r->>'state','failed'); end if;
      end if;
    elsif v_reason is null and q.request_type='WEBHOOK_BINDING' then
      v_r:=integration_control.stripe_webhook_provider_reconcile_v3(true); if v_r->>'state' not in ('PASS','DEGRADED') then v_reason:='webhook_reconcile_failed'; end if;
    elsif v_reason is null and q.request_type='CATALOG_SYNC' then
      perform integration_control.stripe_product_inventory_refresh_v3(100);
    elsif v_reason is null then
      v_reason:='specialized_executor_required_for_'||lower(q.request_type);
    end if;

    if v_reason is null and v_link_id is not null then
      v_r:=integration_control.stripe_os_provider_request_v1(q.account_role,'GET','/v1/payment_links/'||v_link_id,null,null);
      if v_r->>'state'<>'PASS' then v_reason:='payment_link_readback_failed'; else
        v_j:=v_r->'response'; v_account_ref:=v_r->>'account_ref';
        insert into integration_control.stripe_payment_link_inventory_v4(payment_link_id,provider_account_id,url,active,product_id,price_id,metadata,raw,source_run_id,observed_at,created_at,updated_at)
        values(v_link_id,v_account_ref,v_j->>'url',coalesce((v_j->>'active')::boolean,true),v_prod_id,v_price_id,coalesce(v_j->'metadata','{}'::jsonb),v_j,null,now(),now(),now())
        on conflict(payment_link_id) do update set url=excluded.url,active=excluded.active,product_id=excluded.product_id,price_id=excluded.price_id,metadata=excluded.metadata,raw=excluded.raw,observed_at=now(),updated_at=now();
      end if;
    end if;

    if v_reason is null then
      update integration_control.pentagreen_stripe_monetization_requests_v1 set request_state='complete',stripe_product_id=coalesce(v_prod_id,stripe_product_id),stripe_price_id=coalesce(v_price_id,stripe_price_id),stripe_payment_link_id=coalesce(v_link_id,stripe_payment_link_id),result=jsonb_build_object('state','PASS','account_ref',v_account_ref,'product_id',v_prod_id,'price_id',v_price_id,'payment_link_id',v_link_id,'money_movement',false,'authority_created',false),updated_at=now() where request_id=q.request_id;
      update integration_control.thriveevergreen_mesh_work_queue_v1 set work_state='verified',completed_at=now(),last_error=null,updated_at=now() where work_id=w.work_id; v_done:=v_done+1;
    else
      update integration_control.pentagreen_stripe_monetization_requests_v1 set request_state='hold',result=jsonb_build_object('state','HOLD','reason',v_reason,'money_movement',false,'authority_created',false),updated_at=now() where request_id=q.request_id;
      update integration_control.thriveevergreen_mesh_work_queue_v1 set work_state='blocked',last_error=v_reason,updated_at=now() where work_id=w.work_id; v_hold:=v_hold+1;
    end if;
  end loop;
  return jsonb_build_object('state','PASS','seen',v_seen,'completed',v_done,'held',v_hold,'failed',v_failed,'money_movement',false,'new_clock_created',false,'observed_at',now());
end
$fn$;

revoke all on function integration_control.stripe_os_provider_request_v1(text,text,text,text,text) from public,anon,authenticated;
revoke all on function integration_control.pentagreen_stripe_commerce_binder_tick_v1(integer) from public,anon,authenticated;
grant execute on function integration_control.stripe_os_provider_request_v1(text,text,text,text,text),integration_control.pentagreen_stripe_commerce_binder_tick_v1(integer) to service_role;

create or replace function integration_control.thriveevergreen_commerce_mesh_cycle_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'integration_control','public'
as $fn$
declare
  v_id uuid:=gen_random_uuid(); a jsonb; b jsonb; c jsonb; d jsonb; e jsonb; f jsonb; s jsonb;
begin
  insert into integration_control.thriveevergreen_mesh_cycle_receipts_v1(cycle_id) values(v_id);
  a:=integration_control.thriveevergreen_mesh_seed_catalog_v1();
  b:=integration_control.thriveevergreen_mesh_reconcile_routes_v1();
  c:=integration_control.thriveevergreen_mesh_enqueue_gaps_v1();
  d:=integration_control.thriveevergreen_mesh_reconcile_replicas_v1();
  e:=integration_control.pentagreen_stripe_autowire_v1(100);
  f:=integration_control.pentagreen_stripe_commerce_binder_tick_v1(20);
  s:=public.thriveevergreen_commerce_mesh_status_v1()||jsonb_build_object('stripe_autowire',e,'stripe_commerce_binder',f,'stripe_mesh','ct.binding.pentagreen-stripe-mesh.v3');
  update integration_control.thriveevergreen_mesh_cycle_receipts_v1 set cycle_completed_at=now(),seed_result=a,route_result=b,queue_result=c,replica_result=d,status_snapshot=s,result_state='pass' where cycle_id=v_id;
  return jsonb_build_object('cycle_id',v_id,'state','pass','seed',a,'routes',b,'queue',c,'replicas',d,'stripe_autowire',e,'stripe_commerce_binder',f,'status',s);
exception when others then
  update integration_control.thriveevergreen_mesh_cycle_receipts_v1 set cycle_completed_at=now(),result_state='error',status_snapshot=jsonb_build_object('error',sqlerrm) where cycle_id=v_id; raise;
end
$fn$;
