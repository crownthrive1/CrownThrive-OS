-- Applied to production as migration 20260826231217.
-- Records the certified canary and promotes penta.context to PRODUCTION.
do $$
declare
  v_evidence jsonb;
  v_sha text;
begin
  v_evidence := jsonb_build_object(
    'system_key','penta.context',
    'canonical_name','PentaContext',
    'version','1.0.0',
    'promotion','PRODUCTION',
    'database_migrations',jsonb_build_array(
      '20260826230616:penta_context_production_v1',
      '20260826230754:penta_context_explicit_deny_policies_v1',
      '20260826230923:penta_context_fk_indexes_v1',
      '20260826231038:penta_context_source_fk_index_v1'
    ),
    'canary',jsonb_build_object(
      'scope_key','penta.context.canary',
      'context_id','7d37abb3-432a-4327-bcaf-c85e964bcc6a',
      'source_id','8f0d37ec-94e3-46fc-9452-fe0e580b17ca',
      'fingerprint_sha256','154c3d624efd50111bffc28942470701eb365de09dc8836e270553cad193cf89',
      'query_output_sha256','394e647764856cff66d9a11e7ac7312bcf88836250dccc17bd4f9a54dc6fbd31',
      'ingest_pass',true,
      'idempotent_dedupe_pass',true,
      'content_redaction_pass',true,
      'metadata_redaction_pass',true,
      'retrieval_pass',true,
      'wrong_scope_record_count',0,
      'public_ceiling_record_count',0,
      'append_only_receipt_guard_pass',true
    ),
    'access_control',jsonb_build_object(
      'rls_enabled',true,
      'explicit_client_deny_policies',true,
      'anon_table_select',false,
      'authenticated_table_select',false,
      'anon_rpc_execute',false,
      'authenticated_rpc_execute',false,
      'service_role_only',true
    ),
    'performance',jsonb_build_object(
      'all_context_foreign_keys_indexed',true,
      'fts_gin',true,
      'tags_gin',true,
      'scope_time_indexes',true
    ),
    'automation',jsonb_build_object(
      'workflow_id','penta.context.maintenance',
      'cron_job','penta-context-maintenance-v1',
      'schedule','*/15 * * * *',
      'cron_active',true,
      'expiry_tombstone_automated',true
    ),
    'edge',jsonb_build_object(
      'slug','penta-context',
      'deployment_id','e111f3eb-a3c7-488e-92b9-f55d3e63bbce',
      'version',1,
      'status','ACTIVE',
      'artifact_sha256','aad10bddf1dec0e00072b6bcfe90f111f1dae4d63af0ae8065974546ddb90585',
      'custom_service_role_auth',true,
      'allowed_actions',jsonb_build_array('health','query','ingest')
    ),
    'authority',jsonb_build_object(
      'ceiling','D2',
      'context_is_authority',false,
      'authority_created',false,
      'provider_write',false,
      'money_movement',false,
      'd3_effect',false
    ),
    'security_advisor',jsonb_build_object(
      'penta_context_rls_no_policy_findings_after_hardening',0,
      'project_wide_unrelated_advisor_findings_may_remain',true
    ),
    'observed_at',now()
  );
  v_sha := encode(extensions.digest(v_evidence::text,'sha256'),'hex');

  insert into public.penta_system_production_receipts_v1(
    system_key,system_version,canary_key,runtime_ref,passed,evidence,evidence_sha256,
    authority_ceiling,provider_write,money_movement,d3_effect
  ) values (
    'penta.context','1.0.0','penta-context-v1-canary-20260826',
    'edge:penta-context@1;rpc:public.penta_context_query_v1',true,v_evidence,v_sha,
    'D2',false,false,false
  )
  on conflict (system_key,system_version,canary_key) do update
    set runtime_ref=excluded.runtime_ref,passed=excluded.passed,evidence=excluded.evidence,
        evidence_sha256=excluded.evidence_sha256,authority_ceiling=excluded.authority_ceiling,
        provider_write=excluded.provider_write,money_movement=excluded.money_movement,
        d3_effect=excluded.d3_effect,observed_at=now();

  update public.penta_system_registry
  set maturity='production',
      runtime_ref='edge:penta-context@1;rpc:public.penta_context_query_v1',
      last_verified_at=now(),
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'production_canary_pending',false,
        'operational_state','PRODUCTION',
        'automated',true,
        'edge_function','penta-context',
        'edge_version',1,
        'edge_artifact_sha256','aad10bddf1dec0e00072b6bcfe90f111f1dae4d63af0ae8065974546ddb90585',
        'production_receipt_sha256',v_sha,
        'production_promoted_at',now(),
        'source_control_sync_pending',true
      ),
      updated_at=now()
  where system_key='penta.context';

  update public.penta_context_records_v1
  set expires_at=greatest(coalesce(expires_at,now()),now()+interval '7 days'),
      provenance=provenance||jsonb_build_object('synthetic_canary',true,'auto_expire',true)
  where context_id='7d37abb3-432a-4327-bcaf-c85e964bcc6a'::uuid;
end $$;
