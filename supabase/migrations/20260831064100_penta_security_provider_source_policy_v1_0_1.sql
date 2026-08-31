-- Append-only policy correction for ct.penta.security.provider-source-review.v1.
-- v1.0.0 correctly failed closed during transactional canary because its
-- forbidden literal matched the candidate's explanatory comment describing the
-- historic public-schema defect. v1.0.1 narrows the forbidden patterns to the
-- executable default-schema call shapes while retaining predecessor evidence.

insert into penta_security.provider_source_policies_v1(
  policy_key,policy_version,provider_system,resource_type,resource_id,repository,source_path,
  required_literals,forbidden_literals,max_source_bytes,state,supersedes_policy_version
) values (
  'ct.penta.security.policy.institutional-pr-terminal-provider.v1',
  '1.0.1',
  'supabase',
  'edge_function_source',
  'penta-institutional-pr-terminal-provider',
  'crownthrive1/CrownThrive-OS',
  'supabase/functions/penta-institutional-pr-terminal-provider/index.ts',
  array[
    'sb.schema("integration_control")',
    'penta_pr_closeout_claim_v1',
    'penta_pr_closeout_result_v1',
    'ONE_TIME_WAKE_REQUIRED',
    'REPOSITORY_NOT_ALLOWLISTED',
    'crownthrive1/CrownThrive-OS',
    'EXACT_HEAD_MISMATCH',
    'PR_DRAFT',
    'action.expected_head_sha',
    'authority_expansion: false'
  ]::text[],
  array[
    'sb.rpc("penta_pr_closeout_claim_v1"',
    'sb.rpc("penta_pr_closeout_result_v1"'
  ]::text[],
  150000,
  'active',
  '1.0.0'
) on conflict(policy_key,policy_version) do nothing;

do $verify$
declare v_count integer;
begin
  select count(*) into v_count
  from penta_security.provider_source_policies_v1
  where policy_key='ct.penta.security.policy.institutional-pr-terminal-provider.v1'
    and policy_version in ('1.0.0','1.0.1');
  if v_count<>2 then raise exception 'PENTASECURITY_PROVIDER_POLICY_SUPERSESSION_LINEAGE_MISSING'; end if;
end
$verify$;
