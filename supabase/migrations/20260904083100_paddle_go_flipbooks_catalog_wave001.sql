create table if not exists integration_control.paddle_catalog_sync_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  wave_id text not null,
  apply_requested boolean not null,
  state text not null,
  manifest_digest text not null,
  provider_write boolean not null default false,
  summary jsonb not null default '{}'::jsonb,
  provider_objects jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default clock_timestamp()
);

alter table integration_control.paddle_catalog_sync_receipts_v1 enable row level security;
revoke all on table integration_control.paddle_catalog_sync_receipts_v1 from public, anon, authenticated;
grant select, insert on table integration_control.paddle_catalog_sync_receipts_v1 to service_role;

create or replace function integration_control.paddle_go_flipbooks_wave001_v1(p_apply boolean default false)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public','extensions','vault','chlom_runtime','pg_temp'
as $function$
declare
  v_claims text := nullif(current_setting('request.jwt.claims',true),'');
  v_role text := '';
  v_secret text;
  v_now timestamptz := clock_timestamp();
  v_base text := 'https://api.paddle.com';
  v_resp extensions.http_response;
  v_body jsonb := '{}'::jsonb;
  v_catalog jsonb := '{}'::jsonb;
  v_prices_body jsonb := '{}'::jsonb;
  v_readback jsonb := '{}'::jsonb;
  v_payload jsonb;
  v_desired jsonb;
  v_product jsonb;
  v_price jsonb;
  v_entity jsonb;
  v_provider_product jsonb;
  v_provider_price jsonb;
  v_product_result jsonb;
  v_price_result jsonb;
  v_products_result jsonb := '[]'::jsonb;
  v_price_results jsonb;
  v_stable_id text;
  v_product_id text;
  v_price_id text;
  v_price_key text;
  v_match_count integer;
  v_name_conflict_count integer;
  v_created_products integer := 0;
  v_existing_products integer := 0;
  v_created_prices integer := 0;
  v_existing_prices integer := 0;
  v_holds integer := 0;
  v_provider_write boolean := false;
  v_state text := 'HOLD';
  v_manifest_digest text;
  v_result jsonb;
  v_receipt_id uuid;
begin
  if v_claims is not null and v_claims ~ '^\s*\{' then
    v_role := coalesce(v_claims::jsonb->>'role','');
  end if;
  if session_user not in ('postgres','supabase_admin')
     and current_user <> 'service_role' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  v_desired := jsonb_build_object(
    'contract','ct.paddle.catalog-wave.v1',
    'wave_id','ct.paddle.catalog.go-flipbooks.wave-001',
    'source_contract','ct.pentagreen.go-flipbooks-standard-pro.v1',
    'source_sha','91e2880b17fcb8269491a82099053beb484c8b6b',
    'currency','USD',
    'products', jsonb_build_array(
      jsonb_build_object(
        'stable_id','ct.product.go-flipbooks.standard',
        'name','Go Flipbooks Standard',
        'description','Hosted static interactive publication packages for creators, publishers, educators, ministries, businesses, organizations, catalogs, and campaigns.',
        'tax_category','saas',
        'custom_data',jsonb_build_object(
          'ct_stable_id','ct.product.go-flipbooks.standard',
          'ct_catalog_wave','ct.paddle.catalog.go-flipbooks.wave-001',
          'ct_brand','ct.platform.go-flipbooks',
          'ct_fulfillment_profile','go_flipbooks_standard_v1',
          'ct_public_route','https://go-flipbooks.vercel.app/standard',
          'ct_source_contract','ct.pentagreen.go-flipbooks-standard-pro.v1'
        ),
        'prices',jsonb_build_array(
          jsonb_build_object('key','launch','name','Launch','description','Go Flipbooks Standard — Launch — 1 publication — one-time','amount_minor','2900','billing_cycle','null'::jsonb,'custom_data',jsonb_build_object('ct_price_key','launch','ct_publication_capacity',1,'ct_billing','one_time')),
          jsonb_build_object('key','studio','name','Studio','description','Go Flipbooks Standard — Studio — 5 publications — one-time','amount_minor','9900','billing_cycle','null'::jsonb,'custom_data',jsonb_build_object('ct_price_key','studio','ct_publication_capacity',5,'ct_billing','one_time')),
          jsonb_build_object('key','commerce','name','Commerce','description','Go Flipbooks Standard — Commerce — 25 publications — one-time','amount_minor','24900','billing_cycle','null'::jsonb,'custom_data',jsonb_build_object('ct_price_key','commerce','ct_publication_capacity',25,'ct_billing','one_time')),
          jsonb_build_object('key','managed_standard','name','Managed Standard','description','Go Flipbooks Standard — managed hosting add-on — monthly','amount_minor','4900','billing_cycle',jsonb_build_object('interval','month','frequency',1),'custom_data',jsonb_build_object('ct_price_key','managed_standard','ct_role','managed_hosting_add_on','ct_billing','monthly'))
        )
      ),
      jsonb_build_object(
        'stable_id','ct.product.go-flipbooks.pro',
        'name','Go Flipbooks PRO',
        'description','Managed automated interactive publication with implementation, publication automation, delivery, lead and analytics integration, and lifecycle processing.',
        'tax_category','saas',
        'custom_data',jsonb_build_object(
          'ct_stable_id','ct.product.go-flipbooks.pro',
          'ct_catalog_wave','ct.paddle.catalog.go-flipbooks.wave-001',
          'ct_brand','ct.platform.go-flipbooks',
          'ct_fulfillment_profile','go_flipbooks_pro_v1',
          'ct_public_route','https://go-flipbooks.vercel.app/pro',
          'ct_source_contract','ct.pentagreen.go-flipbooks-standard-pro.v1'
        ),
        'prices',jsonb_build_array(
          jsonb_build_object('key','pro_setup','name','PRO Setup','description','Go Flipbooks PRO — implementation setup — one-time','amount_minor','29700','billing_cycle','null'::jsonb,'custom_data',jsonb_build_object('ct_price_key','pro_setup','ct_role','setup','ct_billing','one_time')),
          jsonb_build_object('key','pro_monthly','name','PRO Monthly','description','Go Flipbooks PRO — managed automation — monthly','amount_minor','2900','billing_cycle',jsonb_build_object('interval','month','frequency',1),'custom_data',jsonb_build_object('ct_price_key','pro_monthly','ct_role','recurring','ct_billing','monthly'))
        )
      )
    )
  );

  v_manifest_digest := encode(extensions.digest(convert_to(v_desired::text,'UTF8'),'sha256'),'hex');

  v_secret := public.get_runtime_secret(coalesce((integration_control.penta_wire_select_route_v3('paddle_crownthrive',false)->>'credential_reference'),'Penta_Paddle_Hot'));
  if coalesce(v_secret,'') = '' then
    v_result := jsonb_build_object(
      'contract','ct.paddle.catalog-sync-receipt.v1','wave_id',v_desired->>'wave_id',
      'state','HOLD_CREDENTIAL_RESOLUTION_FAILED','provider_write',false,
      'credential_exposed',false,'secret_value_returned',false,'manifest_digest',v_manifest_digest,
      'observed_at',v_now
    );
    insert into integration_control.paddle_catalog_sync_receipts_v1(wave_id,apply_requested,state,manifest_digest,provider_write,summary,provider_objects)
    values(v_desired->>'wave_id',p_apply,v_result->>'state',v_manifest_digest,false,v_result,'[]'::jsonb)
    returning receipt_id into v_receipt_id;
    return v_result || jsonb_build_object('receipt_id',v_receipt_id);
  end if;

  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','20000');
  perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS','5000');

  v_resp := chlom_runtime.dail_http_v1((row(
    'GET'::extensions.http_method,
    (v_base||'/products?status=active&per_page=200')::varchar,
    array[
      extensions.http_header('Authorization'::varchar,('Bearer '||v_secret)::varchar),
      extensions.http_header('Accept'::varchar,'application/json'::varchar),
      extensions.http_header('Paddle-Version'::varchar,'1'::varchar),
      extensions.http_header('User-Agent'::varchar,'CrownThrive-Paddle-Catalog/1.0'::varchar)
    ]::extensions.http_header[],
    null::varchar,
    null::varchar
  )::extensions.http_request));
  begin v_catalog := coalesce(v_resp.content,'{}')::jsonb; exception when others then v_catalog := '{}'::jsonb; end;
  if v_resp.status <> 200 then
    raise exception 'paddle_catalog_read_failed:%',v_resp.status;
  end if;
  if coalesce((v_catalog#>>'{meta,pagination,has_more}')::boolean,false) then
    raise exception 'paddle_catalog_pagination_requires_extension';
  end if;

  for v_product in select value from jsonb_array_elements(v_desired->'products')
  loop
    v_stable_id := v_product->>'stable_id';
    v_product_result := jsonb_build_object('stable_id',v_stable_id,'name',v_product->>'name','prices','[]'::jsonb);
    v_match_count := 0;
    v_name_conflict_count := 0;
    v_provider_product := null;

    for v_entity in select value from jsonb_array_elements(coalesce(v_catalog->'data','[]'::jsonb))
    loop
      if v_entity#>>'{custom_data,ct_stable_id}' = v_stable_id then
        v_match_count := v_match_count + 1;
        v_provider_product := v_entity;
      elsif v_entity->>'name' = v_product->>'name' then
        v_name_conflict_count := v_name_conflict_count + 1;
      end if;
    end loop;

    if v_match_count > 1 or (v_match_count = 0 and v_name_conflict_count > 0) then
      v_holds := v_holds + 1;
      v_product_result := v_product_result || jsonb_build_object(
        'action','HOLD_CONFLICT',
        'reason',case when v_match_count > 1 then 'multiple_products_with_stable_id' else 'name_exists_without_matching_stable_id' end
      );
      v_products_result := v_products_result || jsonb_build_array(v_product_result);
      continue;
    end if;

    if v_match_count = 1 then
      if v_provider_product->>'name' <> v_product->>'name'
         or v_provider_product->>'tax_category' <> v_product->>'tax_category' then
        v_holds := v_holds + 1;
        v_product_result := v_product_result || jsonb_build_object('action','HOLD_PRODUCT_DRIFT','provider_product_id',v_provider_product->>'id');
        v_products_result := v_products_result || jsonb_build_array(v_product_result);
        continue;
      end if;
      v_product_id := v_provider_product->>'id';
      v_existing_products := v_existing_products + 1;
      v_product_result := v_product_result || jsonb_build_object('action','EXISTING','provider_product_id',v_product_id);
    elsif not p_apply then
      v_product_result := v_product_result || jsonb_build_object('action','WOULD_CREATE');
      v_price_results := '[]'::jsonb;
      for v_price in select value from jsonb_array_elements(v_product->'prices')
      loop
        v_price_results := v_price_results || jsonb_build_array(jsonb_build_object('key',v_price->>'key','action','WOULD_CREATE'));
      end loop;
      v_product_result := v_product_result || jsonb_build_object('prices',v_price_results);
      v_products_result := v_products_result || jsonb_build_array(v_product_result);
      continue;
    else
      v_payload := jsonb_build_object(
        'name',v_product->>'name',
        'description',v_product->>'description',
        'type','standard',
        'tax_category',v_product->>'tax_category',
        'custom_data',v_product->'custom_data'
      );
      v_resp := chlom_runtime.dail_http_v1((row(
        'POST'::extensions.http_method,
        (v_base||'/products')::varchar,
        array[
          extensions.http_header('Authorization'::varchar,('Bearer '||v_secret)::varchar),
          extensions.http_header('Accept'::varchar,'application/json'::varchar),
          extensions.http_header('Paddle-Version'::varchar,'1'::varchar),
          extensions.http_header('User-Agent'::varchar,'CrownThrive-Paddle-Catalog/1.0'::varchar)
        ]::extensions.http_header[],
        'application/json'::varchar,
        v_payload::text::varchar
      )::extensions.http_request));
      begin v_body := coalesce(v_resp.content,'{}')::jsonb; exception when others then v_body := '{}'::jsonb; end;
      if v_resp.status <> 201 or coalesce(v_body#>>'{data,id}','') !~ '^pro_[a-z0-9]{26}$' then
        raise exception 'paddle_product_create_failed:%:%',v_resp.status,coalesce(v_body#>>'{error,code}','unknown');
      end if;
      v_product_id := v_body#>>'{data,id}';
      v_provider_write := true;
      v_created_products := v_created_products + 1;

      v_resp := chlom_runtime.dail_http_v1((row(
        'GET'::extensions.http_method,
        (v_base||'/products/'||v_product_id)::varchar,
        array[
          extensions.http_header('Authorization'::varchar,('Bearer '||v_secret)::varchar),
          extensions.http_header('Accept'::varchar,'application/json'::varchar),
          extensions.http_header('Paddle-Version'::varchar,'1'::varchar),
          extensions.http_header('User-Agent'::varchar,'CrownThrive-Paddle-Catalog/1.0'::varchar)
        ]::extensions.http_header[],
        null::varchar,
        null::varchar
      )::extensions.http_request));
      begin v_readback := coalesce(v_resp.content,'{}')::jsonb; exception when others then v_readback := '{}'::jsonb; end;
      if v_resp.status <> 200
         or v_readback#>>'{data,id}' <> v_product_id
         or v_readback#>>'{data,custom_data,ct_stable_id}' <> v_stable_id then
        raise exception 'paddle_product_readback_failed:%',v_product_id;
      end if;
      v_product_result := v_product_result || jsonb_build_object('action','CREATED','provider_product_id',v_product_id,'readback_status',v_readback#>>'{data,status}');
    end if;

    v_resp := chlom_runtime.dail_http_v1((row(
      'GET'::extensions.http_method,
      (v_base||'/prices?status=active&per_page=200&product_id='||v_product_id)::varchar,
      array[
        extensions.http_header('Authorization'::varchar,('Bearer '||v_secret)::varchar),
        extensions.http_header('Accept'::varchar,'application/json'::varchar),
        extensions.http_header('Paddle-Version'::varchar,'1'::varchar),
        extensions.http_header('User-Agent'::varchar,'CrownThrive-Paddle-Catalog/1.0'::varchar)
      ]::extensions.http_header[],
      null::varchar,
      null::varchar
    )::extensions.http_request));
    begin v_prices_body := coalesce(v_resp.content,'{}')::jsonb; exception when others then v_prices_body := '{}'::jsonb; end;
    if v_resp.status <> 200 then
      raise exception 'paddle_prices_read_failed:%',v_resp.status;
    end if;
    if coalesce((v_prices_body#>>'{meta,pagination,has_more}')::boolean,false) then
      raise exception 'paddle_prices_pagination_requires_extension:%',v_product_id;
    end if;

    v_price_results := '[]'::jsonb;
    for v_price in select value from jsonb_array_elements(v_product->'prices')
    loop
      v_price_key := v_price->>'key';
      v_match_count := 0;
      v_provider_price := null;

      for v_entity in select value from jsonb_array_elements(coalesce(v_prices_body->'data','[]'::jsonb))
      loop
        if v_entity#>>'{custom_data,ct_stable_id}' = v_stable_id
           and v_entity#>>'{custom_data,ct_price_key}' = v_price_key then
          v_match_count := v_match_count + 1;
          v_provider_price := v_entity;
        end if;
      end loop;

      v_price_result := jsonb_build_object('key',v_price_key);
      if v_match_count > 1 then
        v_holds := v_holds + 1;
        v_price_result := v_price_result || jsonb_build_object('action','HOLD_CONFLICT','reason','multiple_prices_with_stable_key');
        v_price_results := v_price_results || jsonb_build_array(v_price_result);
        continue;
      end if;

      if v_match_count = 1 then
        if v_provider_price#>>'{unit_price,amount}' <> v_price->>'amount_minor'
           or v_provider_price#>>'{unit_price,currency_code}' <> 'USD'
           or coalesce(v_provider_price->'billing_cycle','null'::jsonb) <> coalesce(v_price->'billing_cycle','null'::jsonb) then
          v_holds := v_holds + 1;
          v_price_result := v_price_result || jsonb_build_object('action','HOLD_PRICE_DRIFT','provider_price_id',v_provider_price->>'id');
        else
          v_existing_prices := v_existing_prices + 1;
          v_price_result := v_price_result || jsonb_build_object('action','EXISTING','provider_price_id',v_provider_price->>'id');
        end if;
      elsif not p_apply then
        v_price_result := v_price_result || jsonb_build_object('action','WOULD_CREATE');
      else
        v_payload := jsonb_build_object(
          'product_id',v_product_id,
          'description',v_price->>'description',
          'name',v_price->>'name',
          'type','standard',
          'billing_cycle',v_price->'billing_cycle',
          'trial_period','null'::jsonb,
          'tax_mode','account_setting',
          'unit_price',jsonb_build_object('amount',v_price->>'amount_minor','currency_code','USD'),
          'custom_data',(v_price->'custom_data') || jsonb_build_object(
            'ct_stable_id',v_stable_id,
            'ct_price_key',v_price_key,
            'ct_catalog_wave','ct.paddle.catalog.go-flipbooks.wave-001'
          )
        );
        v_resp := chlom_runtime.dail_http_v1((row(
          'POST'::extensions.http_method,
          (v_base||'/prices')::varchar,
          array[
            extensions.http_header('Authorization'::varchar,('Bearer '||v_secret)::varchar),
            extensions.http_header('Accept'::varchar,'application/json'::varchar),
            extensions.http_header('Paddle-Version'::varchar,'1'::varchar),
            extensions.http_header('User-Agent'::varchar,'CrownThrive-Paddle-Catalog/1.0'::varchar)
          ]::extensions.http_header[],
          'application/json'::varchar,
          v_payload::text::varchar
        )::extensions.http_request));
        begin v_body := coalesce(v_resp.content,'{}')::jsonb; exception when others then v_body := '{}'::jsonb; end;
        if v_resp.status <> 201 or coalesce(v_body#>>'{data,id}','') !~ '^pri_[a-z0-9]{26}$' then
          raise exception 'paddle_price_create_failed:%:%:%',v_price_key,v_resp.status,coalesce(v_body#>>'{error,code}','unknown');
        end if;
        v_price_id := v_body#>>'{data,id}';
        v_provider_write := true;
        v_created_prices := v_created_prices + 1;

        v_resp := chlom_runtime.dail_http_v1((row(
          'GET'::extensions.http_method,
          (v_base||'/prices/'||v_price_id)::varchar,
          array[
            extensions.http_header('Authorization'::varchar,('Bearer '||v_secret)::varchar),
            extensions.http_header('Accept'::varchar,'application/json'::varchar),
            extensions.http_header('Paddle-Version'::varchar,'1'::varchar),
            extensions.http_header('User-Agent'::varchar,'CrownThrive-Paddle-Catalog/1.0'::varchar)
          ]::extensions.http_header[],
          null::varchar,
          null::varchar
        )::extensions.http_request));
        begin v_readback := coalesce(v_resp.content,'{}')::jsonb; exception when others then v_readback := '{}'::jsonb; end;
        if v_resp.status <> 200
           or v_readback#>>'{data,id}' <> v_price_id
           or v_readback#>>'{data,custom_data,ct_stable_id}' <> v_stable_id
           or v_readback#>>'{data,custom_data,ct_price_key}' <> v_price_key
           or v_readback#>>'{data,unit_price,amount}' <> v_price->>'amount_minor'
           or v_readback#>>'{data,unit_price,currency_code}' <> 'USD' then
          raise exception 'paddle_price_readback_failed:%',v_price_id;
        end if;
        v_price_result := v_price_result || jsonb_build_object('action','CREATED','provider_price_id',v_price_id,'readback_status',v_readback#>>'{data,status}');
      end if;

      v_price_results := v_price_results || jsonb_build_array(v_price_result);
    end loop;

    v_product_result := v_product_result || jsonb_build_object('prices',v_price_results);
    v_products_result := v_products_result || jsonb_build_array(v_product_result);
  end loop;

  if not p_apply then
    v_state := case when v_holds=0 then 'DRY_RUN_PASS' else 'HOLD' end;
  elsif v_holds=0 and (v_created_products+v_existing_products)=2 and (v_created_prices+v_existing_prices)=6 then
    v_state := 'PASS';
  else
    v_state := 'HOLD';
  end if;

  v_result := jsonb_build_object(
    'contract','ct.paddle.catalog-sync-receipt.v1',
    'wave_id',v_desired->>'wave_id',
    'state',v_state,
    'apply_requested',p_apply,
    'manifest_digest',v_manifest_digest,
    'provider','Paddle',
    'provider_called',true,
    'provider_write',v_provider_write,
    'credential_exposed',false,
    'credential_forwarded_to_caller',false,
    'secret_value_returned',false,
    'summary',jsonb_build_object(
      'desired_products',2,
      'desired_prices',6,
      'created_products',v_created_products,
      'existing_products',v_existing_products,
      'created_prices',v_created_prices,
      'existing_prices',v_existing_prices,
      'holds',v_holds
    ),
    'products',v_products_result,
    'observed_at',clock_timestamp()
  );

  insert into integration_control.paddle_catalog_sync_receipts_v1(
    wave_id,apply_requested,state,manifest_digest,provider_write,summary,provider_objects
  ) values (
    v_desired->>'wave_id',p_apply,v_state,v_manifest_digest,v_provider_write,v_result->'summary',v_products_result
  ) returning receipt_id into v_receipt_id;

  return v_result || jsonb_build_object('receipt_id',v_receipt_id);
exception when others then
  if sqlstate='42501' then raise; end if;
  v_result := jsonb_build_object(
    'contract','ct.paddle.catalog-sync-receipt.v1',
    'wave_id','ct.paddle.catalog.go-flipbooks.wave-001',
    'state','FAIL_RUNTIME_EXCEPTION',
    'apply_requested',p_apply,
    'manifest_digest',coalesce(v_manifest_digest,''),
    'provider_write',v_provider_write,
    'credential_exposed',false,
    'credential_forwarded_to_caller',false,
    'secret_value_returned',false,
    'error_code',sqlstate,
    'error_sha256',encode(extensions.digest(convert_to(coalesce(sqlerrm,''),'UTF8'),'sha256'),'hex'),
    'error_detail_redacted',left(case when coalesce(v_secret,'')<>'' then replace(sqlerrm,v_secret,'[REDACTED]') else sqlerrm end,240),
    'observed_at',clock_timestamp()
  );
  begin
    insert into integration_control.paddle_catalog_sync_receipts_v1(
      wave_id,apply_requested,state,manifest_digest,provider_write,summary,provider_objects
    ) values (
      'ct.paddle.catalog.go-flipbooks.wave-001',p_apply,'FAIL_RUNTIME_EXCEPTION',coalesce(v_manifest_digest,''),v_provider_write,v_result,'[]'::jsonb
    ) returning receipt_id into v_receipt_id;
    v_result := v_result || jsonb_build_object('receipt_id',v_receipt_id);
  exception when others then null;
  end;
  return v_result;
end;
$function$;

revoke all on function integration_control.paddle_go_flipbooks_wave001_v1(boolean) from public, anon, authenticated;
grant execute on function integration_control.paddle_go_flipbooks_wave001_v1(boolean) to service_role;
