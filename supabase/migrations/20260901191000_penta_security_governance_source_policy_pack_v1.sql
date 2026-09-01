-- CrownThrive PentaSecurity governance-source policy pack v1.
--
-- Adds one append-only exact-source review policy for the existing #2020 institutional
-- pre-release/post-release certification-order repair. This extends review coverage only;
-- it does not change reviewer code, certify #2020, merge/deploy anything, create provider
-- write/credential/money/rights/D3/vote/quorum authority, or expand PentaSecurity authority.

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
    'create or replace function integration_control.penta_change_precert_status_v2',
    'Production readback is intentionally NOT a pre-certification predicate.',
    'create or replace function integration_control.penta_change_postrelease_status_v2',
    'create or replace function integration_control.penta_change_issue_certification_v2',
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
    'authority_expansion'':true'
  ]::text[],
  200000,
  'active',
  NULL,
  'none'
)
ON CONFLICT(policy_key,policy_version) DO NOTHING;

DO $readback$
DECLARE
  v_policy penta_security.provider_source_policies_v1%ROWTYPE;
BEGIN
  SELECT * INTO v_policy
  FROM penta_security.provider_source_policies_v1
  WHERE policy_key='ct.penta.security.policy.institutional-pre-release-certification-v2.v1'
    AND policy_version='1.0.0';

  IF NOT FOUND THEN
    RAISE EXCEPTION 'PENTASECURITY_GOVERNANCE_SOURCE_POLICY_READBACK_MISSING';
  END IF;
  IF v_policy.state <> 'active' OR v_policy.authority_effect <> 'none' THEN
    RAISE EXCEPTION 'PENTASECURITY_GOVERNANCE_SOURCE_POLICY_STATE_INVALID';
  END IF;
  IF v_policy.repository <> 'crownthrive1/CrownThrive-OS'
     OR v_policy.source_path <> 'supabase/migrations/20260831074800_penta_institutional_pre_release_certification_v2.sql' THEN
    RAISE EXCEPTION 'PENTASECURITY_GOVERNANCE_SOURCE_POLICY_TARGET_DRIFT';
  END IF;
  IF cardinality(v_policy.required_literals) <> 9 OR cardinality(v_policy.forbidden_literals) <> 4 THEN
    RAISE EXCEPTION 'PENTASECURITY_GOVERNANCE_SOURCE_POLICY_CONTROL_COUNT_DRIFT';
  END IF;
END
$readback$;
