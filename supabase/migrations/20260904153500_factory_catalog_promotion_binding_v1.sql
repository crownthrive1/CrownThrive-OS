create table if not exists integration_control.penta_factory_pressure_catalog_promotions_v1 (
  promotion_id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null unique
    references integration_control.thriveevergreen_publisher_candidates_v2(candidate_id) on delete restrict,
  governed_release_id uuid not null
    references integration_control.governed_releases(release_id) on delete restrict,
  offer_code text not null
    references developer_commerce.catalog_offers(offer_code) on update restrict on delete restrict,
  sku text not null
    references developer_commerce.catalog_products(sku) on update cascade on delete restrict,
  asset_version_id uuid not null
    references developer_commerce.asset_versions(id) on delete restrict,
  route_id text not null
    references integration_control.site_publish_routes(route_id) on delete restrict,
  exact_version_ref text not null,
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  promotion_state text not null default 'candidate_seeded'
    check (promotion_state in ('candidate_seeded','release_ready','published','failed','superseded')),
  provider_readback_state text not null default 'working'
    check (provider_readback_state in ('working','pass','hold','fail','not_applicable')),
  binding_state text not null default 'exact_bound'
    check (binding_state in ('exact_bound','hold','conflict')),
  exact_binding_sha256 text not null check (exact_binding_sha256 ~ '^[0-9a-f]{64}$'),
  source_contract text not null default 'ct.penta.factory-pressure-catalog-promotion-binding.v1',
  provider_write boolean not null default false check (provider_write=false),
  money_movement boolean not null default false check (money_movement=false),
  authority_created boolean not null default false check (authority_created=false),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  unique (governed_release_id,offer_code,asset_version_id,exact_version_ref,content_sha256,route_id)
);

create index if not exists penta_factory_pressure_catalog_promotions_state_idx
  on integration_control.penta_factory_pressure_catalog_promotions_v1(promotion_state,provider_readback_state,updated_at);
create index if not exists penta_factory_pressure_catalog_promotions_offer_idx
  on integration_control.penta_factory_pressure_catalog_promotions_v1(offer_code,exact_version_ref);

create table if not exists integration_control.penta_factory_pressure_catalog_promotion_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  promotion_id uuid not null
    references integration_control.penta_factory_pressure_catalog_promotions_v1(promotion_id) on delete restrict,
  candidate_id uuid not null
    references integration_control.thriveevergreen_publisher_candidates_v2(candidate_id) on delete restrict,
  action text not null check (action in ('bound','refreshed','state_synced')),
  binding_state text not null check (binding_state in ('exact_bound','hold','conflict')),
  promotion_state text not null check (promotion_state in ('candidate_seeded','release_ready','published','failed','superseded')),
  exact_version_ref text not null,
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  evidence jsonb not null,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  provider_write boolean not null default false check (provider_write=false),
  money_movement boolean not null default false check (money_movement=false),
  authority_created boolean not null default false check (authority_created=false),
  created_at timestamptz not null default clock_timestamp(),
  unique (promotion_id,evidence_sha256)
);

create index if not exists penta_factory_pressure_catalog_promotion_receipts_candidate_idx
  on integration_control.penta_factory_pressure_catalog_promotion_receipts_v1(candidate_id,created_at desc);

create or replace function integration_control.reject_penta_factory_catalog_promotion_receipt_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $$
begin
  raise exception 'penta_factory_catalog_promotion_receipts_append_only';
end;
$$;

drop trigger if exists trg_penta_factory_catalog_promotion_receipts_append_only
  on integration_control.penta_factory_pressure_catalog_promotion_receipts_v1;
create trigger trg_penta_factory_catalog_promotion_receipts_append_only
before update or delete on integration_control.penta_factory_pressure_catalog_promotion_receipts_v1
for each row execute function integration_control.reject_penta_factory_catalog_promotion_receipt_mutation_v1();

alter table integration_control.penta_factory_pressure_catalog_promotions_v1 enable row level security;
alter table integration_control.penta_factory_pressure_catalog_promotion_receipts_v1 enable row level security;

create or replace function integration_control.penta_factory_pressure_promote_catalog_v1(p_limit integer default 1)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','developer_commerce','extensions','pg_temp'
as $$
declare
  v_limit integer:=greatest(1,least(coalesce(p_limit,1),500));
  v_now timestamptz:=clock_timestamp();
  v_inserted integer:=0;
  v_updated integer:=0;
  v_unchanged integer:=0;
  v_receipts integer:=0;
  v_active integer:=0;
  v_eligible integer:=0;
  v_bound integer:=0;
  v_unbound integer:=0;
  v_incomplete integer:=0;
  v_seeded integer:=0;
  v_ready integer:=0;
  v_published integer:=0;
  v_failed integer:=0;
  v_promotion_id uuid;
  v_prior_sha text;
  v_prior_state text;
  v_prior_provider text;
  v_exists boolean;
  v_changed boolean;
  v_promotion_state text;
  v_provider_state text;
  v_binding_payload jsonb;
  v_binding_sha text;
  v_receipt_payload jsonb;
  v_receipt_sha text;
  v_holds jsonb:='[]'::jsonb;
  v_state text;
  v_binding_result text;
  r record;
begin
  if p_limit is null or p_limit<1 or p_limit>500 then
    raise exception 'catalog_promotion_limit_out_of_range';
  end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:factory-pressure-catalog-promotion:v1',0)) then
    return jsonb_build_object(
      'state','DEFERRED_CONTENTION','binding_state','DEFERRED_CONTENTION',
      'bound_or_refreshed',0,'provider_write',false,'money_movement',false,
      'authority_created',false,'observed_at',clock_timestamp()
    );
  end if;

  for r in
    select c.candidate_id,c.release_id,c.offer_code,o.sku,c.asset_version_id,c.route_id,
           c.exact_version_ref,c.content_sha256,c.candidate_state,c.priority,
           gr.release_state,gr.certification_state,gr.vote_state,
           integration_control.thriveevergreen_publisher_gate_snapshot_v6(c.candidate_id)->>'decision' as gate_decision,
           p.promotion_id as existing_promotion_id,p.exact_binding_sha256 as existing_binding_sha,
           p.promotion_state as existing_promotion_state,p.provider_readback_state as existing_provider_state
    from integration_control.thriveevergreen_publisher_candidates_v2 c
    join integration_control.governed_releases gr
      on gr.release_id=c.release_id
     and gr.exact_version_ref=c.exact_version_ref
     and gr.content_sha256=c.content_sha256
     and gr.release_state<>'superseded'
    join developer_commerce.catalog_offers o on o.offer_code=c.offer_code
    join developer_commerce.catalog_products cp on cp.sku=o.sku
    join developer_commerce.asset_versions av
      on av.id=c.asset_version_id
     and av.sku=o.sku
     and av.version=c.exact_version_ref
     and av.sha256=c.content_sha256
    join integration_control.site_publish_routes sr
      on sr.route_id=c.route_id and sr.route_state='active'
    join integration_control.thriveevergreen_mesh_product_profiles_v1 mp
      on mp.offer_code=c.offer_code and mp.sku=o.sku and lower(coalesce(mp.desired_state,''))='enabled'
    left join integration_control.penta_factory_pressure_catalog_promotions_v1 p
      on p.candidate_id=c.candidate_id
    where c.candidate_state<>'retired' and c.offer_code is not null
      and (
        p.promotion_id is null
        or p.governed_release_id is distinct from c.release_id
        or p.offer_code is distinct from c.offer_code
        or p.sku is distinct from o.sku
        or p.asset_version_id is distinct from c.asset_version_id
        or p.route_id is distinct from c.route_id
        or p.exact_version_ref is distinct from c.exact_version_ref
        or p.content_sha256 is distinct from c.content_sha256
        or p.promotion_state is distinct from case
             when c.candidate_state='published' then 'published'
             when c.candidate_state='admitted' then 'release_ready'
             else 'candidate_seeded' end
        or p.provider_readback_state is distinct from case
             when c.candidate_state in ('admitted','published') then 'pass'
             else 'working' end
        or p.binding_state<>'exact_bound'
      )
    order by (p.promotion_id is null) desc,c.priority,c.updated_at,c.candidate_id
    limit v_limit
  loop
    v_promotion_state:=case
      when r.candidate_state='published' then 'published'
      when r.candidate_state='admitted' then 'release_ready'
      else 'candidate_seeded' end;
    v_provider_state:=case
      when r.candidate_state in ('admitted','published') then 'pass'
      else 'working' end;

    v_binding_payload:=jsonb_build_object(
      'contract','ct.penta.factory-pressure-catalog-promotion-binding.v1',
      'candidate_id',r.candidate_id,'governed_release_id',r.release_id,
      'offer_code',r.offer_code,'sku',r.sku,'asset_version_id',r.asset_version_id,
      'route_id',r.route_id,'exact_version_ref',r.exact_version_ref,
      'content_sha256',r.content_sha256,'candidate_state',r.candidate_state,
      'promotion_state',v_promotion_state,'provider_readback_state',v_provider_state,
      'binding_state','exact_bound','release_state',r.release_state,
      'certification_state',r.certification_state,'vote_state',r.vote_state,
      'provider_write',false,'money_movement',false,'authority_created',false
    );
    v_binding_sha:=encode(extensions.digest(convert_to(v_binding_payload::text,'UTF8'),'sha256'),'hex');

    select promotion_id,exact_binding_sha256,promotion_state,provider_readback_state
      into v_promotion_id,v_prior_sha,v_prior_state,v_prior_provider
    from integration_control.penta_factory_pressure_catalog_promotions_v1
    where candidate_id=r.candidate_id;
    v_exists:=found;
    v_changed:=not v_exists
      or v_prior_sha is distinct from v_binding_sha
      or v_prior_state is distinct from v_promotion_state
      or v_prior_provider is distinct from v_provider_state;

    if not v_exists then
      insert into integration_control.penta_factory_pressure_catalog_promotions_v1(
        candidate_id,governed_release_id,offer_code,sku,asset_version_id,route_id,
        exact_version_ref,content_sha256,promotion_state,provider_readback_state,
        binding_state,exact_binding_sha256,source_contract,provider_write,money_movement,
        authority_created,metadata,created_at,updated_at
      ) values(
        r.candidate_id,r.release_id,r.offer_code,r.sku,r.asset_version_id,r.route_id,
        r.exact_version_ref,r.content_sha256,v_promotion_state,v_provider_state,
        'exact_bound',v_binding_sha,'ct.penta.factory-pressure-catalog-promotion-binding.v1',
        false,false,false,
        jsonb_build_object(
          'gate_decision',coalesce(r.gate_decision,'WORKING'),
          'exact_release_bound',true,'exact_offer_bound',true,'exact_asset_version_bound',true,
          'exact_route_bound',true,'product_profile_bound',true,
          'publication_authority_created',false,'rights_expansion',false
        ),v_now,v_now
      ) returning promotion_id into v_promotion_id;
      v_inserted:=v_inserted+1;
    elsif v_changed then
      update integration_control.penta_factory_pressure_catalog_promotions_v1
      set governed_release_id=r.release_id,offer_code=r.offer_code,sku=r.sku,
          asset_version_id=r.asset_version_id,route_id=r.route_id,
          exact_version_ref=r.exact_version_ref,content_sha256=r.content_sha256,
          promotion_state=v_promotion_state,provider_readback_state=v_provider_state,
          binding_state='exact_bound',exact_binding_sha256=v_binding_sha,
          source_contract='ct.penta.factory-pressure-catalog-promotion-binding.v1',
          provider_write=false,money_movement=false,authority_created=false,
          metadata=jsonb_build_object(
            'gate_decision',coalesce(r.gate_decision,'WORKING'),
            'exact_release_bound',true,'exact_offer_bound',true,'exact_asset_version_bound',true,
            'exact_route_bound',true,'product_profile_bound',true,
            'publication_authority_created',false,'rights_expansion',false
          ),updated_at=v_now
      where promotion_id=v_promotion_id;
      v_updated:=v_updated+1;
    else
      v_unchanged:=v_unchanged+1;
    end if;

    if v_changed then
      v_receipt_payload:=v_binding_payload||jsonb_build_object(
        'action',case when not v_exists then 'bound'
                      when v_prior_state is distinct from v_promotion_state
                        or v_prior_provider is distinct from v_provider_state then 'state_synced'
                      else 'refreshed' end,
        'promotion_id',v_promotion_id,'observed_at',v_now,
        'historical_receipts_append_only',true
      );
      v_receipt_sha:=encode(extensions.digest(convert_to(v_receipt_payload::text,'UTF8'),'sha256'),'hex');
      insert into integration_control.penta_factory_pressure_catalog_promotion_receipts_v1(
        promotion_id,candidate_id,action,binding_state,promotion_state,exact_version_ref,
        content_sha256,evidence,evidence_sha256,provider_write,money_movement,authority_created,created_at
      ) values(
        v_promotion_id,r.candidate_id,
        case when not v_exists then 'bound'
             when v_prior_state is distinct from v_promotion_state
               or v_prior_provider is distinct from v_provider_state then 'state_synced'
             else 'refreshed' end,
        'exact_bound',v_promotion_state,r.exact_version_ref,r.content_sha256,
        v_receipt_payload,v_receipt_sha,false,false,false,v_now
      ) on conflict(promotion_id,evidence_sha256) do nothing;
      if found then v_receipts:=v_receipts+1; end if;
    end if;
  end loop;

  select count(*)::integer into v_active
  from integration_control.thriveevergreen_publisher_candidates_v2 c
  where c.candidate_state<>'retired' and c.offer_code is not null;

  select count(*)::integer into v_eligible
  from integration_control.thriveevergreen_publisher_candidates_v2 c
  join integration_control.governed_releases gr
    on gr.release_id=c.release_id and gr.exact_version_ref=c.exact_version_ref
   and gr.content_sha256=c.content_sha256 and gr.release_state<>'superseded'
  join developer_commerce.catalog_offers o on o.offer_code=c.offer_code
  join developer_commerce.catalog_products cp on cp.sku=o.sku
  join developer_commerce.asset_versions av
    on av.id=c.asset_version_id and av.sku=o.sku
   and av.version=c.exact_version_ref and av.sha256=c.content_sha256
  join integration_control.site_publish_routes sr on sr.route_id=c.route_id and sr.route_state='active'
  join integration_control.thriveevergreen_mesh_product_profiles_v1 mp
    on mp.offer_code=c.offer_code and mp.sku=o.sku and lower(coalesce(mp.desired_state,''))='enabled'
  where c.candidate_state<>'retired' and c.offer_code is not null;

  select count(*)::integer into v_bound
  from integration_control.penta_factory_pressure_catalog_promotions_v1 p
  join integration_control.thriveevergreen_publisher_candidates_v2 c on c.candidate_id=p.candidate_id
  where c.candidate_state<>'retired' and c.offer_code is not null and p.binding_state='exact_bound';

  select count(*)::integer into v_unbound
  from integration_control.thriveevergreen_publisher_candidates_v2 c
  join integration_control.governed_releases gr
    on gr.release_id=c.release_id and gr.exact_version_ref=c.exact_version_ref
   and gr.content_sha256=c.content_sha256 and gr.release_state<>'superseded'
  join developer_commerce.catalog_offers o on o.offer_code=c.offer_code
  join developer_commerce.asset_versions av
    on av.id=c.asset_version_id and av.sku=o.sku
   and av.version=c.exact_version_ref and av.sha256=c.content_sha256
  join integration_control.site_publish_routes sr on sr.route_id=c.route_id and sr.route_state='active'
  join integration_control.thriveevergreen_mesh_product_profiles_v1 mp
    on mp.offer_code=c.offer_code and mp.sku=o.sku and lower(coalesce(mp.desired_state,''))='enabled'
  left join integration_control.penta_factory_pressure_catalog_promotions_v1 p on p.candidate_id=c.candidate_id
  where c.candidate_state<>'retired' and c.offer_code is not null
    and (p.promotion_id is null or p.binding_state<>'exact_bound');

  v_incomplete:=greatest(v_active-v_eligible,0);

  select count(*) filter(where p.promotion_state='candidate_seeded')::integer,
         count(*) filter(where p.promotion_state='release_ready')::integer,
         count(*) filter(where p.promotion_state='published')::integer,
         count(*) filter(where p.promotion_state='failed')::integer
    into v_seeded,v_ready,v_published,v_failed
  from integration_control.penta_factory_pressure_catalog_promotions_v1 p
  join integration_control.thriveevergreen_publisher_candidates_v2 c on c.candidate_id=p.candidate_id
  where c.candidate_state<>'retired' and c.offer_code is not null;

  if v_incomplete>0 then
    v_holds:=v_holds||jsonb_build_array('HOLD_FACTORY_CATALOG_EXACT_BINDING_INPUT_MISSING');
  end if;
  if v_unbound>0 then
    v_holds:=v_holds||jsonb_build_array('HOLD_FACTORY_CATALOG_BINDING_BACKLOG');
  end if;
  if v_failed>0 then
    v_holds:=v_holds||jsonb_build_array('HOLD_FACTORY_CATALOG_PROMOTION_FAILED');
  end if;
  if v_seeded>0 then
    v_holds:=v_holds||jsonb_build_array('HOLD_FACTORY_CANDIDATE_EVIDENCE_WORKING');
  end if;

  v_binding_result:=case when v_incomplete=0 and v_unbound=0 then 'PASS' else 'HOLD' end;
  v_state:=case when v_binding_result='PASS' and v_failed=0 and v_seeded=0 then 'PASS' else 'PASS_WITH_OPEN_ITEMS' end;

  return jsonb_build_object(
    'state',v_state,'binding_state',v_binding_result,
    'contract','ct.penta.factory-pressure-catalog-promotion-binding.v1',
    'promotion_relation_present',true,'promotion_function_present',true,
    'active_candidates',v_active,'exact_eligible_candidates',v_eligible,
    'exact_bound_candidates',v_bound,'unbound_candidates',v_unbound,
    'incomplete_input_candidates',v_incomplete,
    'candidate_seeded',v_seeded,'release_ready',v_ready,'published',v_published,'failed',v_failed,
    'inserted',v_inserted,'updated',v_updated,'unchanged',v_unchanged,
    'append_only_receipts_created',v_receipts,'hold_codes',v_holds,
    'provider_write',false,'money_movement',false,'rights_expansion',false,
    'publication_authority_created',false,'authority_created',false,
    'observed_at',clock_timestamp()
  );
end;
$$;

create or replace function integration_control.penta_factory_pressure_catalog_promotion_counts_v1()
returns jsonb
language sql
stable
security definer
set search_path to 'pg_catalog','integration_control','developer_commerce'
as $$
  with active as (
    select c.candidate_id
    from integration_control.thriveevergreen_publisher_candidates_v2 c
    where c.candidate_state<>'retired' and c.offer_code is not null
  ), counts as (
    select
      count(*)::bigint as total,
      count(*) filter(where p.promotion_state in ('release_ready','published'))::bigint as release_ready,
      count(*) filter(where p.promotion_state='published')::bigint as published,
      count(*) filter(where p.promotion_state='candidate_seeded')::bigint as candidate_seeded,
      count(*) filter(where p.promotion_state='failed')::bigint as failed,
      count(*) filter(where p.binding_state='exact_bound')::bigint as exact_bound
    from integration_control.penta_factory_pressure_catalog_promotions_v1 p
    join active a on a.candidate_id=p.candidate_id
  )
  select jsonb_build_object(
    'state',case when (select count(*) from active)=counts.exact_bound then 'PASS' else 'PASS_WITH_OPEN_ITEMS' end,
    'relation_present',true,
    'total',counts.total,
    'release_ready',counts.release_ready,
    'published',counts.published,
    'candidate_seeded',counts.candidate_seeded,
    'failed',counts.failed,
    'exact_bound',counts.exact_bound,
    'active_candidates',(select count(*) from active),
    'unbound',greatest((select count(*) from active)-counts.exact_bound,0),
    'provider_write',false,
    'authority_created',false,
    'observed_at',clock_timestamp()
  )
  from counts;
$$;

revoke all on integration_control.penta_factory_pressure_catalog_promotions_v1 from public,anon,authenticated;
revoke all on integration_control.penta_factory_pressure_catalog_promotion_receipts_v1 from public,anon,authenticated;
grant select on integration_control.penta_factory_pressure_catalog_promotions_v1 to service_role;
grant select on integration_control.penta_factory_pressure_catalog_promotion_receipts_v1 to service_role;
revoke all on function integration_control.penta_factory_pressure_promote_catalog_v1(integer) from public,anon,authenticated;
revoke all on function integration_control.penta_factory_pressure_catalog_promotion_counts_v1() from public,anon,authenticated;
grant execute on function integration_control.penta_factory_pressure_promote_catalog_v1(integer) to service_role;
grant execute on function integration_control.penta_factory_pressure_catalog_promotion_counts_v1() to service_role;

do $$
declare
  v_result jsonb;
begin
  v_result:=integration_control.penta_factory_pressure_promote_catalog_v1(500);
  if coalesce(v_result->>'binding_state','HOLD')<>'PASS' then
    raise exception 'factory_catalog_promotion_binding_backfill_failed:%',v_result;
  end if;
end;
$$;