-- CHLOM C3 Rights Registry v1
--
-- Generalized, evidence-bound rights claims for ownership, administration, and representation.
-- This registry records claims and independent dispositions. It does NOT create a license,
-- entitlement, ownership determination, legal conclusion, provider write, money movement,
-- vote/quorum effect, D3 authority, or any other rights grant.
--
-- C3 invariants:
--   * claims and decisions are append-only;
--   * evidence references + evidence digests are required;
--   * originators cannot verify their own claims;
--   * contradictory overlapping claims fail closed as HOLD_CONFLICT;
--   * rights queries never translate a claim into a license/grant;
--   * only service_role may execute mutation/query RPCs; tables are not directly writable.

create table if not exists chlom_runtime.rights_claims_v1 (
  claim_id uuid primary key default extensions.gen_random_uuid(),
  tenant_key text not null,
  rights_object_key text not null,
  subject_ref text not null,
  right_type text not null,
  claim_role text not null,
  claimant_ref text not null,
  territories text[] not null default '{}'::text[],
  media_scopes text[] not null default '{}'::text[],
  use_scopes text[] not null default '{}'::text[],
  restrictions jsonb not null default '{}'::jsonb,
  evidence_refs jsonb not null,
  evidence_sha256 text not null,
  claim_sha256 text not null unique,
  asserted_by text not null,
  legal_effect text not null default 'EVIDENCE_CLAIM_NOT_RIGHTS_GRANT',
  dail_event_id uuid not null,
  dail_event_hash text not null,
  created_at timestamptz not null default now(),
  constraint rights_claims_v1_tenant_key_check check (tenant_key ~ '^[A-Za-z0-9._:-]{1,200}$'),
  constraint rights_claims_v1_subject_ref_check check (length(btrim(subject_ref)) between 1 and 1000),
  constraint rights_claims_v1_right_type_check check (right_type ~ '^[A-Za-z0-9._:-]{1,200}$'),
  constraint rights_claims_v1_claim_role_check check (claim_role in ('ownership','administration','representation')),
  constraint rights_claims_v1_claimant_ref_check check (length(btrim(claimant_ref)) between 1 and 1000),
  constraint rights_claims_v1_restrictions_object_check check (jsonb_typeof(restrictions)='object'),
  constraint rights_claims_v1_evidence_refs_check check (jsonb_typeof(evidence_refs)='array' and jsonb_array_length(evidence_refs)>0),
  constraint rights_claims_v1_evidence_sha_check check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  constraint rights_claims_v1_claim_sha_check check (claim_sha256 ~ '^[0-9a-f]{64}$'),
  constraint rights_claims_v1_legal_effect_check check (legal_effect='EVIDENCE_CLAIM_NOT_RIGHTS_GRANT'),
  constraint rights_claims_v1_dail_hash_check check (dail_event_hash ~ '^[0-9a-f]{64}$')
);

create table if not exists chlom_runtime.rights_claim_decisions_v1 (
  decision_id uuid primary key default extensions.gen_random_uuid(),
  claim_id uuid not null references chlom_runtime.rights_claims_v1(claim_id) on delete restrict,
  requested_disposition text not null,
  effective_disposition text not null,
  reason_code text not null,
  verifier_ref text not null,
  evidence_refs jsonb not null,
  evidence_sha256 text not null,
  decision_sha256 text not null unique,
  legal_effect text not null default 'INDEPENDENT_CLAIM_DISPOSITION_NOT_RIGHTS_GRANT',
  dail_event_id uuid not null,
  dail_event_hash text not null,
  created_at timestamptz not null default now(),
  constraint rights_claim_decisions_v1_requested_check check (requested_disposition in ('verified','hold','rejected','superseded')),
  constraint rights_claim_decisions_v1_effective_check check (effective_disposition in ('verified','hold','rejected','superseded')),
  constraint rights_claim_decisions_v1_reason_check check (length(btrim(reason_code)) between 1 and 500),
  constraint rights_claim_decisions_v1_verifier_check check (length(btrim(verifier_ref)) between 1 and 500),
  constraint rights_claim_decisions_v1_evidence_refs_check check (jsonb_typeof(evidence_refs)='array' and jsonb_array_length(evidence_refs)>0),
  constraint rights_claim_decisions_v1_evidence_sha_check check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  constraint rights_claim_decisions_v1_decision_sha_check check (decision_sha256 ~ '^[0-9a-f]{64}$'),
  constraint rights_claim_decisions_v1_legal_effect_check check (legal_effect='INDEPENDENT_CLAIM_DISPOSITION_NOT_RIGHTS_GRANT'),
  constraint rights_claim_decisions_v1_dail_hash_check check (dail_event_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists rights_claims_v1_subject_idx
  on chlom_runtime.rights_claims_v1(tenant_key,subject_ref,right_type,claim_role,created_at);
create index if not exists rights_claims_v1_object_idx
  on chlom_runtime.rights_claims_v1(rights_object_key,created_at);
create index if not exists rights_claim_decisions_v1_claim_idx
  on chlom_runtime.rights_claim_decisions_v1(claim_id,created_at desc,decision_id desc);

alter table chlom_runtime.rights_claims_v1 enable row level security;
alter table chlom_runtime.rights_claims_v1 force row level security;
alter table chlom_runtime.rights_claim_decisions_v1 enable row level security;
alter table chlom_runtime.rights_claim_decisions_v1 force row level security;

create or replace function chlom_runtime.rights_history_reject_mutation_v1()
returns trigger
language plpgsql
set search_path to 'pg_catalog','chlom_runtime'
as $function$
begin
  raise exception 'CHLOM_RIGHTS_HISTORY_IMMUTABLE';
end
$function$;

drop trigger if exists trg_rights_claims_v1_immutable on chlom_runtime.rights_claims_v1;
create trigger trg_rights_claims_v1_immutable
before update or delete on chlom_runtime.rights_claims_v1
for each row execute function chlom_runtime.rights_history_reject_mutation_v1();

drop trigger if exists trg_rights_claim_decisions_v1_immutable on chlom_runtime.rights_claim_decisions_v1;
create trigger trg_rights_claim_decisions_v1_immutable
before update or delete on chlom_runtime.rights_claim_decisions_v1
for each row execute function chlom_runtime.rights_history_reject_mutation_v1();

create or replace function chlom_runtime.rights_norm_scope_v1(p_values text[])
returns text[]
language sql
immutable
set search_path to 'pg_catalog'
as $function$
  select coalesce(array_agg(v order by v),'{}'::text[])
  from (
    select distinct lower(btrim(x)) as v
    from unnest(coalesce(p_values,'{}'::text[])) as x
    where nullif(btrim(x),'') is not null
  ) s
$function$;

create or replace view chlom_runtime.rights_claim_current_v1
with (security_invoker=true)
as
select
  c.*,
  d.decision_id as current_decision_id,
  d.requested_disposition as current_requested_disposition,
  d.effective_disposition as current_disposition,
  d.reason_code as current_reason_code,
  d.verifier_ref as current_verifier_ref,
  d.evidence_sha256 as current_decision_evidence_sha256,
  d.decision_sha256 as current_decision_sha256,
  d.created_at as current_decided_at
from chlom_runtime.rights_claims_v1 c
left join lateral (
  select d1.*
  from chlom_runtime.rights_claim_decisions_v1 d1
  where d1.claim_id=c.claim_id
  order by d1.created_at desc,d1.decision_id desc
  limit 1
) d on true;

create or replace function chlom_runtime.assert_rights_claim_v1(
  p_tenant_key text,
  p_subject_ref text,
  p_right_type text,
  p_claim_role text,
  p_claimant_ref text,
  p_territories text[] default '{}'::text[],
  p_media_scopes text[] default '{}'::text[],
  p_use_scopes text[] default '{}'::text[],
  p_restrictions jsonb default '{}'::jsonb,
  p_evidence_refs jsonb default '[]'::jsonb,
  p_evidence_sha256 text default null,
  p_asserted_by text default null
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','extensions','chlom_runtime'
as $function$
declare
  v_tenant text:=btrim(coalesce(p_tenant_key,''));
  v_subject text:=btrim(coalesce(p_subject_ref,''));
  v_right_type text:=lower(btrim(coalesce(p_right_type,'')));
  v_role text:=lower(btrim(coalesce(p_claim_role,'')));
  v_claimant text:=btrim(coalesce(p_claimant_ref,''));
  v_actor text:=btrim(coalesce(p_asserted_by,''));
  v_territories text[];
  v_media text[];
  v_use text[];
  v_object_key text;
  v_claim_sha text;
  v_claim_id uuid:=extensions.gen_random_uuid();
  v_existing uuid;
  v_dail jsonb;
begin
  if v_tenant !~ '^[A-Za-z0-9._:-]{1,200}$' then raise exception 'CHLOM_RIGHTS_INVALID_TENANT'; end if;
  if v_subject='' or length(v_subject)>1000 then raise exception 'CHLOM_RIGHTS_INVALID_SUBJECT'; end if;
  if v_right_type !~ '^[a-z0-9._:-]{1,200}$' then raise exception 'CHLOM_RIGHTS_INVALID_RIGHT_TYPE'; end if;
  if v_role not in ('ownership','administration','representation') then raise exception 'CHLOM_RIGHTS_INVALID_CLAIM_ROLE'; end if;
  if v_claimant='' or length(v_claimant)>1000 then raise exception 'CHLOM_RIGHTS_INVALID_CLAIMANT'; end if;
  if v_actor='' or length(v_actor)>500 then raise exception 'CHLOM_RIGHTS_INVALID_ASSERTOR'; end if;
  if coalesce(jsonb_typeof(p_restrictions),'')<>'object' then raise exception 'CHLOM_RIGHTS_INVALID_RESTRICTIONS'; end if;
  if coalesce(jsonb_typeof(p_evidence_refs),'')<>'array' or jsonb_array_length(p_evidence_refs)=0 then raise exception 'CHLOM_RIGHTS_EVIDENCE_REQUIRED'; end if;
  if coalesce(p_evidence_sha256,'') !~ '^[0-9a-f]{64}$' then raise exception 'CHLOM_RIGHTS_EVIDENCE_DIGEST_REQUIRED'; end if;

  v_territories:=chlom_runtime.rights_norm_scope_v1(p_territories);
  v_media:=chlom_runtime.rights_norm_scope_v1(p_media_scopes);
  v_use:=chlom_runtime.rights_norm_scope_v1(p_use_scopes);
  v_object_key:=encode(extensions.digest(convert_to(v_tenant||'|'||v_subject||'|'||v_right_type,'UTF8'),'sha256'),'hex');
  v_claim_sha:=encode(extensions.digest(convert_to(jsonb_build_object(
    'tenant_key',v_tenant,'subject_ref',v_subject,'right_type',v_right_type,
    'claim_role',v_role,'claimant_ref',v_claimant,'territories',v_territories,
    'media_scopes',v_media,'use_scopes',v_use,'restrictions',coalesce(p_restrictions,'{}'::jsonb),
    'evidence_refs',p_evidence_refs,'evidence_sha256',p_evidence_sha256
  )::text,'UTF8'),'sha256'),'hex');

  select claim_id into v_existing
  from chlom_runtime.rights_claims_v1
  where claim_sha256=v_claim_sha;
  if v_existing is not null then
    return jsonb_build_object(
      'state','existing','mutation_applied',false,'claim_id',v_existing,
      'claim_sha256',v_claim_sha,'rights_object_key',v_object_key,
      'legal_effect','EVIDENCE_CLAIM_NOT_RIGHTS_GRANT');
  end if;

  v_dail:=chlom_runtime.append_dail_event(
    'chlom.rights.claim.asserted','rights_claim',v_claim_id::text,
    jsonb_build_object(
      'tenant_key',v_tenant,'subject_ref',v_subject,'right_type',v_right_type,
      'claim_role',v_role,'claimant_ref',v_claimant,'rights_object_key',v_object_key,
      'claim_sha256',v_claim_sha,'evidence_sha256',p_evidence_sha256,
      'legal_effect','EVIDENCE_CLAIM_NOT_RIGHTS_GRANT'),
    v_actor,null,'ct.chlom.rights.v1','1',v_object_key,null,
    'ct.chlom.c3.rights-registry.v1:claim-evidence',null,'restricted');

  insert into chlom_runtime.rights_claims_v1(
    claim_id,tenant_key,rights_object_key,subject_ref,right_type,claim_role,claimant_ref,
    territories,media_scopes,use_scopes,restrictions,evidence_refs,evidence_sha256,
    claim_sha256,asserted_by,dail_event_id,dail_event_hash)
  values(
    v_claim_id,v_tenant,v_object_key,v_subject,v_right_type,v_role,v_claimant,
    v_territories,v_media,v_use,coalesce(p_restrictions,'{}'::jsonb),p_evidence_refs,p_evidence_sha256,
    v_claim_sha,v_actor,(v_dail->>'event_id')::uuid,v_dail->>'event_hash');

  return jsonb_build_object(
    'state','asserted','mutation_applied',true,'claim_id',v_claim_id,
    'claim_sha256',v_claim_sha,'rights_object_key',v_object_key,
    'dail_event_id',v_dail->>'event_id','dail_event_hash',v_dail->>'event_hash',
    'legal_effect','EVIDENCE_CLAIM_NOT_RIGHTS_GRANT');
end
$function$;

create or replace function chlom_runtime.record_rights_claim_decision_v1(
  p_claim_id uuid,
  p_disposition text,
  p_reason_code text,
  p_verifier_ref text,
  p_evidence_refs jsonb,
  p_evidence_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','extensions','chlom_runtime'
as $function$
declare
  c chlom_runtime.rights_claims_v1%rowtype;
  v_requested text:=lower(btrim(coalesce(p_disposition,'')));
  v_effective text;
  v_reason text:=btrim(coalesce(p_reason_code,''));
  v_verifier text:=btrim(coalesce(p_verifier_ref,''));
  v_current text;
  v_conflict uuid;
  v_decision_id uuid:=extensions.gen_random_uuid();
  v_decision_sha text;
  v_existing uuid;
  v_dail jsonb;
begin
  select * into c from chlom_runtime.rights_claims_v1 where claim_id=p_claim_id;
  if not found then raise exception 'CHLOM_RIGHTS_CLAIM_NOT_FOUND'; end if;
  if v_requested not in ('verified','hold','rejected','superseded') then raise exception 'CHLOM_RIGHTS_INVALID_DISPOSITION'; end if;
  if v_reason='' or length(v_reason)>500 then raise exception 'CHLOM_RIGHTS_REASON_REQUIRED'; end if;
  if v_verifier='' or length(v_verifier)>500 then raise exception 'CHLOM_RIGHTS_VERIFIER_REQUIRED'; end if;
  if v_verifier=c.asserted_by or v_verifier=c.claimant_ref then raise exception 'CHLOM_RIGHTS_SELF_VERIFICATION_DENIED'; end if;
  if coalesce(jsonb_typeof(p_evidence_refs),'')<>'array' or jsonb_array_length(p_evidence_refs)=0 then raise exception 'CHLOM_RIGHTS_DECISION_EVIDENCE_REQUIRED'; end if;
  if coalesce(p_evidence_sha256,'') !~ '^[0-9a-f]{64}$' then raise exception 'CHLOM_RIGHTS_DECISION_DIGEST_REQUIRED'; end if;

  select current_disposition into v_current
  from chlom_runtime.rights_claim_current_v1
  where claim_id=c.claim_id;

  if v_current in ('rejected','superseded') then
    raise exception 'CHLOM_RIGHTS_TERMINAL_CLAIM_STATE';
  end if;
  if v_current='verified' and v_requested not in ('hold','superseded') then
    raise exception 'CHLOM_RIGHTS_INVALID_VERIFIED_TRANSITION';
  end if;

  v_effective:=v_requested;
  if v_requested='verified' then
    select x.claim_id into v_conflict
    from chlom_runtime.rights_claim_current_v1 x
    where x.claim_id<>c.claim_id
      and x.tenant_key=c.tenant_key
      and x.subject_ref=c.subject_ref
      and x.right_type=c.right_type
      and x.claim_role=c.claim_role
      and x.claimant_ref<>c.claimant_ref
      and x.current_disposition='verified'
      and (cardinality(x.territories)=0 or cardinality(c.territories)=0 or x.territories && c.territories)
      and (cardinality(x.media_scopes)=0 or cardinality(c.media_scopes)=0 or x.media_scopes && c.media_scopes)
      and (cardinality(x.use_scopes)=0 or cardinality(c.use_scopes)=0 or x.use_scopes && c.use_scopes)
    order by x.created_at,x.claim_id
    limit 1;
    if v_conflict is not null then
      v_effective:='hold';
      v_reason:='CONFLICTING_VERIFIED_CLAIM:'||v_conflict::text||':'||v_reason;
    end if;
  end if;

  v_decision_sha:=encode(extensions.digest(convert_to(jsonb_build_object(
    'claim_id',c.claim_id,'requested_disposition',v_requested,'effective_disposition',v_effective,
    'reason_code',v_reason,'verifier_ref',v_verifier,'evidence_refs',p_evidence_refs,
    'evidence_sha256',p_evidence_sha256,'claim_sha256',c.claim_sha256
  )::text,'UTF8'),'sha256'),'hex');

  select decision_id into v_existing
  from chlom_runtime.rights_claim_decisions_v1
  where decision_sha256=v_decision_sha;
  if v_existing is not null then
    return jsonb_build_object(
      'state','existing','mutation_applied',false,'decision_id',v_existing,
      'claim_id',c.claim_id,'requested_disposition',v_requested,'effective_disposition',v_effective,
      'decision_sha256',v_decision_sha,'legal_effect','INDEPENDENT_CLAIM_DISPOSITION_NOT_RIGHTS_GRANT');
  end if;

  v_dail:=chlom_runtime.append_dail_event(
    'chlom.rights.claim.disposition','rights_claim',c.claim_id::text,
    jsonb_build_object(
      'claim_sha256',c.claim_sha256,'rights_object_key',c.rights_object_key,
      'requested_disposition',v_requested,'effective_disposition',v_effective,
      'reason_code',v_reason,'decision_sha256',v_decision_sha,
      'decision_evidence_sha256',p_evidence_sha256,
      'legal_effect','INDEPENDENT_CLAIM_DISPOSITION_NOT_RIGHTS_GRANT'),
    v_verifier,null,'ct.chlom.rights.v1','1',c.rights_object_key,c.dail_event_id::text,
    'ct.chlom.c3.rights-registry.v1:independent-disposition',null,'restricted');

  insert into chlom_runtime.rights_claim_decisions_v1(
    decision_id,claim_id,requested_disposition,effective_disposition,reason_code,verifier_ref,
    evidence_refs,evidence_sha256,decision_sha256,dail_event_id,dail_event_hash)
  values(
    v_decision_id,c.claim_id,v_requested,v_effective,v_reason,v_verifier,
    p_evidence_refs,p_evidence_sha256,v_decision_sha,
    (v_dail->>'event_id')::uuid,v_dail->>'event_hash');

  return jsonb_build_object(
    'state',case when v_effective='hold' and v_requested='verified' then 'hold_conflict' else v_effective end,
    'mutation_applied',true,'decision_id',v_decision_id,'claim_id',c.claim_id,
    'requested_disposition',v_requested,'effective_disposition',v_effective,
    'decision_sha256',v_decision_sha,'dail_event_id',v_dail->>'event_id',
    'dail_event_hash',v_dail->>'event_hash',
    'legal_effect','INDEPENDENT_CLAIM_DISPOSITION_NOT_RIGHTS_GRANT');
end
$function$;

create or replace function chlom_runtime.rights_query_v1(
  p_tenant_key text,
  p_subject_ref text,
  p_right_type text default null
)
returns jsonb
language plpgsql
stable
security definer
set search_path to 'pg_catalog','chlom_runtime'
as $function$
declare
  v_objects jsonb;
begin
  with q as (
    select *
    from chlom_runtime.rights_claim_current_v1
    where tenant_key=btrim(coalesce(p_tenant_key,''))
      and subject_ref=btrim(coalesce(p_subject_ref,''))
      and (nullif(btrim(coalesce(p_right_type,'')),'') is null or right_type=lower(btrim(p_right_type)))
  ), object_keys as (
    select distinct rights_object_key,tenant_key,subject_ref,right_type from q
  ), evaluated as (
    select
      o.*,
      exists(
        select 1
        from q a join q b
          on a.rights_object_key=b.rights_object_key
         and a.claim_id<b.claim_id
         and a.claim_role=b.claim_role
         and a.claimant_ref<>b.claimant_ref
         and coalesce(a.current_disposition,'asserted') not in ('rejected','superseded')
         and coalesce(b.current_disposition,'asserted') not in ('rejected','superseded')
         and (cardinality(a.territories)=0 or cardinality(b.territories)=0 or a.territories && b.territories)
         and (cardinality(a.media_scopes)=0 or cardinality(b.media_scopes)=0 or a.media_scopes && b.media_scopes)
         and (cardinality(a.use_scopes)=0 or cardinality(b.use_scopes)=0 or a.use_scopes && b.use_scopes)
        where a.rights_object_key=o.rights_object_key
      ) as conflict,
      (select count(*) from q x where x.rights_object_key=o.rights_object_key and x.current_disposition='verified') as verified_count,
      (select count(*) from q x where x.rights_object_key=o.rights_object_key and coalesce(x.current_disposition,'asserted') in ('asserted','hold')) as unresolved_count,
      (select count(*) from q x where x.rights_object_key=o.rights_object_key and coalesce(x.current_disposition,'asserted') not in ('rejected','superseded')) as active_count,
      (select jsonb_agg(jsonb_build_object(
        'claim_id',x.claim_id,'claim_role',x.claim_role,'claimant_ref',x.claimant_ref,
        'territories',x.territories,'media_scopes',x.media_scopes,'use_scopes',x.use_scopes,
        'restrictions',x.restrictions,'claim_sha256',x.claim_sha256,
        'evidence_sha256',x.evidence_sha256,'disposition',coalesce(x.current_disposition,'asserted'),
        'decision_sha256',x.current_decision_sha256,'reason_code',x.current_reason_code,
        'legal_effect',x.legal_effect) order by x.created_at,x.claim_id)
       from q x where x.rights_object_key=o.rights_object_key) as claims
    from object_keys o
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'rights_object_key',rights_object_key,'tenant_key',tenant_key,'subject_ref',subject_ref,
    'right_type',right_type,'query_state',case
      when conflict then 'HOLD_CONFLICT'
      when unresolved_count>0 then 'HOLD_UNVERIFIED'
      when verified_count>0 and active_count=verified_count then 'VERIFIED_CLAIMS_NOT_GRANT'
      when active_count=0 then 'NO_ACTIVE_VERIFIED_CLAIM'
      else 'HOLD_UNRESOLVED'
    end,
    'claim_count',jsonb_array_length(coalesce(claims,'[]'::jsonb)),
    'verified_count',verified_count,'active_count',active_count,
    'claims',coalesce(claims,'[]'::jsonb),
    'legal_effect','QUERY_IS_EVIDENCE_STATUS_NOT_RIGHTS_OR_LICENSE_GRANT')
    order by right_type,rights_object_key),'[]'::jsonb)
  into v_objects
  from evaluated;

  return jsonb_build_object(
    'state',case when jsonb_array_length(v_objects)=0 then 'UNKNOWN_NO_CLAIMS' else 'READBACK' end,
    'tenant_key',btrim(coalesce(p_tenant_key,'')),'subject_ref',btrim(coalesce(p_subject_ref,'')),
    'right_type',nullif(lower(btrim(coalesce(p_right_type,''))),''),'objects',v_objects,
    'legal_effect','QUERY_IS_EVIDENCE_STATUS_NOT_RIGHTS_OR_LICENSE_GRANT');
end
$function$;

revoke all on table chlom_runtime.rights_claims_v1 from public,anon,authenticated,service_role;
revoke all on table chlom_runtime.rights_claim_decisions_v1 from public,anon,authenticated,service_role;
grant select on table chlom_runtime.rights_claims_v1 to service_role;
grant select on table chlom_runtime.rights_claim_decisions_v1 to service_role;

revoke all on function chlom_runtime.rights_history_reject_mutation_v1() from public,anon,authenticated,service_role;
revoke all on function chlom_runtime.rights_norm_scope_v1(text[]) from public,anon,authenticated;
revoke all on function chlom_runtime.assert_rights_claim_v1(text,text,text,text,text,text[],text[],text[],jsonb,jsonb,text,text) from public,anon,authenticated;
revoke all on function chlom_runtime.record_rights_claim_decision_v1(uuid,text,text,text,jsonb,text) from public,anon,authenticated;
revoke all on function chlom_runtime.rights_query_v1(text,text,text) from public,anon,authenticated;
grant execute on function chlom_runtime.assert_rights_claim_v1(text,text,text,text,text,text[],text[],text[],jsonb,jsonb,text,text) to service_role;
grant execute on function chlom_runtime.record_rights_claim_decision_v1(uuid,text,text,text,jsonb,text) to service_role;
grant execute on function chlom_runtime.rights_query_v1(text,text,text) to service_role;

comment on table chlom_runtime.rights_claims_v1 is
'CHLOM C3 append-only evidence claims for ownership, administration, or representation. A row is not a rights grant or legal conclusion.';
comment on table chlom_runtime.rights_claim_decisions_v1 is
'CHLOM C3 append-only independent claim dispositions. Contradictory overlapping verified claims fail closed to HOLD; decisions are not rights grants.';
comment on function chlom_runtime.rights_query_v1(text,text,text) is
'Fail-closed C3 rights evidence query. Returns HOLD_CONFLICT/HOLD_UNVERIFIED/VERIFIED_CLAIMS_NOT_GRANT states and never authorizes licensing or entitlement.';
