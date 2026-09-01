-- Append-only rollback for PentaSecurity governance-source policy pack v1.
-- Policy history is never deleted or updated. Rollback appends a retired successor version,
-- causing the review runtime to fail closed with HOLD_POLICY_NOT_ACTIVE for this policy key.

DO $preflight$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM penta_security.provider_source_policies_v1
    WHERE policy_key='ct.penta.security.policy.institutional-pre-release-certification-v2.v1'
      AND policy_version='1.0.0'
  ) THEN
    RAISE EXCEPTION 'PENTASECURITY_GOVERNANCE_SOURCE_POLICY_V1_NOT_FOUND';
  END IF;
END
$preflight$;

INSERT INTO penta_security.provider_source_policies_v1(
  policy_key, policy_version, provider_system, resource_type, resource_id,
  repository, source_path, required_literals, forbidden_literals,
  max_source_bytes, state, supersedes_policy_version, authority_effect
)
SELECT
  policy_key,
  '1.0.1',
  provider_system,
  resource_type,
  resource_id,
  repository,
  source_path,
  required_literals,
  forbidden_literals,
  max_source_bytes,
  'retired',
  '1.0.0',
  'none'
FROM penta_security.provider_source_policies_v1
WHERE policy_key='ct.penta.security.policy.institutional-pre-release-certification-v2.v1'
  AND policy_version='1.0.0'
ON CONFLICT(policy_key,policy_version) DO NOTHING;

DO $readback$
DECLARE
  v_state text;
  v_supersedes text;
BEGIN
  SELECT state,supersedes_policy_version INTO v_state,v_supersedes
  FROM penta_security.provider_source_policies_v1
  WHERE policy_key='ct.penta.security.policy.institutional-pre-release-certification-v2.v1'
  ORDER BY created_at DESC,policy_version DESC
  LIMIT 1;

  IF v_state <> 'retired' OR v_supersedes <> '1.0.0' THEN
    RAISE EXCEPTION 'PENTASECURITY_GOVERNANCE_SOURCE_POLICY_RETIREMENT_READBACK_FAILED';
  END IF;
END
$readback$;
