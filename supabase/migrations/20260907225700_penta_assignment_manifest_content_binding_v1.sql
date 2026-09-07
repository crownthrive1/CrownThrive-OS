-- CrownThrive PentaSecurity / PentaAssignment manifest-content binding hardening v1
--
-- Source candidate only. This hardens the PR3888 post-merge migration cohort review path
-- so semantic PentaSecurity PASS cannot rely on a stored digest that is not recomputed from
-- the exact reviewed migration set. It creates no release, certification, credential,
-- money, D3, rights, provider-write or authority-expansion power.

create or replace function penta_security.verify_assignment_migration_manifest_v1(
  p_source_repo text,
  p_exact_head_sha text,
  p_migrations jsonb,
  p_declared_manifest_sha256 text,
  p_subject_sha256 text
)
returns jsonb
language plpgsql
immutable
set search_path to 'pg_catalog','extensions'
as $fn$
declare
  v_count integer;
  v_unique_count integer;
  v_versions text[];
  v_normalized jsonb;
  v_envelope jsonb;
  v_computed_sha256 text;
begin
  if nullif(btrim(coalesce(p_source_repo,'')),'') is null
     or coalesce(p_exact_head_sha,'') !~ '^[0-9a-f]{40}$' then
    return jsonb_build_object(
      'state','HOLD','reason','MIGRATION_MANIFEST_EXACT_SUBJECT_REQUIRED',
      'authority_created',false
    );
  end if;

  if jsonb_typeof(p_migrations)<>'array' or jsonb_array_length(p_migrations)=0 then
    return jsonb_build_object(
      'state','HOLD','reason','MIGRATION_MANIFEST_ARRAY_REQUIRED',
      'authority_created',false
    );
  end if;

  if exists(
    select 1
    from jsonb_array_elements(p_migrations) e
    where coalesce(e->>'version','') !~ '^[0-9]{14}$'
       or coalesce(e->>'blob','') !~ '^[0-9a-f]{40}$'
  ) then
    return jsonb_build_object(
      'state','HOLD','reason','MIGRATION_MANIFEST_IDENTITY_INVALID',
      'authority_created',false
    );
  end if;

  select
    count(*),
    count(distinct e->>'version'),
    array_agg(e->>'version' order by e->>'version'),
    jsonb_agg(
      jsonb_build_object('version',e->>'version','blob',e->>'blob')
      order by e->>'version'
    )
  into v_count,v_unique_count,v_versions,v_normalized
  from jsonb_array_elements(p_migrations) e;

  if v_unique_count<>v_count then
    return jsonb_build_object(
      'state','HOLD','reason','MIGRATION_MANIFEST_DUPLICATE_VERSION',
      'migration_count',v_count,'unique_version_count',v_unique_count,
      'authority_created',false
    );
  end if;

  -- v1 is deliberately bounded to the four PR3888 bridge/hardening migrations.
  -- A future cohort must introduce a new verifier contract/version rather than silently
  -- widening this exact subject.
  if v_count<>4 or v_versions<>array[
    '20260831093500',
    '20260831135000',
    '20260831143500',
    '20260831154500'
  ]::text[] then
    return jsonb_build_object(
      'state','HOLD','reason','MIGRATION_MANIFEST_REQUIRED_SET_MISMATCH',
      'observed_versions',to_jsonb(v_versions),
      'authority_created',false
    );
  end if;

  v_envelope:=jsonb_build_object(
    'contract','ct.penta.security.assignment-migration-manifest.v1',
    'source_repo',p_source_repo,
    'exact_head_sha',p_exact_head_sha,
    'migrations',v_normalized
  );
  v_computed_sha256:=encode(
    extensions.digest(convert_to(v_envelope::text,'UTF8'),'sha256'),
    'hex'
  );

  if coalesce(p_declared_manifest_sha256,'')<>v_computed_sha256
     or coalesce(p_subject_sha256,'')<>v_computed_sha256 then
    return jsonb_build_object(
      'state','HOLD','reason','MIGRATION_MANIFEST_DIGEST_MISMATCH',
      'computed_manifest_sha256',v_computed_sha256,
      'declared_manifest_sha256',p_declared_manifest_sha256,
      'subject_sha256',p_subject_sha256,
      'authority_created',false
    );
  end if;

  return jsonb_build_object(
    'state','PASS',
    'contract','ct.penta.security.assignment-migration-manifest.v1',
    'computed_manifest_sha256',v_computed_sha256,
    'normalized_migrations',v_normalized,
    'migration_count',v_count,
    'authority_created',false
  );
end
$fn$;

revoke all on function penta_security.verify_assignment_migration_manifest_v1(text,text,jsonb,text,text)
  from public,anon,authenticated;
grant execute on function penta_security.verify_assignment_migration_manifest_v1(text,text,jsonb,text,text)
  to service_role;

-- Preserve the original exact-source reviewer as an owner-only implementation detail.
-- The public canonical service-role entrypoint below becomes the fail-closed wrapper.
do $rename$
begin
  if to_regprocedure('penta_security.review_assignment_exact_subject_unbound_v1(uuid)') is null then
    if to_regprocedure('penta_security.review_assignment_exact_subject_v1(uuid)') is null then
      raise exception 'PENTASECURITY_ASSIGNMENT_REVIEW_CORE_MISSING';
    end if;
    alter function penta_security.review_assignment_exact_subject_v1(uuid)
      rename to review_assignment_exact_subject_unbound_v1;
  end if;
end
$rename$;

revoke all on function penta_security.review_assignment_exact_subject_unbound_v1(uuid)
  from public,anon,authenticated,service_role;

create or replace function penta_security.review_assignment_exact_subject_v1(p_assignment_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_security','integration_control'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_manifest jsonb;
  v_core jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;

  select * into a
  from integration_control.penta_assignment_contracts_v1
  where assignment_id=p_assignment_id;
  if not found then
    return jsonb_build_object(
      'state','HOLD','reason','ASSIGNMENT_NOT_FOUND',
      'assignment_id',p_assignment_id,'authority_created',false
    );
  end if;

  v_manifest:=penta_security.verify_assignment_migration_manifest_v1(
    a.source_repo,
    a.exact_head_sha,
    a.metadata->'migrations',
    a.metadata->>'migration_manifest_sha256',
    a.exact_artifact_sha256
  );

  if v_manifest->>'state'<>'PASS' then
    return v_manifest||jsonb_build_object(
      'assignment_id',a.assignment_id,
      'exact_head_sha',a.exact_head_sha,
      'subject_sha256',a.exact_artifact_sha256,
      'security_decision',true,
      'independent_certification',false,
      'release_authorized',false,
      'authority_created',false
    );
  end if;

  v_core:=penta_security.review_assignment_exact_subject_unbound_v1(p_assignment_id);
  return v_core||jsonb_build_object(
    'manifest_contract',v_manifest->>'contract',
    'computed_manifest_sha256',v_manifest->>'computed_manifest_sha256',
    'manifest_content_bound',true,
    'authority_created',false
  );
end
$fn$;

revoke all on function penta_security.review_assignment_exact_subject_v1(uuid)
  from public,anon,authenticated;
grant execute on function penta_security.review_assignment_exact_subject_v1(uuid)
  to service_role;

-- Migration-time structural readback only; no semantic review is executed here.
do $verify$
declare
  v_wrapper text;
  v_helper text;
begin
  select pg_get_functiondef('penta_security.verify_assignment_migration_manifest_v1(text,text,jsonb,text,text)'::regprocedure)
    into v_helper;
  if strpos(v_helper,'MIGRATION_MANIFEST_DUPLICATE_VERSION')=0
     or strpos(v_helper,'MIGRATION_MANIFEST_REQUIRED_SET_MISMATCH')=0
     or strpos(v_helper,'MIGRATION_MANIFEST_DIGEST_MISMATCH')=0
     or strpos(v_helper,'ct.penta.security.assignment-migration-manifest.v1')=0 then
    raise exception 'PENTASECURITY_MANIFEST_VERIFIER_CONTRACT_INCOMPLETE';
  end if;

  select pg_get_functiondef('penta_security.review_assignment_exact_subject_v1(uuid)'::regprocedure)
    into v_wrapper;
  if strpos(v_wrapper,'verify_assignment_migration_manifest_v1')=0
     or strpos(v_wrapper,'review_assignment_exact_subject_unbound_v1')=0
     or strpos(v_wrapper,'manifest_content_bound')=0 then
    raise exception 'PENTASECURITY_MANIFEST_WRAPPER_CONTRACT_INCOMPLETE';
  end if;

  if has_function_privilege('service_role','penta_security.review_assignment_exact_subject_unbound_v1(uuid)','EXECUTE') then
    raise exception 'PENTASECURITY_UNBOUND_CORE_MUST_NOT_BE_SERVICE_ROLE_EXECUTABLE';
  end if;
end
$verify$;