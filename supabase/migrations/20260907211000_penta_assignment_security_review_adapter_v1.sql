-- CrownThrive PentaSecurity / PentaAssignment exact-subject review adapter v1
--
-- Source candidate only until current exact-head CI, PentaSecurity/CHLOM/applicable-CIE
-- review, independent PentaCertifier, governed merge/apply and production readback pass.
--
-- PentaSecurity may emit an assignment owner result only after it independently reviews
-- every migration at the assignment exact Git head AND proves the manifest Git blob
-- identity is the Git object for the exact bytes reviewed. This creates no certification,
-- release, provider-write, credential, money, D3, rights or authority-expansion power.

insert into penta_security.provider_source_policies_v1(
  policy_key,policy_version,system_family,provider_system,resource_type,resource_id,
  repository,source_path,required_literals,forbidden_literals,max_source_bytes,state,
  supersedes_policy_version,authority_effect
)
values
(
  'ct.penta.security.assignment-migration.20260831093500.v1','1.0.0','SECURITY_TRUST','github','migration_source',
  'assignment-migration:20260831093500','crownthrive1/CrownThrive-OS',
  'supabase/migrations/20260831093500_penta_assignment_review_only_owner_routes_v1.sql',
  array[
    '''route_mode'',''review_only''',
    '''pm_execution_eligible'',false',
    '''authority_expansion'',false',
    'REVIEW_ONLY_ROUTE_MUST_BE_CENSUS_HANDOFF',
    'HOLD_ASSIGNMENT_REVIEW_TRANSPORT_PENDING'
  ]::text[],
  array[
    '''provider_write'',true',
    '''credential_change'',true',
    '''money_movement'',true',
    '''d3_execution'',true',
    '''authority_expansion'',true'
  ]::text[],
  300000,'active',null,'none'
),
(
  'ct.penta.security.assignment-migration.20260831135000.v1','1.0.0','SECURITY_TRUST','github','migration_source',
  'assignment-migration:20260831135000','crownthrive1/CrownThrive-OS',
  'supabase/migrations/20260831135000_penta_assignment_release_gate_bridge_v1.sql',
  array[
    'release_gate_exact_head_mismatch',
    'release_gate_subject_digest_mismatch',
    'release_gate_dail_readback_required',
    'PENTASECURITY_EXACT_SUBJECT_PASS',
    'OWNER_RESULTS:'
  ]::text[],
  array[
    '''provider_write'',true',
    '''money_movement'',true',
    '''credential_change'',true',
    '''authority_expansion'',true'
  ]::text[],
  500000,'active',null,'none'
),
(
  'ct.penta.security.assignment-migration.20260831143500.v1','1.0.0','SECURITY_TRUST','github','migration_source',
  'assignment-migration:20260831143500','crownthrive1/CrownThrive-OS',
  'supabase/migrations/20260831143500_penta_assignment_release_gate_dail_binding_hardening_v1.sql',
  array[
    'ct.penta.release-gate.receipt.v1',
    'release_gate_dail_payload_contract_mismatch',
    'assignment_id',
    'authority_system_key',
    'authority_created'
  ]::text[],
  array[
    '''authority_created'',true',
    '''release_authorized'',true'
  ]::text[],
  300000,'active',null,'none'
),
(
  'ct.penta.security.assignment-migration.20260831154500.v1','1.0.0','SECURITY_TRUST','github','migration_source',
  'assignment-migration:20260831154500','crownthrive1/CrownThrive-OS',
  'supabase/migrations/20260831154500_penta_wire_assignment_owner_review_transport_v1.sql',
  array[
    'PENTAWIRE_NOT_ASSIGNED_OWNER',
    'GITHUB_EXACT_HEAD_PROVIDER_EVIDENCE_MISSING',
    '''security_decision'',false',
    'penta_assignment_record_owner_result_v1',
    '''authority_expansion'',false'
  ]::text[],
  array[
    '''security_decision'',true',
    '''independent_certification'',true',
    '''authority_expansion'',true'
  ]::text[],
  600000,'active',null,'none'
)
on conflict(policy_key,policy_version) do nothing;

create or replace function penta_security.review_assignment_exact_subject_v1(p_assignment_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_security','integration_control','public','chlom_runtime','extensions'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  m jsonb;
  v_version text;
  v_blob text;
  v_policy_key text;
  v_policy penta_security.provider_source_policies_v1%rowtype;
  v_review jsonb;
  v_reviews jsonb:='[]'::jsonb;
  v_missing jsonb:='[]'::jsonb;
  v_review_count integer:=0;
  v_pass_count integer:=0;
  v_existing_owner_pass boolean:=false;
  v_existing_gate_pass boolean:=false;
  v_http extensions.http_response;
  v_source text;
  v_source_bytes integer;
  v_source_sha256 text;
  v_computed_blob text;
  v_review_base_ok boolean;
  v_evidence jsonb;
  v_evidence_sha text;
  v_gate_payload jsonb;
  v_gate_dail jsonb;
  v_gate_event_id uuid;
  v_gate_event_hash text;
  v_owner_result jsonb;
  v_gate_result jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;

  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:security:assignment-review:'||coalesce(p_assignment_id::text,''),0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','assignment_id',p_assignment_id,'authority_created',false);
  end if;

  select * into a
  from integration_control.penta_assignment_contracts_v1
  where assignment_id=p_assignment_id;
  if not found then
    return jsonb_build_object('state','HOLD','reason','ASSIGNMENT_NOT_FOUND','assignment_id',p_assignment_id,'authority_created',false);
  end if;

  if not (a.owner_pentas ? 'PentaSecurity') then
    return jsonb_build_object('state','HOLD','reason','PENTASECURITY_NOT_ASSIGNED_OWNER','assignment_id',a.assignment_id,'authority_created',false);
  end if;

  if a.risk_class not in ('D0','D1','D2')
     or a.authority_ceiling not in ('D0','D1','D2')
     or a.d3_human_reserved is not true
     or a.provider_write_allowed
     or a.money_movement_allowed
     or a.credential_change_allowed
     or a.authority_expansion then
    return jsonb_build_object('state','HOLD','reason','ASSIGNMENT_AUTHORITY_BOUNDARY','assignment_id',a.assignment_id,'authority_created',false);
  end if;

  if coalesce(a.exact_head_sha,'') !~ '^[0-9a-f]{40}$'
     or coalesce(a.exact_artifact_sha256,'') !~ '^[0-9a-f]{64}$'
     or coalesce(a.exact_artifact_ref,'')='' then
    return jsonb_build_object('state','HOLD','reason','EXACT_SUBJECT_REQUIRED','assignment_id',a.assignment_id,'authority_created',false);
  end if;

  if coalesce(a.metadata->>'migration_manifest_sha256','')<>a.exact_artifact_sha256
     or jsonb_typeof(a.metadata->'migrations')<>'array'
     or jsonb_array_length(a.metadata->'migrations')=0 then
    return jsonb_build_object('state','HOLD','reason','EXACT_MIGRATION_MANIFEST_REQUIRED','assignment_id',a.assignment_id,'authority_created',false);
  end if;

  select exists(
    select 1 from integration_control.penta_assignment_owner_results_v1 r
    where r.assignment_id=a.assignment_id
      and r.owner_penta='PentaSecurity'
      and r.result_state='PASS'
      and r.exact_head_sha=a.exact_head_sha
      and r.exact_artifact_sha256=a.exact_artifact_sha256
  ) into v_existing_owner_pass;

  select exists(
    select 1 from integration_control.penta_assignment_release_gate_bindings_v1 g
    where g.assignment_id=a.assignment_id
      and g.gate_kind='PENTASECURITY'
      and g.disposition='PASS'
      and g.authority_system_key='penta.security'
      and g.exact_head_sha=a.exact_head_sha
      and g.subject_sha256=a.exact_artifact_sha256
  ) into v_existing_gate_pass;

  if v_existing_owner_pass and v_existing_gate_pass then
    return jsonb_build_object(
      'state','PASS_DEDUPED','assignment_id',a.assignment_id,
      'exact_head_sha',a.exact_head_sha,'subject_sha256',a.exact_artifact_sha256,
      'security_decision',true,'independent_certification',false,'release_authorized',false,
      'authority_created',false
    );
  end if;

  for m in select value from jsonb_array_elements(a.metadata->'migrations') loop
    v_version:=coalesce(m->>'version','');
    v_blob:=coalesce(m->>'blob','');
    v_review_count:=v_review_count+1;
    v_source:=null;
    v_source_bytes:=null;
    v_source_sha256:=null;
    v_computed_blob:=null;
    v_review_base_ok:=false;

    if v_version !~ '^[0-9]{14}$' or v_blob !~ '^[0-9a-f]{40}$' then
      v_missing:=v_missing||jsonb_build_array('MIGRATION_IDENTITY_INVALID:'||coalesce(v_version,'<null>'));
      continue;
    end if;

    v_policy_key:='ct.penta.security.assignment-migration.'||v_version||'.v1';
    select * into v_policy
    from penta_security.provider_source_policies_v1 p
    where p.policy_key=v_policy_key and p.state='active'
      and p.repository=a.source_repo
      and p.resource_id='assignment-migration:'||v_version
    order by p.created_at desc,p.policy_version desc
    limit 1;
    if not found then
      v_missing:=v_missing||jsonb_build_array('SOURCE_POLICY_MISSING:'||v_version);
      continue;
    end if;

    begin
      v_review:=penta_security.review_github_provider_source_v1(v_policy_key,a.exact_head_sha);
    exception when others then
      v_review:=jsonb_build_object('disposition','HOLD_SOURCE_REVIEW_RUNTIME_ERROR','error_class',sqlstate,'authority_expansion',false);
    end;

    v_review_base_ok :=
      v_review->>'disposition'='PASS'
      and coalesce(v_review->>'exact_head_sha','')=a.exact_head_sha
      and coalesce(v_review->>'source_sha256','') ~ '^[0-9a-f]{64}$'
      and coalesce(v_review->>'evidence_sha256','') ~ '^[0-9a-f]{64}$'
      and coalesce(v_review->>'dail_event_hash','') ~ '^[0-9a-f]{64}$'
      and coalesce((v_review->>'authority_expansion')::boolean,true)=false;

    if v_review_base_ok then
      begin
        v_http:=extensions.http_get(
          'https://raw.githubusercontent.com/'||v_policy.repository||'/'||a.exact_head_sha||'/'||v_policy.source_path
        );
      exception when others then
        v_http:=null;
      end;

      if v_http is null or v_http.status<>200 then
        v_missing:=v_missing||jsonb_build_array('SOURCE_BLOB_FETCH_FAILED:'||v_version);
      else
        v_source:=coalesce(v_http.content,'');
        v_source_bytes:=octet_length(convert_to(v_source,'UTF8'));
        if v_source_bytes=0 or v_source_bytes>v_policy.max_source_bytes then
          v_missing:=v_missing||jsonb_build_array('SOURCE_BLOB_BYTES_INVALID:'||v_version);
        else
          v_source_sha256:=encode(extensions.digest(convert_to(v_source,'UTF8'),'sha256'),'hex');
          v_computed_blob:=encode(
            extensions.digest(
              convert_to('blob '||v_source_bytes::text,'UTF8') || decode('00','hex') || convert_to(v_source,'UTF8'),
              'sha1'
            ),
            'hex'
          );

          if v_source_sha256<>coalesce(v_review->>'source_sha256','') then
            v_missing:=v_missing||jsonb_build_array('SOURCE_REVIEW_BYTES_MISMATCH:'||v_version);
          elsif v_blob<>v_computed_blob then
            v_missing:=v_missing||jsonb_build_array('MIGRATION_BLOB_SOURCE_MISMATCH:'||v_version);
          else
            v_pass_count:=v_pass_count+1;
          end if;
        end if;
      end if;
    else
      v_missing:=v_missing||jsonb_build_array('SOURCE_REVIEW_NOT_PASS:'||v_version||':'||coalesce(v_review->>'disposition','UNKNOWN'));
    end if;

    v_reviews:=v_reviews||jsonb_build_array(jsonb_build_object(
      'version',v_version,
      'manifest_blob',v_blob,
      'computed_git_blob_sha1',v_computed_blob,
      'blob_match',coalesce(v_blob=v_computed_blob,false),
      'policy_key',v_policy_key,
      'disposition',v_review->>'disposition',
      'review_source_sha256',v_review->>'source_sha256',
      'bound_source_sha256',v_source_sha256,
      'source_bytes',v_source_bytes,
      'evidence_sha256',v_review->>'evidence_sha256',
      'dail_event_id',v_review->>'dail_event_id',
      'dail_event_hash',v_review->>'dail_event_hash'
    ));
  end loop;

  if v_review_count=0 or v_pass_count<>v_review_count or jsonb_array_length(v_missing)>0 then
    return jsonb_build_object(
      'state','HOLD','reason','PENTASECURITY_EXACT_SOURCE_REVIEWS_INCOMPLETE',
      'assignment_id',a.assignment_id,'exact_head_sha',a.exact_head_sha,
      'subject_sha256',a.exact_artifact_sha256,
      'review_count',v_review_count,'pass_count',v_pass_count,
      'missing',v_missing,'reviews',v_reviews,
      'security_decision',true,'independent_certification',false,'release_authorized',false,
      'authority_created',false
    );
  end if;

  v_evidence:=jsonb_build_object(
    'contract','ct.penta.security.assignment-exact-subject-review.v1',
    'assignment_id',a.assignment_id,
    'assignment_key',a.assignment_key,
    'source_repo',a.source_repo,
    'source_pr_number',a.source_pr_number,
    'exact_artifact_ref',a.exact_artifact_ref,
    'exact_head_sha',a.exact_head_sha,
    'subject_sha256',a.exact_artifact_sha256,
    'migration_manifest_sha256',a.metadata->>'migration_manifest_sha256',
    'migration_review_count',v_review_count,
    'migration_pass_count',v_pass_count,
    'source_reviews',v_reviews,
    'security_decision',true,
    'chlom_rights_decision',false,
    'cie_decision',false,
    'independent_certification',false,
    'release_decision',false,
    'provider_write',false,
    'credential_change',false,
    'money_movement',false,
    'd3_execution',false,
    'authority_expansion',false,
    'reviewer_system_key','penta.security',
    'reviewed_at',clock_timestamp()
  );
  v_evidence_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

  v_gate_payload:=jsonb_build_object(
    'release_gate_contract','ct.penta.release-gate.receipt.v1',
    'assignment_id',a.assignment_id,
    'gate_kind','PENTASECURITY',
    'authority_system_key','penta.security',
    'exact_head_sha',a.exact_head_sha,
    'subject_sha256',a.exact_artifact_sha256,
    'disposition','PASS',
    'evidence_ref','penta-security-assignment-review:'||a.assignment_id::text,
    'evidence_sha256',v_evidence_sha,
    'authority_created',false,
    'certification_issued',false,
    'release_authorized',false,
    'source_review_count',v_review_count
  );

  v_gate_dail:=public.chlom_append_dail_event(
    p_event_type=>'penta.security.assignment-release-gate.completed.v1',
    p_entity_type=>'penta_assignment_security_gate',
    p_entity_id=>a.assignment_id::text,
    p_payload=>v_gate_payload,
    p_actor_ref=>'PentaSecurity',
    p_actor_did=>null,
    p_agent_id=>'penta.security',
    p_entity_version=>'1.0.0',
    p_correlation_id=>'penta-security-assignment:'||a.assignment_id::text||':'||a.exact_head_sha,
    p_causation_id=>null,
    p_authority_basis=>'Bounded D1/D2 exact-subject source security decision; CHLOM/CIE and independent certification remain separate',
    p_approval_id=>null,
    p_visibility_class=>'internal'
  );
  v_gate_event_id:=nullif(v_gate_dail->>'event_id','')::uuid;
  select event_hash into v_gate_event_hash
  from chlom_runtime.dail_events
  where event_id=v_gate_event_id;
  if v_gate_event_hash is null then raise exception 'DAIL_PENTASECURITY_ASSIGNMENT_GATE_READBACK_FAILED'; end if;

  v_owner_result:=integration_control.penta_assignment_record_owner_result_v1(
    a.assignment_id,'PentaSecurity','PASS',a.exact_artifact_ref,a.exact_artifact_sha256,a.exact_head_sha,
    v_evidence||jsonb_build_object(
      'release_gate_event_id',v_gate_event_id,
      'release_gate_event_hash',v_gate_event_hash,
      'release_gate_evidence_sha256',v_evidence_sha
    )
  );

  v_gate_result:=integration_control.penta_assignment_bind_release_gate_v1(
    a.assignment_id,'PENTASECURITY','PASS','penta.security',a.exact_head_sha,a.exact_artifact_sha256,
    'penta-security-assignment-review:'||a.assignment_id::text,v_evidence_sha,
    v_gate_event_id,v_gate_event_hash,null,
    jsonb_build_object(
      'adapter_contract','ct.penta.security.assignment-exact-subject-review.v1',
      'owner_result_evidence_sha256',v_owner_result->>'evidence_sha256',
      'source_reviews',v_reviews,
      'authority_created',false
    )
  );

  return jsonb_build_object(
    'state','PASS','assignment_id',a.assignment_id,
    'exact_head_sha',a.exact_head_sha,'subject_sha256',a.exact_artifact_sha256,
    'review_count',v_review_count,'pass_count',v_pass_count,
    'source_reviews',v_reviews,
    'owner_result',v_owner_result,'release_gate',v_gate_result,
    'security_decision',true,'chlom_rights_decision',false,'cie_decision',false,
    'independent_certification',false,'release_authorized',false,'authority_created',false
  );
end
$fn$;

revoke all on function penta_security.review_assignment_exact_subject_v1(uuid) from public,anon,authenticated;
grant execute on function penta_security.review_assignment_exact_subject_v1(uuid) to service_role;

-- Migration-time structural readback only. Semantic PASS remains runtime/evidence dependent.
do $verify$
declare
  v_policy_count integer;
  v_def text;
begin
  select count(*) into v_policy_count
  from penta_security.provider_source_policies_v1
  where policy_key in (
    'ct.penta.security.assignment-migration.20260831093500.v1',
    'ct.penta.security.assignment-migration.20260831135000.v1',
    'ct.penta.security.assignment-migration.20260831143500.v1',
    'ct.penta.security.assignment-migration.20260831154500.v1'
  ) and state='active' and authority_effect='none';
  if v_policy_count<>4 then raise exception 'PENTASECURITY_ASSIGNMENT_SOURCE_POLICIES_MISSING'; end if;

  select pg_get_functiondef('penta_security.review_assignment_exact_subject_v1(uuid)'::regprocedure) into v_def;
  if strpos(v_def,'review_github_provider_source_v1')=0
     or strpos(v_def,'MIGRATION_BLOB_SOURCE_MISMATCH')=0
     or strpos(v_def,'SOURCE_REVIEW_BYTES_MISMATCH')=0
     or strpos(v_def,'computed_git_blob_sha1')=0
     or strpos(v_def,'penta_assignment_record_owner_result_v1')=0
     or strpos(v_def,'penta_assignment_bind_release_gate_v1')=0
     or strpos(v_def,'ct.penta.release-gate.receipt.v1')=0 then
    raise exception 'PENTASECURITY_ASSIGNMENT_ADAPTER_CONTRACT_INCOMPLETE';
  end if;
end
$verify$;