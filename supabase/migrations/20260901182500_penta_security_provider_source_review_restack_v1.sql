-- CrownThrive OS / PentaSecurity
-- Current-main restack of the unique provider-source security review capability preserved in
-- PR #1995 head 945e6ff7bd6b5e74c271164cea6fed6488a00f5e.
-- The predecessor PR/branch remains historical evidence; this migration is additive and
-- does not manufacture certification, provider-write, credential, financial, merge/release,
-- voting/quorum, or D3 authority.

create schema if not exists penta_security;

create table if not exists penta_security.provider_source_policies_v1 (
  policy_key text not null,
  policy_version text not null,
  system_family text not null default 'PentaSecurity',
  provider_system text not null,
  resource_type text not null,
  resource_id text not null,
  repository text not null,
  source_path text not null,
  required_literals text[] not null default '{}'::text[],
  forbidden_literals text[] not null default '{}'::text[],
  max_source_bytes integer not null default 250000 check (max_source_bytes between 1 and 2000000),
  state text not null default 'active' check (state in ('active','retired','hold')),
  supersedes_policy_version text,
  authority_effect text not null default 'none' check (authority_effect='none'),
  created_at timestamptz not null default clock_timestamp(),
  primary key(policy_key,policy_version),
  check (repository ~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'),
  check (source_path <> '' and source_path !~ '(^/|\.\.)')
);

create or replace function penta_security.reject_provider_source_policy_mutation_v1()
returns trigger language plpgsql security definer
set search_path='pg_catalog','penta_security'
as $fn$ begin raise exception 'append_only_provider_source_policy'; end $fn$;

drop trigger if exists penta_security_provider_source_policies_immutable_v1 on penta_security.provider_source_policies_v1;
create trigger penta_security_provider_source_policies_immutable_v1
before update or delete on penta_security.provider_source_policies_v1
for each row execute function penta_security.reject_provider_source_policy_mutation_v1();

create table if not exists penta_security.provider_source_review_receipts_v1 (
  review_id uuid primary key default gen_random_uuid(),
  policy_key text not null,
  policy_version text not null,
  provider_system text not null,
  resource_type text not null,
  resource_id text not null,
  repository text not null,
  source_path text not null,
  exact_head_sha text not null check (exact_head_sha ~ '^[0-9a-f]{40}$'),
  disposition text not null,
  source_sha256 text check (source_sha256 is null or source_sha256 ~ '^[0-9a-f]{64}$'),
  source_bytes integer,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  dail_event_id uuid not null,
  dail_event_hash text not null,
  reviewer_system_key text not null default 'penta.security',
  provider_write boolean not null default false,
  credential_change boolean not null default false,
  money_movement boolean not null default false,
  d3_execution boolean not null default false,
  authority_expansion boolean not null default false,
  reviewed_at timestamptz not null default clock_timestamp(),
  unique(policy_key,policy_version,exact_head_sha,evidence_sha256)
);

create or replace function penta_security.reject_provider_source_review_mutation_v1()
returns trigger language plpgsql security definer
set search_path='pg_catalog','penta_security'
as $fn$ begin raise exception 'append_only_provider_source_review_receipt'; end $fn$;

drop trigger if exists penta_security_provider_source_review_receipts_immutable_v1 on penta_security.provider_source_review_receipts_v1;
create trigger penta_security_provider_source_review_receipts_immutable_v1
before update or delete on penta_security.provider_source_review_receipts_v1
for each row execute function penta_security.reject_provider_source_review_mutation_v1();

create or replace function penta_security.review_github_provider_source_v1(p_policy_key text,p_exact_head_sha text)
returns jsonb
language plpgsql security definer
set search_path='pg_catalog','penta_security','public','chlom_runtime','extensions'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_policy penta_security.provider_source_policies_v1%rowtype;
  v_url text; v_http extensions.http_response; v_source text; v_source_sha text; v_bytes integer:=0;
  v_required text; v_forbidden text; v_missing text[]:='{}'::text[]; v_forbidden_present text[]:='{}'::text[];
  v_disposition text; v_payload jsonb; v_sha text; v_dail jsonb; v_event_id uuid; v_event_hash text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if p_policy_key is null or btrim(p_policy_key)='' then raise exception 'policy_key_required'; end if;

  select * into v_policy from penta_security.provider_source_policies_v1
  where policy_key=p_policy_key order by created_at desc,policy_version desc limit 1;
  if not found then raise exception 'provider_source_policy_not_found'; end if;

  if v_policy.state<>'active' then v_disposition:='HOLD_POLICY_NOT_ACTIVE';
  elsif coalesce(p_exact_head_sha,'') !~ '^[0-9a-f]{40}$' then v_disposition:='HOLD_EXACT_HEAD_INVALID'; end if;

  if v_disposition is null then
    v_url:='https://raw.githubusercontent.com/'||v_policy.repository||'/'||p_exact_head_sha||'/'||v_policy.source_path;
    begin v_http:=extensions.http_get(v_url); exception when others then v_disposition:='HOLD_SOURCE_FETCH_FAILED'; end;
    if v_disposition is null then
      if v_http.status<>200 then v_disposition:='HOLD_SOURCE_FETCH_FAILED';
      else
        v_source:=coalesce(v_http.content,''); v_bytes:=octet_length(v_source);
        if v_bytes=0 then v_disposition:='HOLD_SOURCE_EMPTY';
        elsif v_bytes>v_policy.max_source_bytes then v_disposition:='HOLD_SOURCE_TOO_LARGE'; end if;
      end if;
    end if;
  end if;

  if v_source is not null then
    v_source_sha:=encode(extensions.digest(convert_to(v_source,'UTF8'),'sha256'),'hex');
    foreach v_required in array v_policy.required_literals loop if strpos(v_source,v_required)=0 then v_missing:=array_append(v_missing,v_required); end if; end loop;
    foreach v_forbidden in array v_policy.forbidden_literals loop if strpos(v_source,v_forbidden)>0 then v_forbidden_present:=array_append(v_forbidden_present,v_forbidden); end if; end loop;
    if v_disposition is null and cardinality(v_missing)>0 then v_disposition:='HOLD_REQUIRED_SECURITY_CONTROL_MISSING';
    elsif v_disposition is null and cardinality(v_forbidden_present)>0 then v_disposition:='HOLD_FORBIDDEN_SECURITY_PATTERN_PRESENT';
    elsif v_disposition is null then v_disposition:='PASS'; end if;
  end if;

  v_payload:=jsonb_build_object(
    'contract','ct.penta.security.provider-source-review.v1','policy_key',v_policy.policy_key,'policy_version',v_policy.policy_version,
    'provider_system',v_policy.provider_system,'resource_type',v_policy.resource_type,'resource_id',v_policy.resource_id,
    'repository',v_policy.repository,'source_path',v_policy.source_path,'exact_head_sha',p_exact_head_sha,'source_sha256',v_source_sha,
    'source_bytes',v_bytes,'required_control_count',cardinality(v_policy.required_literals),'forbidden_pattern_count',cardinality(v_policy.forbidden_literals),
    'missing_required_controls',to_jsonb(v_missing),'forbidden_patterns_present',to_jsonb(v_forbidden_present),'raw_source_stored',false,
    'source_fetch_host','raw.githubusercontent.com','disposition',coalesce(v_disposition,'HOLD_UNCLASSIFIED'),'security_decision',true,
    'independent_certification',false,'provider_write',false,'credential_change',false,'money_movement',false,'d3_execution',false,
    'authority_expansion',false,'reviewed_at',clock_timestamp());
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');

  v_dail:=public.chlom_append_dail_event(
    p_event_type=>'penta.security.provider-source-review.completed.v1',p_entity_type=>'penta_security_provider_source_review',
    p_entity_id=>v_policy.resource_id||':'||p_exact_head_sha,p_payload=>v_payload||jsonb_build_object('evidence_sha256',v_sha),
    p_actor_ref=>'PentaSecurity',p_actor_did=>null,p_agent_id=>'penta.security',p_entity_version=>'1.0.0',
    p_correlation_id=>'penta-security-provider-review:'||v_policy.resource_id||':'||p_exact_head_sha,p_causation_id=>null,
    p_authority_basis=>'Bounded D1 read-only exact-head provider source security decision; independent certification remains separate',
    p_approval_id=>null,p_visibility_class=>'internal');
  v_event_id:=nullif(v_dail->>'event_id','')::uuid;
  select event_hash into v_event_hash from chlom_runtime.dail_events where event_id=v_event_id;
  if v_event_hash is null then raise exception 'DAIL_PENTASECURITY_PROVIDER_REVIEW_READBACK_FAILED'; end if;

  insert into penta_security.provider_source_review_receipts_v1(
    policy_key,policy_version,provider_system,resource_type,resource_id,repository,source_path,exact_head_sha,disposition,
    source_sha256,source_bytes,evidence,evidence_sha256,dail_event_id,dail_event_hash)
  values(v_policy.policy_key,v_policy.policy_version,v_policy.provider_system,v_policy.resource_type,v_policy.resource_id,v_policy.repository,
    v_policy.source_path,p_exact_head_sha,coalesce(v_disposition,'HOLD_UNCLASSIFIED'),v_source_sha,v_bytes,v_payload,v_sha,v_event_id,v_event_hash)
  on conflict(policy_key,policy_version,exact_head_sha,evidence_sha256) do nothing;

  return v_payload||jsonb_build_object('evidence_sha256',v_sha,'dail_event_id',v_event_id,'dail_event_hash',v_event_hash);
end $fn$;

-- Preserve the predecessor policy history exactly, then append the corrected version.
insert into penta_security.provider_source_policies_v1(policy_key,policy_version,provider_system,resource_type,resource_id,repository,source_path,required_literals,forbidden_literals,max_source_bytes,state,supersedes_policy_version)
values('ct.penta.security.policy.institutional-pr-terminal-provider.v1','1.0.0','supabase','edge_function_source','penta-institutional-pr-terminal-provider','crownthrive1/CrownThrive-OS','supabase/functions/penta-institutional-pr-terminal-provider/index.ts',
array['sb.schema("integration_control")','penta_pr_closeout_claim_v1','penta_pr_closeout_result_v1','ONE_TIME_WAKE_REQUIRED','REPOSITORY_NOT_ALLOWLISTED','crownthrive1/CrownThrive-OS','EXACT_HEAD_MISMATCH','PR_DRAFT','action.expected_head_sha','authority_expansion: false']::text[],
array['sb.rpc("penta_pr_closeout_claim_v1"','sb.rpc("penta_pr_closeout_result_v1"','public.penta_pr_closeout_claim_v1','public.penta_pr_closeout_result_v1']::text[],150000,'active',null)
on conflict(policy_key,policy_version) do nothing;

insert into penta_security.provider_source_policies_v1(policy_key,policy_version,provider_system,resource_type,resource_id,repository,source_path,required_literals,forbidden_literals,max_source_bytes,state,supersedes_policy_version)
values('ct.penta.security.policy.institutional-pr-terminal-provider.v1','1.0.1','supabase','edge_function_source','penta-institutional-pr-terminal-provider','crownthrive1/CrownThrive-OS','supabase/functions/penta-institutional-pr-terminal-provider/index.ts',
array['sb.schema("integration_control")','penta_pr_closeout_claim_v1','penta_pr_closeout_result_v1','ONE_TIME_WAKE_REQUIRED','REPOSITORY_NOT_ALLOWLISTED','crownthrive1/CrownThrive-OS','EXACT_HEAD_MISMATCH','PR_DRAFT','action.expected_head_sha','authority_expansion: false']::text[],
array['sb.rpc("penta_pr_closeout_claim_v1"','sb.rpc("penta_pr_closeout_result_v1"']::text[],150000,'active','1.0.0')
on conflict(policy_key,policy_version) do nothing;

revoke all on schema penta_security from public;
grant usage on schema penta_security to service_role;
revoke all on table penta_security.provider_source_policies_v1 from public,anon,authenticated;
revoke all on table penta_security.provider_source_review_receipts_v1 from public,anon,authenticated;
grant select on table penta_security.provider_source_policies_v1 to service_role;
grant select on table penta_security.provider_source_review_receipts_v1 to service_role;
revoke all on function penta_security.review_github_provider_source_v1(text,text) from public,anon,authenticated;
grant execute on function penta_security.review_github_provider_source_v1(text,text) to service_role;
revoke all on function penta_security.reject_provider_source_policy_mutation_v1() from public,anon,authenticated;
revoke all on function penta_security.reject_provider_source_review_mutation_v1() from public,anon,authenticated;

do $verify$
declare v_count integer;
begin
  select count(*) into v_count from penta_security.provider_source_policies_v1
  where policy_key='ct.penta.security.policy.institutional-pr-terminal-provider.v1' and policy_version in ('1.0.0','1.0.1');
  if v_count<>2 then raise exception 'PENTASECURITY_PROVIDER_POLICY_LINEAGE_MISSING'; end if;
  if has_function_privilege('public','penta_security.review_github_provider_source_v1(text,text)','EXECUTE')
     or has_function_privilege('anon','penta_security.review_github_provider_source_v1(text,text)','EXECUTE')
     or has_function_privilege('authenticated','penta_security.review_github_provider_source_v1(text,text)','EXECUTE') then
    raise exception 'PENTASECURITY_PROVIDER_REVIEW_PUBLIC_EXECUTE_EXPOSURE';
  end if;
  if not has_function_privilege('service_role','penta_security.review_github_provider_source_v1(text,text)','EXECUTE') then
    raise exception 'PENTASECURITY_PROVIDER_REVIEW_SERVICE_ROLE_MISSING';
  end if;
end $verify$;