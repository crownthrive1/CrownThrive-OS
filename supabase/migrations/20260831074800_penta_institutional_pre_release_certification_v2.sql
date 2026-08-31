-- CrownThrive institutional change pre-release certification ordering v2
--
-- Purpose: remove the circular requirement that production readback must PASS before
-- independent certification can be issued. Production readback remains mandatory for
-- terminal/institutional completion after governed release.
--
-- This migration is readiness/order control only. It does not issue certification,
-- merge or deploy code, mutate provider state, create credentials, move money, grant
-- rights, create sovereign vote/quorum effect, or expand D3 authority.

create or replace function integration_control.penta_change_precert_status_v2(p_change_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path to 'pg_catalog', 'integration_control', 'penta_help'
as $function$
declare
  c integration_control.penta_change_contracts_v1%rowtype;
  m jsonb := '[]'::jsonb;
begin
  select * into c
  from integration_control.penta_change_contracts_v1
  where change_id = p_change_id;

  if not found then
    return jsonb_build_object(
      'contract','ct.penta.institutional-change.precert.v2',
      'phase','pre_release',
      'ready',false,
      'missing',jsonb_build_array('CHANGE_NOT_FOUND'),
      'post_release_production_readback_required',true
    );
  end if;

  if not c.source_task_completed then
    m := m || '"SOURCE_TASK_COMPLETED"'::jsonb;
  end if;
  if c.source_sha256 !~ '^[0-9a-f]{64}$' then
    m := m || '"SOURCE_DIGEST"'::jsonb;
  end if;
  if c.security_state not in ('pass','not_applicable') then
    m := m || '"SECURITY"'::jsonb;
  end if;
  if c.rollback_state not in ('pass','not_applicable') then
    m := m || '"ROLLBACK"'::jsonb;
  end if;

  -- Production readback is intentionally NOT a pre-certification predicate.
  -- It is a post-release terminal predicate evaluated by penta_change_postrelease_status_v2
  -- and the existing institutional completion/terminalization controls.

  if c.risk_class not in ('D0','D1','D2')
     or c.d3_effect
     or c.money_movement
     or c.credential_effect
     or c.rights_effect
     or c.legal_tax_professional_effect
     or c.final_contract_effect
     or c.sovereign_vote_effect
     or c.authority_expansion then
    m := m || '"RESERVED_EFFECT"'::jsonb;
  end if;

  if not exists (
    select 1 from integration_control.penta_change_receipts_v1
    where change_id=c.change_id and lane='evidence'
  ) then m := m || '"DAIL_EVIDENCE"'::jsonb; end if;

  if not exists (
    select 1 from integration_control.penta_change_receipts_v1
    where change_id=c.change_id and lane='decision'
  ) then m := m || '"DAIL_DECISION"'::jsonb; end if;

  if not exists (
    select 1 from integration_control.penta_change_receipts_v1
    where change_id=c.change_id and lane='execution'
  ) then m := m || '"DAIL_EXECUTION"'::jsonb; end if;

  if (
    select count(distinct projection_kind)
    from integration_control.penta_change_projections_v1
    where change_id=c.change_id and readback_pass
  ) < 4 then
    m := m || '"PROJECTIONS"'::jsonb;
  end if;

  if c.close_mode <> 'leave_open_hold'
     and (c.pr_number is null or nullif(c.base_ref,'') is null or c.exact_head_sha !~ '^[0-9a-f]{40}$') then
    m := m || '"EXACT_PR_HEAD"'::jsonb;
  end if;

  if exists (
    select 1
    from penta_help.requests_v1 r
    where r.state not in ('resolved','retired','expired')
      and r.risk_class in ('D2','D3')
      and r.context->>'change_id'=c.change_id::text
      and r.context->>'stage'<>'certify'
  ) then
    m := m || '"OPEN_DEPENDENCY"'::jsonb;
  end if;

  return jsonb_build_object(
    'contract','ct.penta.institutional-change.precert.v2',
    'phase','pre_release',
    'ready',jsonb_array_length(m)=0,
    'missing',m,
    'change_id',c.change_id,
    'production_readback_state',c.production_readback_state,
    'post_release_production_readback_required',true,
    'certification_issued',false,
    'authority_created',false
  );
end
$function$;

comment on function integration_control.penta_change_precert_status_v2(uuid)
is 'Pre-release readiness only. Production readback is deliberately post-release and remains mandatory for terminal completion. This function issues no certification or authority.';

create or replace function integration_control.penta_change_postrelease_status_v2(p_change_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path to 'pg_catalog', 'integration_control', 'chlom_runtime'
as $function$
declare
  c integration_control.penta_change_contracts_v1%rowtype;
  m jsonb := '[]'::jsonb;
  v_active_cert boolean := false;
  v_projection_count integer := 0;
begin
  select * into c
  from integration_control.penta_change_contracts_v1
  where change_id=p_change_id;

  if not found then
    return jsonb_build_object(
      'contract','ct.penta.institutional-change.postrelease.v2',
      'phase','post_release',
      'ready_for_terminal',false,
      'missing',jsonb_build_array('CHANGE_NOT_FOUND')
    );
  end if;

  select exists(
    select 1
    from integration_control.penta_change_certifications_v1 cert
    where cert.change_id=c.change_id
      and cert.state='active'
      and cert.independence_state='separation_of_duties_satisfied'
      and cert.subject_sha256=c.source_sha256
      and (cert.expires_at is null or cert.expires_at>now())
      and cert.activation_dail_event_id is not null
      and cert.activation_dail_event_hash ~ '^[0-9a-f]{64}$'
  ) into v_active_cert;

  if not v_active_cert then
    m := m || '"ACTIVE_INDEPENDENT_CERTIFICATION"'::jsonb;
  end if;

  if c.production_readback_state <> 'pass' then
    m := m || '"PRODUCTION_READBACK"'::jsonb;
  end if;

  select count(distinct projection_kind)
  into v_projection_count
  from integration_control.penta_change_projections_v1
  where change_id=c.change_id and readback_pass;

  if v_projection_count < 4 then
    m := m || '"PROJECTIONS"'::jsonb;
  end if;

  if not exists (
    select 1 from integration_control.penta_change_receipts_v1
    where change_id=c.change_id and lane='execution'
  ) then
    m := m || '"DAIL_EXECUTION"'::jsonb;
  end if;

  if c.close_mode <> 'leave_open_hold'
     and (c.pr_number is null or nullif(c.base_ref,'') is null or c.exact_head_sha !~ '^[0-9a-f]{40}$') then
    m := m || '"EXACT_PR_HEAD"'::jsonb;
  end if;

  return jsonb_build_object(
    'contract','ct.penta.institutional-change.postrelease.v2',
    'phase','post_release',
    'ready_for_terminal',jsonb_array_length(m)=0,
    'missing',m,
    'change_id',c.change_id,
    'active_independent_certification',v_active_cert,
    'production_readback_state',c.production_readback_state,
    'projection_count',v_projection_count,
    'authority_created',false
  );
end
$function$;

comment on function integration_control.penta_change_postrelease_status_v2(uuid)
is 'Post-release terminal readiness. Requires active independent certification and exact production readback; issues no certification or release authority.';

revoke all on function integration_control.penta_change_precert_status_v2(uuid) from public, anon, authenticated;
revoke all on function integration_control.penta_change_postrelease_status_v2(uuid) from public, anon, authenticated;
grant execute on function integration_control.penta_change_precert_status_v2(uuid) to service_role;
grant execute on function integration_control.penta_change_postrelease_status_v2(uuid) to service_role;
