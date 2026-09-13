-- Fail-closed rollback for ct.cie.cos-release-candidate-final-disposition.v1.
-- Historical CIE disposition receipts and DAIL evidence remain append-only.

create or replace function chlom_runtime.review_cos_release_candidate_cie_final_disposition_v1(p_candidate_id text)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  return jsonb_build_object(
    'contract','ct.cie.cos-release-candidate-final-disposition.v1',
    'candidate_id',p_candidate_id,
    'final_disposition','HOLD_REVIEW_RUNTIME_ROLLED_BACK_FAIL_CLOSED',
    'activation_authorized',false,
    'operational_activation',false,
    'provider_write_effect',false,
    'economic_effect',false,
    'rights_effect',false,
    'vote_effect',false,
    'd3_auto',false,
    'founder_request_reused',false,
    'source_reauthorization_performed',false,
    'independent_certification',false,
    'release_decision',false,
    'historical_receipts_preserved',true,
    'observed_at',clock_timestamp()
  );
end;
$$;

revoke all on function chlom_runtime.review_cos_release_candidate_cie_final_disposition_v1(text) from public, anon, authenticated;
grant execute on function chlom_runtime.review_cos_release_candidate_cie_final_disposition_v1(text) to service_role;
