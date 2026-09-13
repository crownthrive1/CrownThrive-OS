-- Fail-closed rollback for ct.penta.security.cos-release-candidate-review.v1
-- Historical review receipts/DAIL evidence are preserved append-only.

create or replace function penta_security.review_cos_release_candidate_v1(p_candidate_id text)
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
    'contract','ct.penta.security.cos-release-candidate-review.v1',
    'candidate_id',p_candidate_id,
    'disposition','HOLD_REVIEW_RUNTIME_ROLLED_BACK_FAIL_CLOSED',
    'security_decision',false,
    'independent_certification',false,
    'release_decision',false,
    'provider_write',false,
    'credential_change',false,
    'money_movement',false,
    'rights_disposition',false,
    'd3_execution',false,
    'authority_expansion',false,
    'historical_receipts_preserved',true,
    'observed_at',clock_timestamp()
  );
end;
$$;

revoke all on function penta_security.review_cos_release_candidate_v1(text) from public, anon, authenticated;
grant execute on function penta_security.review_cos_release_candidate_v1(text) to service_role;
