-- Append-only rollback for PentaSecurity PR-cleanup exact-source policy extension v2.
-- Policy history is never deleted or updated. Rollback appends retired successor versions,
-- causing the exact-source reviewer to fail closed with HOLD_POLICY_NOT_ACTIVE.

DO $preflight$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count
  FROM penta_security.provider_source_policies_v1
  WHERE policy_version='1.0.0'
    AND policy_key IN (
      'ct.penta.security.policy.penta-pr-stale-sequence-v2.v1',
      'ct.penta.security.policy.penta-pr-repo-identity-citext-v2.v1',
      'ct.penta.security.policy.pentarelease-intelligence-idempotency-v4.v1',
      'ct.penta.security.policy.penta-pr-terminal-provider-schema-v4.v1'
    );
  IF v_count <> 4 THEN
    RAISE EXCEPTION 'PENTASECURITY_PR_CLEANUP_SOURCE_POLICY_PACK_V2_NOT_FOUND:%',v_count;
  END IF;
END
$preflight$;

INSERT INTO penta_security.provider_source_policies_v1(
  policy_key, policy_version, provider_system, resource_type, resource_id,
  repository, source_path, required_literals, forbidden_literals,
  max_source_bytes, state, supersedes_policy_version, authority_effect
)
SELECT
  policy_key,'1.0.1',provider_system,resource_type,resource_id,
  repository,source_path,required_literals,forbidden_literals,
  max_source_bytes,'retired','1.0.0','none'
FROM penta_security.provider_source_policies_v1
WHERE policy_version='1.0.0'
  AND policy_key IN (
    'ct.penta.security.policy.penta-pr-stale-sequence-v2.v1',
    'ct.penta.security.policy.penta-pr-repo-identity-citext-v2.v1',
    'ct.penta.security.policy.pentarelease-intelligence-idempotency-v4.v1',
    'ct.penta.security.policy.penta-pr-terminal-provider-schema-v4.v1'
  )
ON CONFLICT(policy_key,policy_version) DO NOTHING;

DO $readback$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count
  FROM (
    SELECT DISTINCT ON (policy_key) policy_key,state,supersedes_policy_version
    FROM penta_security.provider_source_policies_v1
    WHERE policy_key IN (
      'ct.penta.security.policy.penta-pr-stale-sequence-v2.v1',
      'ct.penta.security.policy.penta-pr-repo-identity-citext-v2.v1',
      'ct.penta.security.policy.pentarelease-intelligence-idempotency-v4.v1',
      'ct.penta.security.policy.penta-pr-terminal-provider-schema-v4.v1'
    )
    ORDER BY policy_key,created_at DESC,policy_version DESC
  ) latest
  WHERE state='retired' AND supersedes_policy_version='1.0.0';

  IF v_count <> 4 THEN
    RAISE EXCEPTION 'PENTASECURITY_PR_CLEANUP_SOURCE_POLICY_PACK_V2_RETIREMENT_READBACK_FAILED:%',v_count;
  END IF;
END
$readback$;
