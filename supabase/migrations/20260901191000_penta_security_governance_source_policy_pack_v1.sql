-- CrownThrive PentaSecurity governance-source policy pack v1.
--
-- Extends the production exact-source reviewer with append-only policies for two existing
-- governance/security repair lanes: #2020 certification-order v2 and #1894 PentaAssure
-- independent-certifier integrity v2. This changes policy data only. It does not rewrite
-- reviewer code, certify either PR, merge/deploy provider code, create provider-write,
-- credential, money, rights, D3, vote/quorum authority, or expand PentaSecurity authority.

DO $preflight$
BEGIN
  IF to_regprocedure('penta_security.review_github_provider_source_v1(text,text)') IS NULL THEN
    RAISE EXCEPTION 'PENTASECURITY_PROVIDER_SOURCE_REVIEW_RUNTIME_REQUIRED';
  END IF;
  IF to_regclass('penta_security.provider_source_policies_v1') IS NULL THEN
    RAISE EXCEPTION 'PENTASECURITY_PROVIDER_SOURCE_POLICY_REGISTRY_REQUIRED';
  END IF;
END
$preflight$;

INSERT INTO penta_security.provider_source_policies_v1(
  policy_key, policy_version, provider_system, resource_type, resource_id,
  repository, source_path, required_literals, forbidden_literals,
  max_source_bytes, state, supersedes_policy_version, authority_effect
)
VALUES (
  'ct.penta.security.policy.institutional-pre-release-certification-v2.v1',
  '1.0.0',
  'github',
  'sql_migration_source',
  'penta-institutional-pre-release-certification-v2',
  'crownthrive1/CrownThrive-OS',
  'supabase/migrations/20260831074800_penta_institutional_pre_release_certification_v2.sql',
  ARRAY[
    'create or replace ' || 'function integration_control.penta_change_precert_status_v2',
    'Production readback is intentionally NOT a pre-certification predicate.',
    'create or replace ' || 'function integration_control.penta_change_postrelease_status_v2',
    'create or replace ' || 'function integration_control.penta_change_issue_certification_v2',
    'if p_certifier=c.originator_system_key then raise exception ''ORIGINATOR_CANNOT_CERTIFY''; end if;',
    'if p_subject_sha256 <> c.source_sha256 then raise exception ''SUBJECT_DIGEST_MISMATCH''; end if;',
    '''independence_state'',''separation_of_duties_satisfied''',
    'revoke all on function integration_control.penta_change_issue_certification_v2(uuid,text,text,text,text,timestamptz,jsonb) from public, anon, authenticated;',
    'grant execute on function integration_control.penta_change_issue_certification_v2(uuid,text,text,text,text,timestamptz,jsonb) to service_role;'
  ]::text[],
  ARRAY[
    'v_pre:=integration_control.penta_change_precert_status_v1',
    'grant execute on function integration_control.penta_change_issue_certification_v2(uuid,text,text,text,text,timestamptz,jsonb) to anon',
    'grant execute on function integration_control.penta_change_issue_certification_v2(uuid,text,text,text,text,timestamptz,jsonb) to authenticated',
    '''authority_expansion'',true'
  ]::text[],
  200000,
  'active',
  NULL,
  'none'
),(
  'ct.penta.security.policy.penta-assure-independent-certifier-integrity-v2.v1',
  '1.0.0',
  'github',
  'sql_migration_source',
  'penta-assure-independent-certifier-integrity-v2',
  'crownthrive1/CrownThrive-OS',
  'supabase/migrations/20260830194000_penta_assure_independent_certifier_integrity_v2.sql',
  ARRAY[
    'create or replace ' || 'function public.penta_assure_certify_v1(',
    'v_certifier := nullif(btrim(coalesce(p_metadata->>''certifier_id'','''')), '''');',
    'v_originator := nullif(btrim(coalesce(p_metadata->>''originator_id'','''')), '''');',
    'v_reason := ''self_certification_detected'';',
    'v_reason := ''certifier_is_builder'';',
    'v_reason := ''certifier_is_producer'';',
    'v_reason := ''d3_human_reserved'';',
    '''independence_contract_version'', ''2.0.0''',
    'revoke all on function public.penta_assure_certify_v1',
    'from public, anon, authenticated;',
    'grant execute on function public.penta_assure_certify_v1',
    'to service_role;'
  ]::text[],
  ARRAY[
    'grant execute on function public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb) to anon',
    'grant execute on function public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb) to authenticated',
    'grant execute on function public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb) to public',
    '''authority_expansion'', true',
    'if p_risk_class = ''D3'' then v_disp := ''certified'''
  ]::text[],
  120000,
  'active',
  NULL,
  'none'
)
ON CONFLICT(policy_key,policy_version) DO NOTHING;

DO $readback$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count
  FROM penta_security.provider_source_policies_v1
  WHERE policy_version='1.0.0'
    AND state='active'
    AND authority_effect='none'
    AND (
      (policy_key='ct.penta.security.policy.institutional-pre-release-certification-v2.v1'
       AND source_path='supabase/migrations/20260831074800_penta_institutional_pre_release_certification_v2.sql'
       AND cardinality(required_literals)=9 AND cardinality(forbidden_literals)=4)
      OR
      (policy_key='ct.penta.security.policy.penta-assure-independent-certifier-integrity-v2.v1'
       AND source_path='supabase/migrations/20260830194000_penta_assure_independent_certifier_integrity_v2.sql'
       AND cardinality(required_literals)=12 AND cardinality(forbidden_literals)=5)
    );

  IF v_count <> 2 THEN
    RAISE EXCEPTION 'PENTASECURITY_GOVERNANCE_SOURCE_POLICY_PACK_READBACK_FAILED:%',v_count;
  END IF;
END
$readback$;
