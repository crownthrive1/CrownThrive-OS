-- CrownThrive PentaSecurity PR-cleanup exact-source policy extension v2.
--
-- Extends the existing provider-source reviewer with bounded read-only source policies for
-- the current PR terminalization cleanup machinery. This migration registers review policy
-- only. It does not execute a review, certify a PR, merge/deploy, mutate provider/customer
-- state, create credentials, move money, grant rights, perform D3/vote/quorum actions, or
-- expand PentaSecurity authority.

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
VALUES
(
  'ct.penta.security.policy.penta-pr-stale-sequence-v2.v1',
  '1.0.0','github','sql_migration_source','penta-pr-stale-sequence-v2',
  'crownthrive1/CrownThrive-OS',
  'supabase/migrations/20260902193000_penta_pr_lifecycle_stale_sequence_fix_v2.sql',
  ARRAY[
    'create or replace ' || 'function public.penta_pr_apply_lifecycle_classification_v2(',
    'v2 sequence invariant: stale classification is allowed before successor creation.',
    'and p_successor_pr_number is not null',
    '''handoff_required_before_terminalization''',
    'create or replace ' || 'function public.penta_pr_record_provider_terminal_readback_v2(',
    '''HOLD_STALE_PREDECESSOR_MUST_CLOSE_NOT_MERGE''',
    '''HOLD_STALE_PREDECESSOR_HANDOFF_REQUIRED''',
    '''authority_created'', false'
  ]::text[],
  ARRAY[
    'stale_predecessor_requires_successor_or_handoff_before_close',
    'grant execute on function public.penta_pr_apply_lifecycle_classification_v2(text,bigint,text,text,text,text,text,bigint,text,text,timestamptz) to anon',
    'grant execute on function public.penta_pr_apply_lifecycle_classification_v2(text,bigint,text,text,text,text,text,bigint,text,text,timestamptz) to authenticated',
    '''authority_created'', true'
  ]::text[],
  120000,'active',NULL,'none'
),
(
  'ct.penta.security.policy.penta-pr-repo-identity-citext-v2.v1',
  '1.0.0','github','sql_migration_source','penta-pr-repo-identity-citext-v2',
  'crownthrive1/CrownThrive-OS',
  'supabase/migrations/20260901210200_penta_pr_repo_identity_citext_v2.sql',
  ARRAY[
    'create extension if not exists citext with schema extensions;',
    'create ' || 'table if not exists penta_pr.lifecycle_identity_alias_archive_v2',
    'revoke all on table penta_pr.lifecycle_identity_alias_archive_v2 from public, anon, authenticated;',
    'penta_pr_active_alias_head_conflict',
    'penta_pr_active_alias_classification_conflict',
    'penta_pr_active_alias_disposition_conflict',
    'alter column repo type extensions.citext',
    'l.repo::text as repo',
    'l.repo = v.repository_full_name::extensions.citext',
    'penta_pr_case_identity_duplicate_remaining'
  ]::text[],
  ARRAY[
    'drop ' || 'table penta_pr.lifecycle',
    'truncate table penta_pr.lifecycle',
    'drop ' || 'view penta_pr.current_zero_delta_candidates_v3 cascade',
    'drop ' || 'view penta_runtime.current_vergence_repairs_v3 cascade',
    'grant select on table penta_pr.lifecycle_identity_alias_archive_v2 to anon',
    'grant select on table penta_pr.lifecycle_identity_alias_archive_v2 to authenticated'
  ]::text[],
  180000,'active',NULL,'none'
),
(
  'ct.penta.security.policy.pentarelease-intelligence-idempotency-v4.v1',
  '1.0.0','github','github_actions_workflow_source','pentarelease-intelligence-idempotency-v4',
  'crownthrive1/CrownThrive-OS',
  '.github/workflows/pentarelease-release-intelligence-v3.yml',
  ARRAY[
    'BASE_SHA=$(git rev-parse HEAD)',
    'CONTENT_SHA=$(git diff --no-ext-diff --binary -- "${TRACKED[@]}" | sha256sum | awk ''{print $1}'')',
    'BRANCH="pentarelease/intelligence-${SAFE_TAG}-${BASE_SHA:0:12}-${CONTENT_SHA:0:12}"',
    '--state all --base main --limit 300',
    '.baseRefOid == $base and .headRefName == $branch',
    'gh pr reopen "$PR_NUM" --repo "$GITHUB_REPOSITORY"',
    'if: steps.candidate.outputs.exists != ''true''',
    'Reusing deterministic exact-base/exact-content release-intelligence subject'
  ]::text[],
  ARRAY[
    '${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}',
    'BRANCH="pentarelease/intelligence-${SAFE_TAG}-${GITHUB_RUN_ID}',
    '--state open --base main --limit 300'
  ]::text[],
  150000,'active',NULL,'none'
),
(
  'ct.penta.security.policy.penta-pr-terminal-provider-schema-v4.v1',
  '1.0.0','github','edge_function_source','penta-pr-terminal-provider-schema-v4',
  'crownthrive1/CrownThrive-OS',
  'supabase/functions/penta-institutional-pr-terminal-provider/index.ts',
  ARRAY[
    'const institutional = sb.schema("integration_control");',
    'institutional.rpc("penta_pr_closeout_claim_v1"',
    'institutional.rpc("penta_pr_closeout_result_v1"',
    'ONE_TIME_WAKE_REQUIRED',
    'REPOSITORY_NOT_ALLOWLISTED',
    'MISSING_GITHUB_PROVIDER_CREDENTIAL',
    'EXACT_HEAD_MISMATCH',
    'PR_DRAFT',
    'provider_write: false',
    'authority_expansion: false'
  ]::text[],
  ARRAY[
    'sb.rpc("penta_pr_closeout_claim_v1"',
    'sb.rpc("penta_pr_closeout_result_v1"',
    'action.repository !== input.repository',
    'credential_exposed: true'
  ]::text[],
  120000,'active',NULL,'none'
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
      (policy_key='ct.penta.security.policy.penta-pr-stale-sequence-v2.v1'
       AND cardinality(required_literals)=8 AND cardinality(forbidden_literals)=4)
      OR
      (policy_key='ct.penta.security.policy.penta-pr-repo-identity-citext-v2.v1'
       AND cardinality(required_literals)=10 AND cardinality(forbidden_literals)=6)
      OR
      (policy_key='ct.penta.security.policy.pentarelease-intelligence-idempotency-v4.v1'
       AND cardinality(required_literals)=8 AND cardinality(forbidden_literals)=3)
      OR
      (policy_key='ct.penta.security.policy.penta-pr-terminal-provider-schema-v4.v1'
       AND cardinality(required_literals)=10 AND cardinality(forbidden_literals)=4)
    );

  IF v_count <> 4 THEN
    RAISE EXCEPTION 'PENTASECURITY_PR_CLEANUP_SOURCE_POLICY_PACK_V2_READBACK_FAILED:%',v_count;
  END IF;
END
$readback$;
