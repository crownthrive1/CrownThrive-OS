-- Fail-closed rollback for ct.chlom.cos-release-candidate-authority-rights-review.v1.
-- Historical CHLOM receipts/DAIL evidence remain append-only.

create or replace function chlom_runtime.review_cos_release_candidate_authority_rights_v1(p_candidate_id text)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;
  return jsonb_build_object(
    'contract','ct.chlom.cos-release-candidate-authority-rights-review.v1',
    'candidate_id',p_candidate_id,
    'disposition','HOLD_REVIEW_RUNTIME_ROLLED_BACK_FAIL_CLOSED',
    'authority_rights_disposition','NO_CURRENT_TECHNICAL_DISPOSITION_AFTER_ROLLBACK',
    'legal_rights_conclusion',false,
    'third_party_rights_validated',false,
    'new_rights_granted',false,
    'existing_rights_modified',false,
    'release_authority_created',false,
    'certification_created',false,
    'independent_certification',false,
    'd3_execution',false,
    'authority_expansion',false,
    'historical_receipts_preserved',true,
    'observed_at',clock_timestamp()
  );
end;
$$;

revoke all on function chlom_runtime.review_cos_release_candidate_authority_rights_v1(text) from public, anon, authenticated;
grant execute on function chlom_runtime.review_cos_release_candidate_authority_rights_v1(text) to service_role;
