-- Forward-only repair for the production-applied Stripe OS runtime.
-- The prior provider-request signature remains only as a private, exact-route
-- transport helper. All callers use typed operation IDs through v2.

alter table integration_control.stripe_catalog_prices_v2
  add column if not exists provider_account_id text;

create index if not exists stripe_catalog_prices_v2_account_price_idx
  on integration_control.stripe_catalog_prices_v2(provider_account_id, provider_price_id);

update integration_control.stripe_catalog_prices_v2 pr
set provider_account_id=p.provider_account_id
from integration_control.stripe_catalog_products_v2 p
where p.provider_product_id=pr.provider_product_id
  and pr.provider_account_id is null
  and p.provider_account_id is not null;

create table if not exists integration_control.stripe_os_provider_operation_receipts_v2 (
  receipt_id uuid primary key default gen_random_uuid(),
  request_id uuid,
  operation_key text not null,
  account_role text not null,
  account_ref text,
  resource_ref text,
  provider_http_status integer,
  result_state text not null,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  credential_role text,
  secret_exposed boolean not null default false,
  authority_created boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default clock_timestamp()
);

alter table integration_control.stripe_os_provider_operation_receipts_v2 enable row level security;
revoke all on integration_control.stripe_os_provider_operation_receipts_v2 from public, anon, authenticated;
grant select on integration_control.stripe_os_provider_operation_receipts_v2 to service_role;

create or replace function integration_control.stripe_os_provider_request_v1(
  p_account_role text,
  p_method text,
  p_path text,
  p_form_body text default null,
  p_idempotency_key text default null
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_account_ref text;
  v_lane record;
  v_cap record;
  v_request integration_control.pentagreen_stripe_monetization_requests_v1%rowtype;
  v_secret text;
  v_probe extensions.http_response;
  v_probe_json jsonb;
  v_resp extensions.http_response;
  v_resp_json jsonb;
  v_safe_response jsonb;
  v_headers extensions.http_header[];
  v_alias text;
  v_custody_role text;
  v_method extensions.http_method;
  v_digest text;
  v_operation text;
  v_capability_key text;
  v_resource_ref text;
  v_allowed_keys text[];
  v_keys text[];
  v_required_keys text[];
  v_part text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;
  if upper(coalesce(p_method,'')) not in ('GET','POST') then
    raise exception 'stripe_adapter_method_not_allowed';
  end if;
  if p_path is null or length(p_path)>180 or p_path ~ '[?#]' or p_path ~* '(%2f|%5c|%2e|\.\.)' then
    raise exception 'stripe_adapter_exact_path_required';
  end if;

  if upper(p_method)='GET' and p_path='/v1/account' then
    v_operation:='account.retrieve'; v_capability_key:='stripe.account';
  elsif upper(p_method)='GET' and p_path ~ '^/v1/products/prod_[A-Za-z0-9]+$' then
    v_operation:='product.retrieve'; v_capability_key:='stripe.products'; v_resource_ref:=regexp_replace(p_path,'^.*/','');
  elsif upper(p_method)='GET' and p_path ~ '^/v1/prices/(price|plan)_[A-Za-z0-9]+$' then
    v_operation:='price.retrieve'; v_capability_key:='stripe.prices'; v_resource_ref:=regexp_replace(p_path,'^.*/','');
  elsif upper(p_method)='GET' and p_path ~ '^/v1/payment_links/plink_[A-Za-z0-9]+$' then
    v_operation:='payment_link.retrieve'; v_capability_key:='stripe.payment_links'; v_resource_ref:=regexp_replace(p_path,'^.*/','');
  elsif upper(p_method)='POST' and p_path='/v1/products' then
    v_operation:='product.create'; v_capability_key:='stripe.products';
    v_allowed_keys:=array['name','tax_code','metadata%5Bct_sku%5D','metadata%5Bct_offer_code%5D','metadata%5Bct_economic_authority%5D'];
    v_required_keys:=array['name','tax_code','metadata%5Bct_sku%5D','metadata%5Bct_offer_code%5D'];
  elsif upper(p_method)='POST' and p_path='/v1/prices' then
    v_operation:='price.create'; v_capability_key:='stripe.prices';
    v_allowed_keys:=array['unit_amount','currency','product','tax_behavior','recurring%5Binterval%5D','metadata%5Bct_sku%5D','metadata%5Bct_offer_code%5D'];
    v_required_keys:=array['unit_amount','currency','product','tax_behavior','metadata%5Bct_sku%5D','metadata%5Bct_offer_code%5D'];
  elsif upper(p_method)='POST' and p_path='/v1/payment_links' then
    v_operation:='payment_link.create'; v_capability_key:='stripe.payment_links';
    v_allowed_keys:=array['line_items%5B0%5D%5Bprice%5D','line_items%5B0%5D%5Bquantity%5D','automatic_tax%5Benabled%5D','metadata%5Bct_sku%5D','metadata%5Bct_offer_code%5D','metadata%5Bct_entitlement_handler_ref%5D','metadata%5Bct_webhook_binding_key%5D'];
    v_required_keys:=array['line_items%5B0%5D%5Bprice%5D','line_items%5B0%5D%5Bquantity%5D','metadata%5Bct_sku%5D','metadata%5Bct_offer_code%5D','metadata%5Bct_entitlement_handler_ref%5D','metadata%5Bct_webhook_binding_key%5D'];
  else
    raise exception 'stripe_adapter_typed_route_not_allowed';
  end if;

  select * into v_cap
  from integration_control.stripe_os_capabilities_v1
  where capability_key=v_capability_key;
  if not found or (upper(p_method)='GET' and not coalesce(v_cap.read_allowed,false)) then
    raise exception 'stripe_capability_read_not_allowed';
  end if;
  if upper(p_method)='POST' and (
    not coalesce(v_cap.provider_write_allowed,false)
    or not coalesce(v_cap.monetization_write_allowed,false)
    or coalesce(v_cap.d3_or_human_gate_required,false)
  ) then
    raise exception 'stripe_capability_write_not_allowed';
  end if;

  if upper(p_method)='POST' then
    if p_idempotency_key is null or length(p_idempotency_key)<66 or length(p_idempotency_key)>255
       or p_idempotency_key !~ '^[0-9a-f]{64}:[a-z_]+$' then
      raise exception 'stripe_idempotency_key_required';
    end if;
    if p_form_body is null or length(p_form_body)>5000 or p_form_body ~ E'[\\r\\n]' then
      raise exception 'stripe_form_body_invalid';
    end if;
    v_keys:=array[]::text[];
    foreach v_part in array string_to_array(p_form_body,'&') loop
      if v_part='' or position('=' in v_part)=0 or split_part(v_part,'=',1)<>all(v_allowed_keys) then
        raise exception 'stripe_form_parameter_not_allowed';
      end if;
      if split_part(v_part,'=',1)=any(v_keys) then
        raise exception 'stripe_duplicate_form_parameter';
      end if;
      v_keys:=array_append(v_keys,split_part(v_part,'=',1));
    end loop;
    if not (v_keys @> v_required_keys) then
      raise exception 'stripe_required_form_parameter_missing';
    end if;
    select * into v_request
    from integration_control.pentagreen_stripe_monetization_requests_v1
    where idempotency_key=split_part(p_idempotency_key,':',1)
      and account_role=p_account_role
      and request_state='executing';
    if not found then raise exception 'stripe_executing_request_binding_required'; end if;
    if v_operation in ('product.create','price.create') and v_request.request_type not in ('PRODUCT_PRICE','REPRICE') then
      raise exception 'stripe_operation_request_type_mismatch';
    end if;
    if v_operation='payment_link.create' and v_request.request_type not in ('PRODUCT_PRICE','PAYMENT_LINK') then
      raise exception 'stripe_operation_request_type_mismatch';
    end if;
  end if;

  select account_ref into v_account_ref
  from integration_control.stripe_os_accounts_v1
  where account_role=p_account_role and livemode=true and provider_state like 'provider_live_verified%'
  order by route_priority limit 1;
  if v_account_ref is null then
    return jsonb_build_object('state','HOLD_ACCOUNT_ROLE_NOT_AVAILABLE','account_role',p_account_role,'secret_exposed',false);
  end if;

  for v_lane in
    select * from integration_control.stripe_live_secret_lanes_v1
    where enabled=true and platform_failover_eligible=true and independent_material=true
      and custody_role in ('HOT','WARM','COLD')
    order by priority
  loop
    begin
      v_secret:=public.get_runtime_secret(v_lane.vault_alias);
      if nullif(v_secret,'') is null then continue; end if;
      v_probe:=chlom_runtime.dail_http_v1((
        'GET'::extensions.http_method,
        'https://api.stripe.com/v1/account'::varchar,
        array[
          row('Authorization','Bearer '||v_secret)::extensions.http_header,
          row('Accept','application/json')::extensions.http_header,
          row('Stripe-Version','2026-07-29.dahlia')::extensions.http_header,
          row('User-Agent','CrownThrive-Stripe-OS-v2')::extensions.http_header
        ],null::varchar,null::varchar
      )::extensions.http_request);
      if v_probe.status=200 then
        begin v_probe_json:=v_probe.content::jsonb; exception when others then v_probe_json:='{}'::jsonb; end;
        if v_probe_json->>'id'=v_account_ref then
          v_alias:=v_lane.vault_alias; v_custody_role:=v_lane.custody_role; exit;
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
    row('Stripe-Version','2026-07-29.dahlia')::extensions.http_header,
    row('User-Agent','CrownThrive-Stripe-OS-v2')::extensions.http_header
  ];
  if upper(p_method)='POST' then
    v_headers:=v_headers||array[
      row('Content-Type','application/x-www-form-urlencoded')::extensions.http_header,
      row('Idempotency-Key',p_idempotency_key)::extensions.http_header
    ];
  end if;
  v_method:=upper(p_method)::extensions.http_method;
  begin
    v_resp:=chlom_runtime.dail_http_v1((
      v_method,('https://api.stripe.com'||p_path)::varchar,v_headers,
      case when upper(p_method)='POST' then 'application/x-www-form-urlencoded'::varchar else null::varchar end,
      case when upper(p_method)='POST' then p_form_body::varchar else null::varchar end
    )::extensions.http_request);
    begin v_resp_json:=v_resp.content::jsonb; exception when others then v_resp_json:='{}'::jsonb; end;
  exception when others then
    v_digest:=encode(extensions.digest(convert_to(jsonb_build_object('operation',v_operation,'account_ref',v_account_ref,'transport_error',sqlstate)::text,'UTF8'),'sha256'),'hex');
    insert into integration_control.stripe_os_provider_operation_receipts_v2(request_id,operation_key,account_role,account_ref,resource_ref,result_state,evidence_sha256,credential_role,metadata)
    values(case when upper(p_method)='POST' then v_request.request_id else null end,v_operation,p_account_role,v_account_ref,v_resource_ref,'HOLD_TRANSPORT_ERROR',v_digest,v_custody_role,jsonb_build_object('sqlstate',sqlstate,'api_version','2026-07-29.dahlia'));
    return jsonb_build_object('state','HOLD_TRANSPORT_ERROR','account_role',p_account_role,'account_ref',v_account_ref,'evidence_sha256',v_digest,'secret_exposed',false);
  end;

  if v_operation='account.retrieve' then
    v_safe_response:=jsonb_strip_nulls(jsonb_build_object('id',v_resp_json->>'id','country',v_resp_json->>'country','default_currency',v_resp_json->>'default_currency','charges_enabled',v_resp_json->'charges_enabled','payouts_enabled',v_resp_json->'payouts_enabled','details_submitted',v_resp_json->'details_submitted'));
  elsif v_operation like 'product.%' then
    v_safe_response:=jsonb_strip_nulls(jsonb_build_object('id',v_resp_json->>'id','object',v_resp_json->>'object','active',v_resp_json->'active','name',v_resp_json->>'name','description',v_resp_json->>'description','default_price',v_resp_json->'default_price','statement_descriptor',v_resp_json->>'statement_descriptor','tax_code',v_resp_json->>'tax_code','metadata',coalesce(v_resp_json->'metadata','{}'::jsonb),'created',v_resp_json->'created'));
  elsif v_operation like 'price.%' then
    v_safe_response:=jsonb_strip_nulls(jsonb_build_object('id',v_resp_json->>'id','object',v_resp_json->>'object','active',v_resp_json->'active','currency',v_resp_json->>'currency','unit_amount',v_resp_json->'unit_amount','type',v_resp_json->>'type','product',v_resp_json->'product','recurring',v_resp_json->'recurring','lookup_key',v_resp_json->>'lookup_key','nickname',v_resp_json->>'nickname','tax_behavior',v_resp_json->>'tax_behavior','metadata',coalesce(v_resp_json->'metadata','{}'::jsonb),'created',v_resp_json->'created'));
  elsif v_operation like 'payment_link.%' then
    v_safe_response:=jsonb_strip_nulls(jsonb_build_object('id',v_resp_json->>'id','object',v_resp_json->>'object','active',v_resp_json->'active','url',v_resp_json->>'url','automatic_tax',v_resp_json->'automatic_tax','metadata',coalesce(v_resp_json->'metadata','{}'::jsonb),'created',v_resp_json->'created'));
  else
    v_safe_response:='{}'::jsonb;
  end if;
  if v_resp.status<200 or v_resp.status>299 then
    v_safe_response:=jsonb_strip_nulls(jsonb_build_object('error_type',v_resp_json#>>'{error,type}','error_code',v_resp_json#>>'{error,code}','error_param',v_resp_json#>>'{error,param}'));
  end if;
  v_resource_ref:=coalesce(v_resource_ref,v_safe_response->>'id');
  v_digest:=encode(extensions.digest(convert_to(jsonb_build_object('account_ref',v_account_ref,'operation',v_operation,'status',v_resp.status,'response',v_safe_response)::text,'UTF8'),'sha256'),'hex');
  insert into integration_control.stripe_os_provider_operation_receipts_v2(request_id,operation_key,account_role,account_ref,resource_ref,provider_http_status,result_state,evidence_sha256,credential_role,metadata)
  values(case when upper(p_method)='POST' then v_request.request_id else null end,v_operation,p_account_role,v_account_ref,v_resource_ref,v_resp.status,case when v_resp.status between 200 and 299 then 'PASS' else 'HOLD_PROVIDER_RESPONSE' end,v_digest,v_custody_role,jsonb_build_object('api_version','2026-07-29.dahlia','response_content_copied',false,'request_content_copied',false));
  return jsonb_build_object('state',case when v_resp.status between 200 and 299 then 'PASS' else 'HOLD_PROVIDER_RESPONSE' end,'provider_http_status',v_resp.status,'operation',v_operation,'account_role',p_account_role,'account_ref',v_account_ref,'credential_role',v_custody_role,'credential_alias_ref',v_alias,'response',v_safe_response,'evidence_sha256',v_digest,'secret_exposed',false,'authority_created',false);
end
$fn$;

create or replace function integration_control.stripe_os_provider_operation_v2(
  p_request_id uuid,
  p_operation text,
  p_resource_ref text default null,
  p_payload jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $fn$
declare
  q integration_control.pentagreen_stripe_monetization_requests_v1%rowtype;
  v_body text;
  v_name text;
  v_sku text;
  v_offer text;
  v_tax_code text;
  v_tax_behavior text;
  v_currency text;
  v_billing text;
  v_interval text;
  v_handler text;
  v_webhook text;
  v_unit bigint;
  v_suffix text;
begin
  select * into q from integration_control.pentagreen_stripe_monetization_requests_v1
  where request_id=p_request_id and request_state='executing';
  if not found then raise exception 'executing_stripe_request_required'; end if;
  if jsonb_typeof(coalesce(p_payload,'{}'::jsonb))<>'object' then raise exception 'stripe_typed_payload_object_required'; end if;

  v_sku:=nullif(p_payload->>'sku',''); v_offer:=nullif(p_payload->>'offer_code','');
  if p_operation='product.create' then
    v_name:=nullif(p_payload->>'name',''); v_tax_code:=nullif(p_payload->>'tax_code','');
    if q.request_type not in ('PRODUCT_PRICE','REPRICE') or v_name is null or length(v_name)>250 or v_sku is null or v_offer is null or v_tax_code !~ '^txcd_[0-9]+$' then raise exception 'invalid_product_create_contract'; end if;
    v_body:='name='||extensions.urlencode(v_name::varchar)||'&tax_code='||extensions.urlencode(v_tax_code::varchar)||'&metadata%5Bct_sku%5D='||extensions.urlencode(v_sku::varchar)||'&metadata%5Bct_offer_code%5D='||extensions.urlencode(v_offer::varchar)||'&metadata%5Bct_economic_authority%5D=PentaGreen';
    v_suffix:='product';
    return integration_control.stripe_os_provider_request_v1(q.account_role,'POST','/v1/products',v_body,q.idempotency_key||':'||v_suffix);
  elsif p_operation='product.retrieve' then
    if coalesce(p_resource_ref,'') !~ '^prod_[A-Za-z0-9]+$' then raise exception 'invalid_product_ref'; end if;
    return integration_control.stripe_os_provider_request_v1(q.account_role,'GET','/v1/products/'||p_resource_ref,null,null);
  elsif p_operation='price.create' then
    v_unit:=nullif(p_payload->>'unit_amount','')::bigint; v_currency:=lower(nullif(p_payload->>'currency','')); v_billing:=lower(coalesce(nullif(p_payload->>'billing_mode',''),'one_time')); v_interval:=lower(nullif(p_payload->>'recurring_interval','')); v_tax_behavior:=lower(nullif(p_payload->>'tax_behavior',''));
    if q.request_type not in ('PRODUCT_PRICE','REPRICE') or coalesce(p_resource_ref,'') !~ '^prod_[A-Za-z0-9]+$' or v_unit is null or v_unit<1 or coalesce(v_currency,'') !~ '^[a-z]{3}$' or v_tax_behavior is null or v_tax_behavior not in ('inclusive','exclusive') or v_sku is null or v_offer is null then raise exception 'invalid_price_create_contract'; end if;
    v_body:='unit_amount='||v_unit::text||'&currency='||extensions.urlencode(v_currency::varchar)||'&product='||extensions.urlencode(p_resource_ref::varchar)||'&tax_behavior='||v_tax_behavior||'&metadata%5Bct_sku%5D='||extensions.urlencode(v_sku::varchar)||'&metadata%5Bct_offer_code%5D='||extensions.urlencode(v_offer::varchar);
    if v_billing='recurring' then
      if v_interval not in ('day','week','month','year') then raise exception 'invalid_recurring_interval'; end if;
      v_body:=v_body||'&recurring%5Binterval%5D='||v_interval;
    elsif v_billing<>'one_time' then raise exception 'invalid_billing_mode'; end if;
    return integration_control.stripe_os_provider_request_v1(q.account_role,'POST','/v1/prices',v_body,q.idempotency_key||':price');
  elsif p_operation='price.retrieve' then
    if coalesce(p_resource_ref,'') !~ '^(price|plan)_[A-Za-z0-9]+$' then raise exception 'invalid_price_ref'; end if;
    return integration_control.stripe_os_provider_request_v1(q.account_role,'GET','/v1/prices/'||p_resource_ref,null,null);
  elsif p_operation='payment_link.create' then
    v_handler:=nullif(p_payload->>'entitlement_handler_ref',''); v_webhook:=nullif(p_payload->>'webhook_binding_key','');
    if q.request_type not in ('PRODUCT_PRICE','PAYMENT_LINK') or coalesce(p_resource_ref,'') !~ '^(price|plan)_[A-Za-z0-9]+$' or v_sku is null or v_offer is null or v_handler is null or v_webhook is null then raise exception 'invalid_payment_link_create_contract'; end if;
    v_body:='line_items%5B0%5D%5Bprice%5D='||extensions.urlencode(p_resource_ref::varchar)||'&line_items%5B0%5D%5Bquantity%5D=1&metadata%5Bct_sku%5D='||extensions.urlencode(v_sku::varchar)||'&metadata%5Bct_offer_code%5D='||extensions.urlencode(v_offer::varchar)||'&metadata%5Bct_entitlement_handler_ref%5D='||extensions.urlencode(v_handler::varchar)||'&metadata%5Bct_webhook_binding_key%5D='||extensions.urlencode(v_webhook::varchar);
    if coalesce((p_payload->>'automatic_tax_enabled')::boolean,false) then v_body:=v_body||'&automatic_tax%5Benabled%5D=true'; end if;
    return integration_control.stripe_os_provider_request_v1(q.account_role,'POST','/v1/payment_links',v_body,q.idempotency_key||':payment_link');
  elsif p_operation='payment_link.retrieve' then
    if coalesce(p_resource_ref,'') !~ '^plink_[A-Za-z0-9]+$' then raise exception 'invalid_payment_link_ref'; end if;
    return integration_control.stripe_os_provider_request_v1(q.account_role,'GET','/v1/payment_links/'||p_resource_ref,null,null);
  else
    raise exception 'unsupported_stripe_typed_operation';
  end if;
end
$fn$;

revoke all on function integration_control.stripe_os_provider_request_v1(text,text,text,text,text) from public,anon,authenticated,service_role;
revoke all on function integration_control.stripe_os_provider_operation_v2(uuid,text,text,jsonb) from public,anon,authenticated,service_role;

comment on function integration_control.stripe_os_provider_request_v1(text,text,text,text,text) is
  'Private exact-route Stripe transport. Superseded for callers by stripe_os_provider_operation_v2; never grant to API roles.';
comment on function integration_control.stripe_os_provider_operation_v2(uuid,text,text,jsonb) is
  'Private typed Stripe catalog operation adapter. Invoked only by the governed Commerce Binder owner context.';
