-- PentaContext v1 production context/memory plane.
-- Applied to CrownThrive production as migration 20260826230616.

create table public.penta_context_sources_v1 (
  source_id uuid primary key default gen_random_uuid(),
  scope_key text not null check (length(scope_key) between 2 and 128),
  source_type text not null check (source_type = any (array['github','drive','database','api','web','document','message','email','calendar','event','system','manual','other']::text[])),
  source_ref text not null check (length(btrim(source_ref)) > 0),
  source_uri text,
  trust_tier text not null default 'internal' check (trust_tier = any (array['authoritative','trusted','internal','untrusted']::text[])),
  classification text not null default 'internal' check (classification = any (array['public','internal','confidential','restricted']::text[])),
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (scope_key, source_type, source_ref)
);

create table public.penta_context_records_v1 (
  context_id uuid primary key default gen_random_uuid(),
  scope_key text not null check (length(scope_key) between 2 and 128),
  tenant_ref text not null default 'crownthrive',
  system_ref text,
  brand_ref text,
  corridor_ref text,
  source_id uuid not null references public.penta_context_sources_v1(source_id) on delete restrict,
  title text,
  content text not null check (length(btrim(content)) > 0 and length(content) <= 500000),
  summary text,
  tags text[] not null default '{}'::text[],
  facts jsonb not null default '{}'::jsonb,
  classification text not null default 'internal' check (classification = any (array['public','internal','confidential','restricted']::text[])),
  importance numeric(5,4) not null default 0.5000 check (importance between 0 and 1),
  confidence numeric(5,4) not null default 0.7000 check (confidence between 0 and 1),
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  fingerprint_sha256 text not null check (fingerprint_sha256 ~ '^[0-9a-f]{64}$'),
  content_redacted boolean not null default false,
  provenance jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now(),
  effective_from timestamptz,
  expires_at timestamptz,
  supersedes_context_id uuid references public.penta_context_records_v1(context_id) on delete restrict,
  tombstoned_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (scope_key, fingerprint_sha256),
  check (expires_at is null or expires_at > created_at)
);

create table public.penta_context_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  operation text not null check (operation = any (array['ingest','query','maintenance','health','tombstone']::text[])),
  scope_key text not null,
  context_id uuid references public.penta_context_records_v1(context_id) on delete restrict,
  source_id uuid references public.penta_context_sources_v1(source_id) on delete restrict,
  actor_ref text not null default 'penta.context',
  idempotency_key text,
  input_sha256 text check (input_sha256 is null or input_sha256 ~ '^[0-9a-f]{64}$'),
  output_sha256 text check (output_sha256 is null or output_sha256 ~ '^[0-9a-f]{64}$'),
  passed boolean not null default true,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (operation, idempotency_key)
);

create index penta_context_records_scope_observed_idx on public.penta_context_records_v1(scope_key, observed_at desc) where tombstoned_at is null;
create index penta_context_records_expiry_idx on public.penta_context_records_v1(expires_at) where expires_at is not null and tombstoned_at is null;
create index penta_context_records_tags_gin_idx on public.penta_context_records_v1 using gin(tags);
create index penta_context_records_fts_gin_idx on public.penta_context_records_v1 using gin(to_tsvector('simple', coalesce(title,'') || ' ' || content || ' ' || coalesce(summary,'')));
create index penta_context_sources_scope_active_idx on public.penta_context_sources_v1(scope_key, active, last_seen_at desc);
create index penta_context_receipts_scope_time_idx on public.penta_context_receipts_v1(scope_key, created_at desc);

create or replace function public.penta_context_touch_updated_at_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger penta_context_sources_touch_v1 before update on public.penta_context_sources_v1 for each row execute function public.penta_context_touch_updated_at_v1();
create trigger penta_context_records_touch_v1 before update on public.penta_context_records_v1 for each row execute function public.penta_context_touch_updated_at_v1();

create or replace function public.penta_context_receipt_immutable_guard_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  raise exception 'penta_context_receipts_v1 is append-only';
end;
$$;

create trigger penta_context_receipts_immutable_v1 before update or delete on public.penta_context_receipts_v1 for each row execute function public.penta_context_receipt_immutable_guard_v1();

create or replace function public.penta_context_classification_rank_v1(p_classification text)
returns integer
language sql
immutable
strict
set search_path = pg_catalog
as $$
  select case lower($1)
    when 'public' then 0
    when 'internal' then 1
    when 'confidential' then 2
    when 'restricted' then 3
    else 99
  end;
$$;

create or replace function public.penta_context_redact_v1(p_input text)
returns text
language plpgsql
immutable
strict
set search_path = pg_catalog
as $$
declare
  v text := p_input;
begin
  v := regexp_replace(v, '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[redacted-email]', 'gi');
  v := regexp_replace(v, '[0-9]{3}-[0-9]{2}-[0-9]{4}', '[redacted-ssn]', 'g');
  v := regexp_replace(v, '(?i)(bearer[[:space:]]+)[A-Za-z0-9._~+/-]{12,}', '\1[redacted-secret]', 'g');
  v := regexp_replace(v, '(?i)(sk-[A-Za-z0-9_-]{10,}|sb_secret_[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})', '[redacted-secret]', 'g');
  v := regexp_replace(v, '(?i)(api[_ -]?key|secret|token|password|private[_ -]?key)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._~+/-]{12,}', '[redacted-secret]', 'g');
  return v;
end;
$$;

create or replace function public.penta_context_sanitize_metadata_v1(p_input jsonb)
returns jsonb
language plpgsql
immutable
set search_path = pg_catalog, public
as $$
declare
  v_out jsonb;
  v_key text;
  v_value jsonb;
begin
  if p_input is null then return '{}'::jsonb; end if;
  if jsonb_typeof(p_input) = 'object' then
    v_out := '{}'::jsonb;
    for v_key, v_value in select key, value from jsonb_each(p_input)
    loop
      if lower(v_key) ~ '(secret|token|password|api[_-]?key|authorization|credential|private[_-]?key)' then
        v_out := v_out || jsonb_build_object(v_key, '[redacted]');
      else
        v_out := v_out || jsonb_build_object(v_key, public.penta_context_sanitize_metadata_v1(v_value));
      end if;
    end loop;
    return v_out;
  elsif jsonb_typeof(p_input) = 'array' then
    select coalesce(jsonb_agg(public.penta_context_sanitize_metadata_v1(value)), '[]'::jsonb)
      into v_out from jsonb_array_elements(p_input);
    return v_out;
  elsif jsonb_typeof(p_input) = 'string' then
    return to_jsonb(public.penta_context_redact_v1(p_input #>> '{}'));
  end if;
  return p_input;
end;
$$;

create or replace function public.penta_context_ingest_v1(
  p_scope_key text,
  p_source_type text,
  p_source_ref text,
  p_content text,
  p_title text default null,
  p_summary text default null,
  p_tags text[] default '{}'::text[],
  p_metadata jsonb default '{}'::jsonb,
  p_classification text default 'internal',
  p_importance numeric default 0.5,
  p_confidence numeric default 0.7,
  p_observed_at timestamptz default now(),
  p_expires_at timestamptz default null,
  p_actor_ref text default 'penta.context'
)
returns jsonb
language plpgsql
set search_path = pg_catalog, public, extensions
as $$
declare
  v_scope text := lower(btrim(p_scope_key));
  v_source_type text := lower(btrim(p_source_type));
  v_classification text := lower(btrim(p_classification));
  v_content text;
  v_title text;
  v_summary text;
  v_metadata jsonb;
  v_tags text[] := '{}'::text[];
  v_source_id uuid;
  v_context_id uuid;
  v_source_sha text;
  v_fingerprint text;
  v_rows integer := 0;
  v_inserted boolean := false;
  v_trust text;
begin
  if v_scope = '' or length(v_scope) > 128 then raise exception 'invalid scope_key'; end if;
  if v_source_type <> all(array['github','drive','database','api','web','document','message','email','calendar','event','system','manual','other']::text[]) then raise exception 'invalid source_type'; end if;
  if v_classification <> all(array['public','internal','confidential','restricted']::text[]) then raise exception 'invalid classification'; end if;
  if p_content is null or length(btrim(p_content)) = 0 or length(p_content) > 500000 then raise exception 'invalid content length'; end if;
  if p_importance < 0 or p_importance > 1 or p_confidence < 0 or p_confidence > 1 then raise exception 'importance/confidence out of range'; end if;

  v_content := public.penta_context_redact_v1(p_content);
  v_title := case when p_title is null then null else public.penta_context_redact_v1(p_title) end;
  v_summary := case when p_summary is null then null else public.penta_context_redact_v1(p_summary) end;
  v_metadata := public.penta_context_sanitize_metadata_v1(coalesce(p_metadata, '{}'::jsonb));
  v_trust := case lower(coalesce(v_metadata->>'trust_tier','internal')) when 'authoritative' then 'authoritative' when 'trusted' then 'trusted' when 'untrusted' then 'untrusted' else 'internal' end;

  select coalesce(array_agg(distinct lower(btrim(x))) filter (where btrim(x) <> ''), '{}'::text[])
    into v_tags from unnest(coalesce(p_tags, '{}'::text[])) as x;

  v_source_sha := encode(extensions.digest(p_content, 'sha256'), 'hex');
  v_fingerprint := encode(extensions.digest(concat_ws(E'\n', v_scope, v_source_type, p_source_ref, coalesce(v_title,''), v_content), 'sha256'), 'hex');

  insert into public.penta_context_sources_v1(scope_key, source_type, source_ref, source_uri, trust_tier, classification, metadata, active, last_seen_at)
  values (v_scope, v_source_type, btrim(p_source_ref), nullif(v_metadata->>'source_uri',''), v_trust, v_classification, v_metadata, true, coalesce(p_observed_at, now()))
  on conflict (scope_key, source_type, source_ref) do update
    set source_uri = coalesce(excluded.source_uri, penta_context_sources_v1.source_uri),
        trust_tier = excluded.trust_tier,
        classification = excluded.classification,
        metadata = penta_context_sources_v1.metadata || excluded.metadata,
        active = true,
        last_seen_at = greatest(coalesce(penta_context_sources_v1.last_seen_at, '-infinity'::timestamptz), excluded.last_seen_at)
  returning source_id into v_source_id;

  insert into public.penta_context_records_v1(
    scope_key, tenant_ref, system_ref, brand_ref, corridor_ref, source_id, title, content, summary, tags, facts,
    classification, importance, confidence, source_sha256, fingerprint_sha256, content_redacted, provenance,
    observed_at, effective_from, expires_at
  ) values (
    v_scope,
    coalesce(nullif(v_metadata->>'tenant_ref',''),'crownthrive'),
    nullif(v_metadata->>'system_ref',''),
    nullif(v_metadata->>'brand_ref',''),
    nullif(v_metadata->>'corridor_ref',''),
    v_source_id, v_title, v_content, v_summary, v_tags,
    coalesce(v_metadata->'facts','{}'::jsonb), v_classification, p_importance, p_confidence,
    v_source_sha, v_fingerprint,
    v_content is distinct from p_content or v_title is distinct from p_title or v_summary is distinct from p_summary,
    jsonb_build_object('source_type',v_source_type,'source_ref',btrim(p_source_ref),'source_uri',v_metadata->>'source_uri','trust_tier',v_trust),
    coalesce(p_observed_at,now()), p_observed_at, p_expires_at
  )
  on conflict (scope_key, fingerprint_sha256) do nothing
  returning context_id into v_context_id;
  get diagnostics v_rows = row_count;
  v_inserted := v_rows > 0;

  if v_context_id is null then
    select context_id into v_context_id from public.penta_context_records_v1 where scope_key=v_scope and fingerprint_sha256=v_fingerprint;
  end if;

  insert into public.penta_context_receipts_v1(operation, scope_key, context_id, source_id, actor_ref, idempotency_key, input_sha256, output_sha256, evidence)
  values ('ingest', v_scope, v_context_id, v_source_id, coalesce(nullif(p_actor_ref,''),'penta.context'), 'ingest:'||v_fingerprint, v_source_sha, v_fingerprint,
          jsonb_build_object('inserted',v_inserted,'classification',v_classification,'content_redacted',v_content is distinct from p_content,'authority_created',false))
  on conflict (operation, idempotency_key) do nothing;

  return jsonb_build_object('context_id',v_context_id,'source_id',v_source_id,'scope_key',v_scope,'fingerprint_sha256',v_fingerprint,'inserted',v_inserted,'content_redacted',v_content is distinct from p_content,'authority_created',false);
end;
$$;

create or replace function public.penta_context_query_v1(
  p_scope_key text,
  p_query text default '',
  p_limit integer default 8,
  p_max_chars integer default 12000,
  p_tags text[] default null,
  p_classification_ceiling text default 'internal',
  p_actor_ref text default 'penta.context'
)
returns jsonb
language plpgsql
set search_path = pg_catalog, public, extensions
as $$
declare
  v_scope text := lower(btrim(p_scope_key));
  v_query text := btrim(coalesce(p_query,''));
  v_limit integer := greatest(1, least(coalesce(p_limit,8), 50));
  v_budget integer := greatest(512, least(coalesce(p_max_chars,12000), 100000));
  v_ceiling text := lower(btrim(coalesce(p_classification_ceiling,'internal')));
  v_items jsonb := '[]'::jsonb;
  v_used integer := 0;
  v_take integer;
  v_count integer := 0;
  v_output_sha text;
  r record;
begin
  if v_scope = '' or length(v_scope) > 128 then raise exception 'invalid scope_key'; end if;
  if public.penta_context_classification_rank_v1(v_ceiling) = 99 then raise exception 'invalid classification ceiling'; end if;

  for r in
    with candidates as (
      select c.context_id, c.title, c.content, c.summary, c.tags, c.classification, c.importance, c.confidence,
             c.observed_at, c.expires_at, c.fingerprint_sha256, c.provenance,
             s.source_type, s.source_ref, s.source_uri, s.trust_tier,
             case when v_query = '' then 0::real else ts_rank_cd(to_tsvector('simple',coalesce(c.title,'')||' '||c.content||' '||coalesce(c.summary,'')), websearch_to_tsquery('simple',v_query)) end as text_score,
             case when p_tags is null or cardinality(p_tags)=0 then 0::numeric when c.tags && p_tags then 1::numeric else 0::numeric end as tag_score,
             greatest(0::numeric, 1::numeric - least(1::numeric, extract(epoch from (now()-c.observed_at))::numeric / 31536000::numeric)) as recency_score
      from public.penta_context_records_v1 c
      join public.penta_context_sources_v1 s on s.source_id=c.source_id and s.active=true
      where c.scope_key=v_scope
        and c.tombstoned_at is null
        and (c.expires_at is null or c.expires_at > now())
        and public.penta_context_classification_rank_v1(c.classification) <= public.penta_context_classification_rank_v1(v_ceiling)
        and (v_query='' or to_tsvector('simple',coalesce(c.title,'')||' '||c.content||' '||coalesce(c.summary,'')) @@ websearch_to_tsquery('simple',v_query))
        and (p_tags is null or cardinality(p_tags)=0 or c.tags && p_tags)
    )
    select *, (text_score::numeric*0.55 + tag_score*0.10 + importance*0.15 + confidence*0.10 + recency_score*0.10) as score
    from candidates order by score desc, observed_at desc, context_id limit v_limit
  loop
    exit when v_used >= v_budget;
    v_take := least(length(r.content), v_budget-v_used);
    if v_take <= 0 then exit; end if;
    v_items := v_items || jsonb_build_array(jsonb_build_object(
      'context_id',r.context_id,'title',r.title,'content',left(r.content,v_take),'truncated',v_take<length(r.content),
      'summary',r.summary,'tags',r.tags,'classification',r.classification,'importance',r.importance,'confidence',r.confidence,
      'observed_at',r.observed_at,'expires_at',r.expires_at,'fingerprint_sha256',r.fingerprint_sha256,
      'source',jsonb_build_object('type',r.source_type,'ref',r.source_ref,'uri',r.source_uri,'trust_tier',r.trust_tier),
      'provenance',r.provenance,'score',round(r.score,6)
    ));
    v_used := v_used + v_take;
    v_count := v_count + 1;
  end loop;

  v_output_sha := encode(extensions.digest(v_items::text,'sha256'),'hex');
  insert into public.penta_context_receipts_v1(operation,scope_key,actor_ref,input_sha256,output_sha256,evidence)
  values ('query',v_scope,coalesce(nullif(p_actor_ref,''),'penta.context'),
          encode(extensions.digest(concat_ws('|',v_scope,v_query,coalesce(array_to_string(p_tags,','),''),v_ceiling),'sha256'),'hex'),v_output_sha,
          jsonb_build_object('record_count',v_count,'used_chars',v_used,'max_chars',v_budget,'classification_ceiling',v_ceiling,'authority_created',false));

  return jsonb_build_object('system_key','penta.context','scope_key',v_scope,'query',v_query,'record_count',v_count,'used_chars',v_used,'max_chars',v_budget,'classification_ceiling',v_ceiling,'records',v_items,'output_sha256',v_output_sha,'authority_created',false);
end;
$$;

create or replace function public.penta_context_health_v1()
returns jsonb
language sql
stable
set search_path = pg_catalog, public
as $$
  select jsonb_build_object(
    'system_key','penta.context',
    'state',case when count(*) filter (where tombstoned_at is null and (expires_at is null or expires_at>now())) > 0 then 'healthy' else 'ready_empty' end,
    'active_records',count(*) filter (where tombstoned_at is null and (expires_at is null or expires_at>now())),
    'expired_pending_tombstone',count(*) filter (where tombstoned_at is null and expires_at<=now()),
    'restricted_records',count(*) filter (where classification='restricted' and tombstoned_at is null),
    'latest_observed_at',max(observed_at) filter (where tombstoned_at is null),
    'checked_at',now(),'authority_created',false
  ) from public.penta_context_records_v1;
$$;

create or replace function public.penta_context_maintenance_v1()
returns jsonb
language plpgsql
set search_path = pg_catalog, public, extensions
as $$
declare
  v_tombstoned integer := 0;
  v_health jsonb;
  v_sha text;
begin
  update public.penta_context_records_v1 set tombstoned_at=now()
   where tombstoned_at is null and expires_at is not null and expires_at<=now();
  get diagnostics v_tombstoned = row_count;
  v_health := public.penta_context_health_v1();
  v_sha := encode(extensions.digest(v_health::text,'sha256'),'hex');
  insert into public.penta_context_receipts_v1(operation,scope_key,actor_ref,output_sha256,evidence)
  values ('maintenance','penta.context','penta.mation',v_sha,jsonb_build_object('tombstoned_expired',v_tombstoned,'health',v_health,'authority_created',false));
  update public.penta_system_registry
    set last_verified_at=now(), metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('last_context_maintenance_at',now(),'last_context_health',v_health,'automated',true), updated_at=now()
    where system_key='penta.context';
  return jsonb_build_object('tombstoned_expired',v_tombstoned,'health',v_health,'evidence_sha256',v_sha,'authority_created',false);
end;
$$;

create or replace view public.penta_context_status_v1 with (security_invoker=true) as
select 'penta.context'::text as system_key,
       count(*) filter (where c.tombstoned_at is null and (c.expires_at is null or c.expires_at>now())) as active_records,
       count(distinct c.scope_key) filter (where c.tombstoned_at is null and (c.expires_at is null or c.expires_at>now())) as active_scopes,
       count(*) filter (where c.tombstoned_at is null and c.expires_at<=now()) as expired_pending_tombstone,
       max(c.observed_at) filter (where c.tombstoned_at is null) as latest_observed_at,
       now() as observed_at
from public.penta_context_records_v1 c;

alter table public.penta_context_sources_v1 enable row level security;
alter table public.penta_context_records_v1 enable row level security;
alter table public.penta_context_receipts_v1 enable row level security;

revoke all on public.penta_context_sources_v1 from public, anon, authenticated;
revoke all on public.penta_context_records_v1 from public, anon, authenticated;
revoke all on public.penta_context_receipts_v1 from public, anon, authenticated;
revoke all on public.penta_context_status_v1 from public, anon, authenticated;
grant select,insert,update on public.penta_context_sources_v1 to service_role;
grant select,insert,update on public.penta_context_records_v1 to service_role;
grant select,insert on public.penta_context_receipts_v1 to service_role;
grant select on public.penta_context_status_v1 to service_role;

revoke execute on function public.penta_context_touch_updated_at_v1() from public, anon, authenticated;
revoke execute on function public.penta_context_receipt_immutable_guard_v1() from public, anon, authenticated;
revoke execute on function public.penta_context_classification_rank_v1(text) from public, anon, authenticated;
revoke execute on function public.penta_context_redact_v1(text) from public, anon, authenticated;
revoke execute on function public.penta_context_sanitize_metadata_v1(jsonb) from public, anon, authenticated;
revoke execute on function public.penta_context_ingest_v1(text,text,text,text,text,text,text[],jsonb,text,numeric,numeric,timestamptz,timestamptz,text) from public, anon, authenticated;
revoke execute on function public.penta_context_query_v1(text,text,integer,integer,text[],text,text) from public, anon, authenticated;
revoke execute on function public.penta_context_health_v1() from public, anon, authenticated;
revoke execute on function public.penta_context_maintenance_v1() from public, anon, authenticated;
grant execute on function public.penta_context_classification_rank_v1(text) to service_role;
grant execute on function public.penta_context_redact_v1(text) to service_role;
grant execute on function public.penta_context_sanitize_metadata_v1(jsonb) to service_role;
grant execute on function public.penta_context_ingest_v1(text,text,text,text,text,text,text[],jsonb,text,numeric,numeric,timestamptz,timestamptz,text) to service_role;
grant execute on function public.penta_context_query_v1(text,text,integer,integer,text[],text,text) to service_role;
grant execute on function public.penta_context_health_v1() to service_role;
grant execute on function public.penta_context_maintenance_v1() to service_role;

insert into public.penta_system_registry(system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,public_exposure,docs_ref,runtime_ref,metadata,last_verified_at)
values (
  'penta.context','PentaContext','context_memory_plane',
  'Automated scoped context ingestion, normalization, redaction, provenance, retrieval, retention and context-pack assembly across the Penta/CrownThrive runtime.',
  'Context is evidence and operational memory, never authority. PentaContext may ingest, normalize, rank, retrieve, tombstone expired records and emit receipts through D2; it may not manufacture credentials, rights, governance approval, legal authority, provider-write authority, money movement or D3 effects.',
  'D2','implemented','1.0.0',false,'PENTACONTEXT.md','function:public.penta_context_query_v1',
  jsonb_build_object('mark','TM','phase',3,'automated',true,'exact_scope_isolation',true,'provenance_required',true,'secret_redaction',true,'classification_levels',jsonb_build_array('public','internal','confidential','restricted'),'retrieval','postgres-full-text+tags+importance+confidence+recency','vector_dependency',false,'maintenance_schedule','*/15 * * * *','authority_manufacture',false,'production_canary_pending',true),
  now()
)
on conflict (system_key) do update set
  canonical_name=excluded.canonical_name,category=excluded.category,purpose=excluded.purpose,authority_boundary=excluded.authority_boundary,
  risk_ceiling=excluded.risk_ceiling,maturity=excluded.maturity,version=excluded.version,public_exposure=excluded.public_exposure,
  docs_ref=excluded.docs_ref,runtime_ref=excluded.runtime_ref,metadata=public.penta_system_registry.metadata||excluded.metadata,last_verified_at=now(),updated_at=now();

with d as (
  select jsonb_build_object('system_key','penta.context','action','maintenance','schedule','*/15 * * * *','function','public.penta_context_maintenance_v1','idempotent_expiry_tombstone',true,'authority_created',false) as definition
)
insert into public.penta_mation_workflows(workflow_id,version,status,trigger_type,risk_class,authority_ref,owner_ref,definition,definition_sha256,schema_version)
select 'penta.context.maintenance',1,'active','schedule','D1','penta.context:D1-maintenance','penta.context',definition,encode(extensions.digest(definition::text,'sha256'),'hex'),'1.0.0' from d
on conflict (workflow_id,version) do update set status='active',definition=excluded.definition,definition_sha256=excluded.definition_sha256,updated_at=now();

do $$
begin
  perform cron.unschedule('penta-context-maintenance-v1');
exception when others then null;
end $$;
select cron.schedule('penta-context-maintenance-v1','*/15 * * * *','select public.penta_context_maintenance_v1();');

comment on table public.penta_context_records_v1 is 'PentaContext v1 scoped redacted context records. Context is evidence/memory and never grants authority.';
comment on table public.penta_context_receipts_v1 is 'Append-only PentaContext ingest/query/maintenance evidence receipts.';
comment on function public.penta_context_query_v1(text,text,integer,integer,text[],text,text) is 'Builds a scope-isolated, classification-bounded context pack under a character budget; never grants authority.';
