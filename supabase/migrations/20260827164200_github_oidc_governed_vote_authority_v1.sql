-- Exact GitHub Actions OIDC governance authority for the first PentaFactory production release.
-- This migration never manufactures a vote: the Edge verifier must cryptographically validate
-- GitHub's RS256 token before invoking the service-role-only recorder.

update institutional_federation.repository_registry
set repo_full_name='crownthrive1/CrownThrive-OS',
    metadata=metadata||jsonb_build_object(
      'legacy_repo_full_name',repo_full_name,
      'repository_renamed_at','2026-08-27T16:22:02Z',
      'repository_rename_source','github-repository-id:1336348391',
      'canonical_repository_id',1336348391,
      'canonical_repository_owner_id',315660018,
      'canonical_repository_full_name','crownthrive1/CrownThrive-OS',
      'governed_oidc_vote_workflow','.github/workflows/penta-governed-release-vote-oidc.yml'
    ),
    updated_at=now()
where repo_id='ct.repo.crownthrive-support'
  and github_repository_id=1336348391;

create or replace function integration_control.record_github_oidc_governed_vote_v1(
  p_release_id uuid,
  p_voter_agent_id text,
  p_exact_version_ref text,
  p_content_sha256 text,
  p_oidc_issuer text,
  p_oidc_audience text,
  p_github_repository_id bigint,
  p_github_repository_full_name text,
  p_github_repository_owner text,
  p_github_repository_owner_id bigint,
  p_github_ref text,
  p_github_workflow_ref text,
  p_github_workflow_sha text,
  p_github_run_id text,
  p_github_run_attempt text,
  p_github_event_name text,
  p_oidc_jti text,
  p_oidc_subject text,
  p_actor text,
  p_actor_id text,
  p_token_sha256 text,
  p_receipt_digest text,
  p_verified_at timestamptz,
  p_expires_at timestamptz,
  p_claims jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control','institutional_federation','extensions'
as $$
declare
  v_release integration_control.governed_releases%rowtype;
  v_repo institutional_federation.repository_registry%rowtype;
  v_candidate_id uuid;
  v_candidate_status jsonb;
  v_message_id uuid;
  v_receipt_id uuid;
  v_vote_id uuid;
  v_existing_vote integration_control.governed_release_votes%rowtype;
  v_recompute jsonb;
  v_dispatch jsonb;
  v_job jsonb;
  v_yes integer:=0;
  v_no integer:=0;
  v_agent_d_yes boolean:=false;
  v_now timestamptz:=clock_timestamp();
begin
  if p_oidc_issuer<>'https://token.actions.githubusercontent.com' then
    raise exception 'github_oidc_issuer_invalid' using errcode='28000';
  end if;
  if p_github_repository_id<>1336348391
     or p_github_repository_full_name<>'crownthrive1/CrownThrive-OS'
     or p_github_repository_owner<>'crownthrive1'
     or p_github_repository_owner_id<>315660018 then
    raise exception 'github_oidc_repository_identity_invalid' using errcode='28000';
  end if;
  if p_github_ref<>'refs/heads/main' then
    raise exception 'github_oidc_ref_invalid' using errcode='28000';
  end if;
  if p_github_workflow_ref<>'crownthrive1/CrownThrive-OS/.github/workflows/penta-governed-release-vote-oidc.yml@refs/heads/main' then
    raise exception 'github_oidc_workflow_ref_invalid' using errcode='28000';
  end if;
  if p_github_event_name<>'repository_dispatch' then
    raise exception 'github_oidc_event_invalid' using errcode='28000';
  end if;
  if p_github_run_id !~ '^[0-9]+$' or p_github_run_attempt !~ '^[0-9]+$' then
    raise exception 'github_oidc_run_identity_invalid' using errcode='28000';
  end if;
  if p_token_sha256 !~ '^[0-9a-f]{64}$' or p_receipt_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'github_oidc_digest_invalid' using errcode='22023';
  end if;
  if p_verified_at>v_now+interval '30 seconds'
     or p_verified_at<v_now-interval '10 minutes'
     or p_expires_at<=v_now
     or p_expires_at>v_now+interval '20 minutes' then
    raise exception 'github_oidc_time_window_invalid' using errcode='28000';
  end if;

  select * into strict v_release
  from integration_control.governed_releases
  where release_id=p_release_id
  for update;

  if v_release.exact_version_ref is distinct from p_exact_version_ref
     or v_release.content_sha256 is distinct from p_content_sha256 then
    raise exception 'github_oidc_vote_exact_snapshot_mismatch' using errcode='23514';
  end if;
  if v_release.certification_state<>'pass' then
    raise exception 'github_oidc_vote_release_not_certified' using errcode='23514';
  end if;
  if p_voter_agent_id=v_release.originating_agent_id then
    raise exception 'github_oidc_originator_cannot_vote' using errcode='23514';
  end if;

  select * into strict v_repo
  from institutional_federation.repository_registry
  where repo_id='ct.repo.crownthrive-support'
    and github_repository_id=p_github_repository_id
    and repo_full_name=p_github_repository_full_name
    and operationally_enabled=true
    and can_vote=true;

  if p_oidc_audience is distinct from v_repo.oidc_audience then
    raise exception 'github_oidc_audience_invalid' using errcode='28000';
  end if;

  if not exists(
    select 1 from institutional_federation.repository_agent_bindings b
    where b.repo_id=v_repo.repo_id
      and b.agent_id=p_voter_agent_id
      and b.vote_eligible=true
      and b.binding_state='active'
      and b.authority_ceiling in ('D0','D1','D2')
  ) then
    raise exception 'github_oidc_voter_binding_invalid' using errcode='42501';
  end if;

  select m.message_id into v_message_id
  from institutional_federation.repository_messages m
  where m.correlation_id=p_release_id
    and m.message_type='governed_release_vote_request'
    and m.receiver_repo_id=v_repo.repo_id
    and m.payload->>'voter_agent_id'=p_voter_agent_id
    and m.payload->>'release_id'=p_release_id::text
    and m.payload->>'exact_version_ref'=p_exact_version_ref
    and m.payload->>'content_sha256'=p_content_sha256
    and coalesce((m.payload->>'self_approval_prohibited')::boolean,false)=true
    and (m.expires_at is null or m.expires_at>v_now)
  order by m.created_at desc
  limit 1;
  if v_message_id is null then
    raise exception 'github_oidc_vote_request_missing_or_expired' using errcode='23514';
  end if;

  select c.candidate_id into v_candidate_id
  from integration_control.thriveevergreen_publisher_candidates_v2 c
  where c.release_id=p_release_id
    and c.exact_version_ref=p_exact_version_ref
    and c.content_sha256=p_content_sha256
  order by c.updated_at desc
  limit 1;
  if v_candidate_id is null then
    raise exception 'github_oidc_exact_candidate_missing' using errcode='23514';
  end if;

  v_candidate_status:=integration_control.pentafactory_exact_candidate_status_v1(v_candidate_id);
  if coalesce((v_candidate_status->>'genuine_pass')::boolean,false) is not true
     or coalesce((v_candidate_status->>'evidence_pass')::boolean,false) is not true
     or v_candidate_status#>>'{route,verified}'<>'true'
     or (v_candidate_status#>>'{certification,independent_pass}')::integer<>(v_candidate_status#>>'{certification,required}')::integer
     or (v_candidate_status#>>'{health,pass}')::integer<>(v_candidate_status#>>'{health,required}')::integer then
    raise exception 'github_oidc_exact_candidate_not_genuine_pass' using errcode='23514';
  end if;

  select a.receipt_id into v_receipt_id
  from integration_control.governed_vote_authority_receipts a
  where a.receipt_digest=p_receipt_digest;

  if v_receipt_id is null then
    v_receipt_id:=gen_random_uuid();
    insert into integration_control.governed_vote_authority_receipts(
      receipt_id,release_id,voter_repo_id,voter_agent_id,exact_version_ref,content_sha256,
      authority_provider,oidc_issuer,oidc_audience,github_repository_id,github_ref,
      github_workflow_ref,github_run_id,github_run_attempt,receipt_digest,receipt_state,
      verified_at,expires_at,metadata
    ) values(
      v_receipt_id,p_release_id,v_repo.repo_id,p_voter_agent_id,p_exact_version_ref,p_content_sha256,
      'github_actions_oidc',p_oidc_issuer,p_oidc_audience,p_github_repository_id,p_github_ref,
      p_github_workflow_ref,p_github_run_id,p_github_run_attempt,p_receipt_digest,'verified',
      p_verified_at,p_expires_at,
      jsonb_build_object(
        'repository',p_github_repository_full_name,
        'repository_owner',p_github_repository_owner,
        'repository_owner_id',p_github_repository_owner_id,
        'workflow_sha',p_github_workflow_sha,
        'event_name',p_github_event_name,
        'oidc_jti',p_oidc_jti,
        'oidc_subject',p_oidc_subject,
        'actor',p_actor,
        'actor_id',p_actor_id,
        'token_sha256',p_token_sha256,
        'message_id',v_message_id,
        'candidate_id',v_candidate_id,
        'candidate_status_sha256',encode(extensions.digest(v_candidate_status::text,'sha256'),'hex'),
        'jwt_signature_verified',true,
        'jwks_issuer_verified',true,
        'synthetic',false,
        'test_only',false,
        'not_sovereign_approval',false,
        'raw_token_persisted',false,
        'claims',coalesce(p_claims,'{}'::jsonb)
      )
    );
  end if;

  select * into v_existing_vote
  from integration_control.governed_release_votes
  where release_id=p_release_id and voter_agent_id=p_voter_agent_id;

  if v_existing_vote.vote_id is null then
    insert into integration_control.governed_release_votes(
      release_id,voter_repo_id,voter_agent_id,vote,exact_version_ref,content_sha256,
      evidence_ref,metadata,authority_receipt_id
    ) values(
      p_release_id,v_repo.repo_id,p_voter_agent_id,'yes',p_exact_version_ref,p_content_sha256,
      'github-actions-oidc:'||p_github_run_id||':'||p_github_run_attempt||':'||p_oidc_jti,
      jsonb_build_object(
        'authority_provider','github_actions_oidc',
        'workflow_ref',p_github_workflow_ref,
        'workflow_sha',p_github_workflow_sha,
        'repository_id',p_github_repository_id,
        'repository',p_github_repository_full_name,
        'message_id',v_message_id,
        'candidate_id',v_candidate_id,
        'genuine_pass_verified',true,
        'independent_certifications_verified',true,
        'provider_health_verified',true,
        'route_verified',true,
        'synthetic',false,
        'test_only',false,
        'not_sovereign_approval',false,
        'self_approval',false,
        'money_movement',false,
        'checkout_activation',false
      ),
      v_receipt_id
    ) returning vote_id into v_vote_id;
  else
    if v_existing_vote.vote<>'yes'
       or v_existing_vote.exact_version_ref<>p_exact_version_ref
       or v_existing_vote.content_sha256<>p_content_sha256
       or v_existing_vote.authority_receipt_id is null then
      raise exception 'github_oidc_existing_vote_conflict' using errcode='23514';
    end if;
    v_vote_id:=v_existing_vote.vote_id;
  end if;

  v_recompute:=integration_control.recompute_governed_release(p_release_id);
  select count(*) filter(where v.vote='yes'),count(*) filter(where v.vote='no'),
         exists(select 1 from integration_control.governed_release_votes d where d.release_id=p_release_id and d.voter_agent_id='ct.relay.agent-d' and d.vote='yes')
  into v_yes,v_no,v_agent_d_yes
  from integration_control.governed_release_votes v
  where v.release_id=p_release_id;

  select * into v_release from integration_control.governed_releases where release_id=p_release_id;
  if v_release.vote_state='accepted'
     and v_release.certification_state='pass'
     and v_release.release_state in ('accepted','publish_queued') then
    v_dispatch:=integration_control.dispatch_dynamic_feed_publications(25);
  end if;

  select jsonb_build_object(
    'job_id',j.job_id,'state',j.state,'surface_id',j.surface_id,'adapter_id',j.adapter_id,
    'exact_version_ref',j.exact_version_ref,'content_sha256',j.content_sha256,
    'rollback_ref',j.rollback_ref,'public_url',j.public_url,'attempt_count',j.attempt_count,
    'published_at',j.published_at,'updated_at',j.updated_at
  ) into v_job
  from integration_control.site_publish_jobs j
  where j.release_id=p_release_id;

  select * into v_release from integration_control.governed_releases where release_id=p_release_id;
  return jsonb_build_object(
    'authenticated',true,
    'receipt_id',v_receipt_id,
    'receipt_state','verified',
    'vote_id',v_vote_id,
    'vote','yes',
    'voter_agent_id',p_voter_agent_id,
    'yes_votes',v_yes,
    'no_votes',v_no,
    'agent_d_yes',v_agent_d_yes,
    'release',jsonb_build_object(
      'release_id',v_release.release_id,
      'certification_state',v_release.certification_state,
      'vote_state',v_release.vote_state,
      'release_state',v_release.release_state,
      'exact_version_ref',v_release.exact_version_ref,
      'content_sha256',v_release.content_sha256,
      'accepted_at',v_release.accepted_at,
      'published_at',v_release.published_at
    ),
    'candidate_status',v_candidate_status,
    'recompute',v_recompute,
    'dispatch',v_dispatch,
    'publish_job',v_job,
    'raw_token_persisted',false,
    'authority_manufactured',false,
    'self_vote_created',false,
    'money_movement',false,
    'checkout_activation',false
  );
end $$;

revoke all on function integration_control.record_github_oidc_governed_vote_v1(uuid,text,text,text,text,text,bigint,text,text,bigint,text,text,text,text,text,text,text,text,text,text,text,text,timestamptz,timestamptz,jsonb) from public,anon,authenticated;
grant execute on function integration_control.record_github_oidc_governed_vote_v1(uuid,text,text,text,text,text,bigint,text,text,bigint,text,text,text,text,text,text,text,text,text,text,text,text,timestamptz,timestamptz,jsonb) to service_role;

create or replace function integration_control.github_oidc_governed_release_proof_v1(p_release_id uuid)
returns jsonb
language sql
stable
security definer
set search_path='pg_catalog','integration_control'
as $$
  select jsonb_build_object(
    'release',jsonb_build_object(
      'release_id',r.release_id,'subject_ref',r.subject_ref,'exact_version_ref',r.exact_version_ref,
      'content_sha256',r.content_sha256,'certification_state',r.certification_state,
      'vote_state',r.vote_state,'release_state',r.release_state,'accepted_at',r.accepted_at,'published_at',r.published_at
    ),
    'votes',jsonb_build_object(
      'yes',count(v.*) filter(where v.vote='yes'),
      'no',count(v.*) filter(where v.vote='no'),
      'abstain',count(v.*) filter(where v.vote='abstain'),
      'agent_d_yes',coalesce(bool_or(v.voter_agent_id='ct.relay.agent-d' and v.vote='yes'),false),
      'voters',coalesce(jsonb_agg(jsonb_build_object(
        'voter_agent_id',v.voter_agent_id,'vote',v.vote,'evidence_ref',v.evidence_ref,
        'authority_receipt_id',v.authority_receipt_id,'created_at',v.created_at
      ) order by v.voter_agent_id) filter(where v.vote_id is not null),'[]'::jsonb)
    ),
    'authority_receipts',coalesce((select jsonb_agg(jsonb_build_object(
      'receipt_id',a.receipt_id,'voter_agent_id',a.voter_agent_id,'authority_provider',a.authority_provider,
      'oidc_issuer',a.oidc_issuer,'oidc_audience',a.oidc_audience,
      'github_repository_id',a.github_repository_id,'github_ref',a.github_ref,
      'github_workflow_ref',a.github_workflow_ref,'github_run_id',a.github_run_id,
      'github_run_attempt',a.github_run_attempt,'receipt_digest',a.receipt_digest,
      'receipt_state',a.receipt_state,'verified_at',a.verified_at,'expires_at',a.expires_at,
      'jwt_signature_verified',a.metadata->'jwt_signature_verified','raw_token_persisted',a.metadata->'raw_token_persisted'
    ) order by a.voter_agent_id) from integration_control.governed_vote_authority_receipts a where a.release_id=r.release_id),'[]'::jsonb),
    'publish_job',(select jsonb_build_object(
      'job_id',j.job_id,'state',j.state,'surface_id',j.surface_id,'adapter_id',j.adapter_id,
      'exact_version_ref',j.exact_version_ref,'content_sha256',j.content_sha256,
      'rollback_ref',j.rollback_ref,'public_url',j.public_url,'attempt_count',j.attempt_count,
      'published_at',j.published_at,'updated_at',j.updated_at
    ) from integration_control.site_publish_jobs j where j.release_id=r.release_id),
    'projection',(select jsonb_build_object(
      'surface_id',p.surface_id,'subject_ref',p.subject_ref,'exact_version_ref',p.exact_version_ref,
      'content_sha256',p.content_sha256,'publication_state',p.publication_state,
      'published_at',p.published_at,'updated_at',p.updated_at
    ) from integration_control.site_catalog_projection p where p.release_id=r.release_id),
    'money_movement',false,'checkout_activation',false,'generated_at',now()
  )
  from integration_control.governed_releases r
  left join integration_control.governed_release_votes v on v.release_id=r.release_id
  where r.release_id=p_release_id
  group by r.release_id;
$$;

revoke all on function integration_control.github_oidc_governed_release_proof_v1(uuid) from public,anon,authenticated;
grant execute on function integration_control.github_oidc_governed_release_proof_v1(uuid) to service_role;
