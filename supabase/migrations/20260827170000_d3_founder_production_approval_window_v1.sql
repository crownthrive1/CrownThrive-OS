-- D3 Founder Production Approval Window v1
--
-- Prospectively binds the Founder-human approval predicate for exact D3
-- production candidates to the existing nonrenewing fourteen-day campaign.
-- This migration does not convert the campaign HOLD into PASS and does not
-- create technical, verifier, provider, financial, rights, credential, legal,
-- privacy, destructive, or release authority.

create table if not exists penta_runtime.d3_founder_approval_windows_v1 (
  window_id text primary key,
  directive_id text not null unique
    references developer_commerce.founder_directives(directive_id) on delete restrict,
  campaign_id text not null
    references penta_runtime.d3_campaign_bindings_v1(campaign_id) on delete restrict,
  founder_ref text not null,
  starts_at timestamptz not null,
  expires_at timestamptz not null,
  risk_class text not null default 'D3',
  approval_effect text not null default 'human_approval_predicate_only',
  eligible_action_classes text[] not null,
  required_release_dimensions text[] not null,
  separate_authority_requirements text[] not null,
  production_only boolean not null default true,
  exact_candidate_required boolean not null default true,
  independent_evidence_required boolean not null default true,
  independent_evidence_substitution_allowed boolean not null default false,
  nonrenewing boolean not null default true,
  created_at timestamptz not null default clock_timestamp(),
  check (window_id ~ '^ct[.]d3[.]founder-production-window[.][0-9]{8}[.]v[0-9]+$'),
  check (expires_at = starts_at + interval '14 days'),
  check (risk_class = 'D3'),
  check (approval_effect = 'human_approval_predicate_only'),
  check (cardinality(eligible_action_classes) > 0 and array_position(eligible_action_classes, null) is null),
  check (cardinality(required_release_dimensions) > 0 and array_position(required_release_dimensions, null) is null),
  check (cardinality(separate_authority_requirements) > 0 and array_position(separate_authority_requirements, null) is null),
  check (production_only is true),
  check (exact_candidate_required is true),
  check (independent_evidence_required is true),
  check (independent_evidence_substitution_allowed is false),
  check (nonrenewing is true)
);

create table if not exists penta_runtime.d3_founder_approval_revocations_v1 (
  window_id text primary key
    references penta_runtime.d3_founder_approval_windows_v1(window_id) on delete restrict,
  reason text not null,
  evidence_sha256 text not null,
  revoked_by text not null,
  revoked_at timestamptz not null default clock_timestamp(),
  check (length(btrim(reason)) between 1 and 1000),
  check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  check (length(btrim(revoked_by)) between 1 and 500)
);

create table if not exists penta_runtime.d3_founder_approval_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  window_id text not null
    references penta_runtime.d3_founder_approval_windows_v1(window_id) on delete restrict,
  release_id uuid
    references integration_control.governed_releases(release_id) on delete restrict,
  subject_type text not null,
  subject_ref text not null,
  target_system text not null,
  action_class text not null,
  exact_version_ref text not null,
  content_sha256 text not null,
  requested_by text not null,
  decision text not null default 'approved',
  approval_effect text not null default 'human_approval_predicate_only',
  release_authority_created boolean not null default false,
  independent_evidence_substitution_allowed boolean not null default false,
  window_starts_at timestamptz not null,
  window_expires_at timestamptz not null,
  receipt_sha256 text not null unique,
  consumed_at timestamptz not null default clock_timestamp(),
  check (length(btrim(subject_type)) between 1 and 100),
  check (length(btrim(subject_ref)) between 1 and 1000),
  check (length(btrim(target_system)) between 1 and 500),
  check (length(btrim(action_class)) between 1 and 100),
  check (length(btrim(exact_version_ref)) between 1 and 1000),
  check (content_sha256 ~ '^[0-9a-f]{64}$'),
  check (length(btrim(requested_by)) between 1 and 500),
  check (decision = 'approved'),
  check (approval_effect = 'human_approval_predicate_only'),
  check (release_authority_created is false),
  check (independent_evidence_substitution_allowed is false),
  check (window_expires_at = window_starts_at + interval '14 days'),
  check (consumed_at >= window_starts_at and consumed_at < window_expires_at),
  check (receipt_sha256 ~ '^[0-9a-f]{64}$')
);

create unique index if not exists d3_founder_approval_receipts_release_v1_uidx
  on penta_runtime.d3_founder_approval_receipts_v1(release_id)
  where release_id is not null;

create unique index if not exists d3_founder_approval_receipts_candidate_v1_uidx
  on penta_runtime.d3_founder_approval_receipts_v1(
    window_id,
    coalesce(release_id, '00000000-0000-0000-0000-000000000000'::uuid),
    subject_ref,
    exact_version_ref,
    content_sha256,
    action_class,
    target_system
  );

alter table penta_runtime.d3_founder_approval_windows_v1 enable row level security;
alter table penta_runtime.d3_founder_approval_windows_v1 force row level security;
alter table penta_runtime.d3_founder_approval_revocations_v1 enable row level security;
alter table penta_runtime.d3_founder_approval_revocations_v1 force row level security;
alter table penta_runtime.d3_founder_approval_receipts_v1 enable row level security;
alter table penta_runtime.d3_founder_approval_receipts_v1 force row level security;

drop policy if exists deny_client_access_v1 on penta_runtime.d3_founder_approval_windows_v1;
create policy deny_client_access_v1 on penta_runtime.d3_founder_approval_windows_v1
  for all to anon, authenticated using (false) with check (false);
drop policy if exists deny_client_access_v1 on penta_runtime.d3_founder_approval_revocations_v1;
create policy deny_client_access_v1 on penta_runtime.d3_founder_approval_revocations_v1
  for all to anon, authenticated using (false) with check (false);
drop policy if exists deny_client_access_v1 on penta_runtime.d3_founder_approval_receipts_v1;
create policy deny_client_access_v1 on penta_runtime.d3_founder_approval_receipts_v1
  for all to anon, authenticated using (false) with check (false);

drop trigger if exists trg_d3_founder_approval_windows_immutable_v1
  on penta_runtime.d3_founder_approval_windows_v1;
create trigger trg_d3_founder_approval_windows_immutable_v1
  before update or delete on penta_runtime.d3_founder_approval_windows_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();
drop trigger if exists trg_d3_founder_approval_revocations_immutable_v1
  on penta_runtime.d3_founder_approval_revocations_v1;
create trigger trg_d3_founder_approval_revocations_immutable_v1
  before update or delete on penta_runtime.d3_founder_approval_revocations_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();
drop trigger if exists trg_d3_founder_approval_receipts_immutable_v1
  on penta_runtime.d3_founder_approval_receipts_v1;
create trigger trg_d3_founder_approval_receipts_immutable_v1
  before update or delete on penta_runtime.d3_founder_approval_receipts_v1
  for each row execute function penta_runtime.reject_row_mutation_v1();

revoke all on penta_runtime.d3_founder_approval_windows_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.d3_founder_approval_revocations_v1 from public, anon, authenticated, service_role;
revoke all on penta_runtime.d3_founder_approval_receipts_v1 from public, anon, authenticated, service_role;
grant select on penta_runtime.d3_founder_approval_windows_v1 to service_role;
grant select on penta_runtime.d3_founder_approval_revocations_v1 to service_role;
grant select on penta_runtime.d3_founder_approval_receipts_v1 to service_role;

create or replace function penta_runtime.consume_d3_founder_approval_v1(
  p_subject_type text,
  p_subject_ref text,
  p_target_system text,
  p_action_class text,
  p_exact_version_ref text,
  p_content_sha256 text,
  p_requested_by text,
  p_release_id uuid default null
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, integration_control, extensions
as $$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true), '');
  v_window penta_runtime.d3_founder_approval_windows_v1%rowtype;
  v_release integration_control.governed_releases%rowtype;
  v_receipt_id uuid;
  v_receipt_sha256 text;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if coalesce(btrim(p_subject_type), '') = ''
     or coalesce(btrim(p_subject_ref), '') = ''
     or coalesce(btrim(p_target_system), '') = ''
     or coalesce(btrim(p_action_class), '') = ''
     or coalesce(btrim(p_exact_version_ref), '') = ''
     or coalesce(btrim(p_requested_by), '') = '' then
    raise exception 'exact_d3_candidate_fields_required';
  end if;
  if p_content_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'valid_content_sha256_required';
  end if;

  select w.* into v_window
  from penta_runtime.d3_founder_approval_windows_v1 w
  where w.starts_at <= clock_timestamp()
    and w.expires_at > clock_timestamp()
    and w.risk_class = 'D3'
    and w.approval_effect = 'human_approval_predicate_only'
    and w.production_only is true
    and w.exact_candidate_required is true
    and w.independent_evidence_required is true
    and w.independent_evidence_substitution_allowed is false
    and w.nonrenewing is true
    and p_action_class = any(w.eligible_action_classes)
    and not exists (
      select 1 from penta_runtime.d3_founder_approval_revocations_v1 x
      where x.window_id = w.window_id
    )
  order by w.starts_at desc
  limit 1;

  if not found then
    return jsonb_build_object(
      'state', 'HOLD',
      'reason', 'no_active_exact_scope_d3_founder_approval_window',
      'human_approval_state', 'pending',
      'release_authority_created', false
    );
  end if;

  if p_release_id is not null then
    select * into v_release
    from integration_control.governed_releases
    where release_id = p_release_id
    for update;
    if not found then raise exception 'governed_release_not_found'; end if;
    if v_release.risk_class <> 'D3'
       or v_release.subject_type is distinct from p_subject_type
       or v_release.subject_ref is distinct from p_subject_ref
       or v_release.exact_version_ref is distinct from p_exact_version_ref
       or v_release.content_sha256 is distinct from p_content_sha256 then
      raise exception 'governed_release_exact_candidate_mismatch';
    end if;
    if v_release.human_approval_state = 'denied' then
      return jsonb_build_object(
        'state', 'HOLD',
        'reason', 'exact_release_has_explicit_human_denial',
        'release_id', p_release_id,
        'release_authority_created', false
      );
    end if;
  end if;

  v_receipt_sha256 := encode(
    extensions.digest(
      convert_to(
        concat_ws(chr(31),
          v_window.window_id,
          coalesce(p_release_id::text, ''),
          p_subject_type,
          p_subject_ref,
          p_target_system,
          p_action_class,
          p_exact_version_ref,
          p_content_sha256,
          'human_approval_predicate_only'
        ),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  insert into penta_runtime.d3_founder_approval_receipts_v1(
    window_id, release_id, subject_type, subject_ref, target_system,
    action_class, exact_version_ref, content_sha256, requested_by,
    window_starts_at, window_expires_at, receipt_sha256
  ) values (
    v_window.window_id, p_release_id, p_subject_type, p_subject_ref, p_target_system,
    p_action_class, p_exact_version_ref, p_content_sha256, p_requested_by,
    v_window.starts_at, v_window.expires_at, v_receipt_sha256
  )
  on conflict do nothing
  returning receipt_id into v_receipt_id;

  if v_receipt_id is null then
    select receipt_id into v_receipt_id
    from penta_runtime.d3_founder_approval_receipts_v1
    where window_id = v_window.window_id
      and release_id is not distinct from p_release_id
      and subject_ref = p_subject_ref
      and exact_version_ref = p_exact_version_ref
      and content_sha256 = p_content_sha256
      and action_class = p_action_class
      and target_system = p_target_system;
  end if;

  return jsonb_build_object(
    'state', 'APPROVED',
    'human_approval_state', 'approved',
    'approval_effect', 'human_approval_predicate_only',
    'window_id', v_window.window_id,
    'window_expires_at', v_window.expires_at,
    'receipt_id', v_receipt_id,
    'receipt_sha256', v_receipt_sha256,
    'release_authority_created', false,
    'independent_evidence_substitution_allowed', false
  );
end;
$$;

revoke all on function penta_runtime.consume_d3_founder_approval_v1(
  text, text, text, text, text, text, text, uuid
) from public, anon, authenticated;
grant execute on function penta_runtime.consume_d3_founder_approval_v1(
  text, text, text, text, text, text, text, uuid
) to service_role;

create or replace function integration_control.enforce_d3_release_contract_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, integration_control, penta_runtime
as $$
declare
  v_dimension text;
  v_effect text;
  v_effect_dimension text;
  v_receipt penta_runtime.d3_founder_approval_receipts_v1%rowtype;
begin
  if new.risk_class <> 'D3' then return new; end if;

  foreach v_dimension in array array[
    'commercial_readiness',
    'exact_snapshot',
    'independent_verification',
    'monetization_readiness',
    'observability',
    'post_release_readback',
    'production_readiness',
    'rollback_readback',
    'security',
    'technical_tests'
  ] loop
    if not coalesce(new.required_certification_dimensions, '[]'::jsonb) @> jsonb_build_array(v_dimension) then
      raise exception 'd3_required_certification_dimension_missing:%', v_dimension;
    end if;
  end loop;

  if jsonb_typeof(coalesce(new.metadata->'requested_effects', '[]'::jsonb)) <> 'array' then
    raise exception 'd3_requested_effects_must_be_array';
  end if;
  for v_effect in
    select jsonb_array_elements_text(coalesce(new.metadata->'requested_effects', '[]'::jsonb))
  loop
    v_effect_dimension := case v_effect
      when 'provider_write' then 'provider_write_certification'
      when 'money_movement' then 'money_movement_authority'
      when 'payment' then 'money_movement_authority'
      when 'settlement' then 'money_movement_authority'
      when 'rights_disposition' then 'rights_authority'
      when 'license_grant' then 'rights_authority'
      when 'credential_mutation' then 'credential_custody'
      when 'contract_or_legal_commitment' then 'legal_signatory_authority'
      when 'personal_data' then 'privacy_compliance'
      else null
    end;
    if v_effect_dimension is null then
      raise exception 'unsupported_d3_requested_effect:%', v_effect;
    end if;
    if not new.required_certification_dimensions @> jsonb_build_array(v_effect_dimension) then
      raise exception 'd3_effect_certification_dimension_missing:%', v_effect_dimension;
    end if;
  end loop;

  if new.human_approval_state = 'approved'
     or new.release_state in ('accepted', 'publish_queued', 'published') then
    select r.* into v_receipt
    from penta_runtime.d3_founder_approval_receipts_v1 r
    join penta_runtime.d3_founder_approval_windows_v1 w on w.window_id = r.window_id
    where r.release_id = new.release_id
      and r.subject_type = new.subject_type
      and r.subject_ref = new.subject_ref
      and r.exact_version_ref = new.exact_version_ref
      and r.content_sha256 = new.content_sha256
      and r.decision = 'approved'
      and r.approval_effect = 'human_approval_predicate_only'
      and r.release_authority_created is false
      and r.independent_evidence_substitution_allowed is false
      and not exists (
        select 1 from penta_runtime.d3_founder_approval_revocations_v1 x
        where x.window_id = r.window_id
      )
    limit 1;
    if not found then raise exception 'exact_d3_founder_approval_receipt_required'; end if;
  end if;

  if new.release_state in ('accepted', 'publish_queued', 'published') then
    if new.human_approval_state <> 'approved' then
      raise exception 'd3_human_approval_required';
    end if;
    if new.accepted_at is null
       or new.accepted_at < v_receipt.window_starts_at
       or new.accepted_at >= v_receipt.window_expires_at then
      raise exception 'd3_release_acceptance_outside_founder_window';
    end if;
    if (tg_op = 'INSERT' or old.accepted_at is null)
       and not (clock_timestamp() >= v_receipt.window_starts_at and clock_timestamp() < v_receipt.window_expires_at) then
      raise exception 'd3_founder_approval_window_expired';
    end if;
  end if;

  return new;
end;
$$;

drop trigger if exists trg_enforce_d3_release_contract_v1
  on integration_control.governed_releases;
create trigger trg_enforce_d3_release_contract_v1
  before insert or update of
    risk_class,
    human_approval_state,
    required_certification_dimensions,
    metadata,
    exact_version_ref,
    content_sha256,
    release_state,
    accepted_at
  on integration_control.governed_releases
  for each row execute function integration_control.enforce_d3_release_contract_v1();

create or replace function integration_control.apply_d3_founder_approval_window_v1(
  p_release_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control, penta_runtime
as $$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true), '');
  v_release integration_control.governed_releases%rowtype;
  v_action_class text;
  v_approval jsonb;
  v_recompute jsonb;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  select * into v_release
  from integration_control.governed_releases
  where release_id = p_release_id
  for update;
  if not found then raise exception 'governed_release_not_found'; end if;
  if v_release.risk_class <> 'D3' then
    return jsonb_build_object('state', 'NOT_APPLICABLE', 'release_id', p_release_id);
  end if;
  if v_release.human_approval_state = 'denied' then
    return jsonb_build_object(
      'state', 'HOLD',
      'reason', 'exact_release_has_explicit_human_denial',
      'release_id', p_release_id
    );
  end if;

  v_action_class := coalesce(
    nullif(v_release.metadata->>'d3_action_class', ''),
    case
      when v_release.subject_type in ('product', 'offer', 'bundle', 'membership') then 'commercial_release'
      else 'production_release'
    end
  );

  v_approval := penta_runtime.consume_d3_founder_approval_v1(
    v_release.subject_type,
    v_release.subject_ref,
    'integration_control.governed_releases',
    v_action_class,
    v_release.exact_version_ref,
    v_release.content_sha256,
    coalesce(v_release.originating_agent_id, 'ct.system.governed-release'),
    v_release.release_id
  );

  if v_approval->>'state' <> 'APPROVED' then return v_approval; end if;

  update integration_control.governed_releases
  set human_approval_required = true,
      human_approval_state = 'approved',
      metadata = metadata || jsonb_build_object(
        'd3_founder_window_id', v_approval->>'window_id',
        'd3_founder_approval_receipt_id', v_approval->>'receipt_id',
        'd3_founder_approval_receipt_sha256', v_approval->>'receipt_sha256',
        'd3_founder_approval_effect', 'human_approval_predicate_only',
        'independent_evidence_substitution_allowed', false
      ),
      updated_at = clock_timestamp()
  where release_id = p_release_id
    and human_approval_state <> 'denied';

  v_recompute := integration_control.recompute_governed_release(p_release_id);
  return v_approval || jsonb_build_object(
    'release_id', p_release_id,
    'release_gate', v_recompute
  );
end;
$$;

revoke all on function integration_control.apply_d3_founder_approval_window_v1(uuid)
  from public, anon, authenticated;
grant execute on function integration_control.apply_d3_founder_approval_window_v1(uuid)
  to service_role;

create or replace function integration_control.auto_bind_d3_founder_approval_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
begin
  if new.risk_class = 'D3' and new.human_approval_state = 'pending' then
    perform integration_control.apply_d3_founder_approval_window_v1(new.release_id);
  end if;
  return new;
end;
$$;

revoke all on function integration_control.enforce_d3_release_contract_v1()
  from public, anon, authenticated, service_role;
revoke all on function integration_control.auto_bind_d3_founder_approval_v1()
  from public, anon, authenticated, service_role;

drop trigger if exists trg_auto_bind_d3_founder_approval_v1
  on integration_control.governed_releases;
create trigger trg_auto_bind_d3_founder_approval_v1
  after insert or update of risk_class, exact_version_ref, content_sha256, required_certification_dimensions
  on integration_control.governed_releases
  for each row execute function integration_control.auto_bind_d3_founder_approval_v1();

create or replace function penta_runtime.revoke_d3_founder_approval_window_v1(
  p_window_id text,
  p_reason text,
  p_evidence_sha256 text,
  p_revoked_by text
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, integration_control
as $$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true), '');
  v_release record;
  v_count integer := 0;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if coalesce(btrim(p_reason), '') = '' or coalesce(btrim(p_revoked_by), '') = '' then
    raise exception 'revocation_reason_and_principal_required';
  end if;
  if p_evidence_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'valid_revocation_evidence_sha256_required';
  end if;
  if not exists (
    select 1 from penta_runtime.d3_founder_approval_windows_v1 where window_id = p_window_id
  ) then raise exception 'd3_founder_approval_window_not_found'; end if;

  insert into penta_runtime.d3_founder_approval_revocations_v1(
    window_id, reason, evidence_sha256, revoked_by
  ) values (p_window_id, p_reason, p_evidence_sha256, p_revoked_by)
  on conflict (window_id) do nothing;

  for v_release in
    select g.release_id, g.release_state
    from integration_control.governed_releases g
    join penta_runtime.d3_founder_approval_receipts_v1 r on r.release_id = g.release_id
    where r.window_id = p_window_id
  loop
    if v_release.release_state = 'published' then
      perform integration_control.rollback_dynamic_feed_publication(
        v_release.release_id,
        'd3_founder_approval_window_revoked'
      );
    end if;
    update integration_control.governed_releases
    set human_approval_state = 'denied',
        release_state = case
          when release_state in ('rolled_back', 'superseded') then release_state
          else 'quarantined'
        end,
        accepted_at = null,
        updated_at = clock_timestamp(),
        metadata = metadata || jsonb_build_object(
          'd3_founder_window_revoked', true,
          'd3_founder_window_revocation_evidence_sha256', p_evidence_sha256
        )
    where release_id = v_release.release_id;
    v_count := v_count + 1;
  end loop;

  return jsonb_build_object(
    'state', 'REVOKED',
    'window_id', p_window_id,
    'affected_releases', v_count,
    'authority_effect', 'reduced'
  );
end;
$$;

revoke all on function penta_runtime.revoke_d3_founder_approval_window_v1(text, text, text, text)
  from public, anon, authenticated;
grant execute on function penta_runtime.revoke_d3_founder_approval_window_v1(text, text, text, text)
  to service_role;

create or replace function penta_runtime.d3_founder_approval_status_v1()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, penta_runtime
as $$
  select coalesce(
    (
      select jsonb_build_object(
        'window_id', w.window_id,
        'campaign_id', w.campaign_id,
        'risk_class', w.risk_class,
        'approval_effect', w.approval_effect,
        'starts_at', w.starts_at,
        'expires_at', w.expires_at,
        'active', now() >= w.starts_at
          and now() < w.expires_at
          and not exists (
            select 1 from penta_runtime.d3_founder_approval_revocations_v1 x
            where x.window_id = w.window_id
          ),
        'nonrenewing', w.nonrenewing,
        'independent_evidence_substitution_allowed', w.independent_evidence_substitution_allowed,
        'approval_receipt_count', (
          select count(*) from penta_runtime.d3_founder_approval_receipts_v1 r
          where r.window_id = w.window_id
        ),
        'revoked', exists (
          select 1 from penta_runtime.d3_founder_approval_revocations_v1 x
          where x.window_id = w.window_id
        )
      )
      from penta_runtime.d3_founder_approval_windows_v1 w
      order by w.starts_at desc
      limit 1
    ),
    jsonb_build_object('active', false, 'reason', 'no_window_registered')
  );
$$;

revoke all on function penta_runtime.d3_founder_approval_status_v1()
  from public, anon, authenticated;
grant execute on function penta_runtime.d3_founder_approval_status_v1()
  to service_role;

insert into developer_commerce.founder_directives(
  directive_id,
  founder_ref,
  directive_class,
  scope,
  source_sha256,
  authority_effect,
  independent_evidence_substitution_allowed,
  recorded_at
) values (
  'ct-founder-directive-d3-commercial-production-20260827-v1',
  'ct.person.founder.kavonte-jones-sr',
  'release_authorization',
  jsonb_build_object(
    'effective_at', '2026-08-27T16:51:43Z',
    'campaign_id', 'ct.penta.flow-control.20260826.v1',
    'window_id', 'ct.d3.founder-production-window.20260827.v1',
    'target_scope', 'all_crownthrive_d3_production_work',
    'human_approval_state', 'preapproved_during_window',
    'approval_effect', 'human_approval_predicate_only',
    'production_only', true,
    'exact_candidate_required', true,
    'commercialization_and_monetization_readiness_required', true,
    'independent_evidence_substitution_allowed', false,
    'automatic_renewal', false,
    'raw_directive_text_retained', false,
    'source_retention', 'sha256_and_public_safe_normalization_only'
  ),
  '3de7d9ace9d9b5d3f08bcd8ee4bc9c5d4fca42a6be1efac0b3664d94f813ea5b',
  'Pre-satisfies only the Founder-human approval predicate for exact D3 production candidates during the existing fourteen-day window; all non-human and effect-specific gates remain mandatory.',
  false,
  '2026-08-27T16:51:43Z'::timestamptz
)
on conflict (directive_id) do nothing;

do $$
begin
  if not exists (
    select 1
    from developer_commerce.founder_directives
    where directive_id = 'ct-founder-directive-d3-commercial-production-20260827-v1'
      and founder_ref = 'ct.person.founder.kavonte-jones-sr'
      and directive_class = 'release_authorization'
      and source_sha256 = '3de7d9ace9d9b5d3f08bcd8ee4bc9c5d4fca42a6be1efac0b3664d94f813ea5b'
      and independent_evidence_substitution_allowed is false
  ) then raise exception 'founder_directive_conflict'; end if;
end;
$$;

insert into penta_runtime.d3_founder_approval_windows_v1(
  window_id,
  directive_id,
  campaign_id,
  founder_ref,
  starts_at,
  expires_at,
  eligible_action_classes,
  required_release_dimensions,
  separate_authority_requirements
) values (
  'ct.d3.founder-production-window.20260827.v1',
  'ct-founder-directive-d3-commercial-production-20260827-v1',
  'ct.penta.flow-control.20260826.v1',
  'ct.person.founder.kavonte-jones-sr',
  '2026-08-27T01:23:52.144189Z'::timestamptz,
  '2026-09-10T01:23:52.144189Z'::timestamptz,
  array[
    'commercial_release',
    'monetization_activation',
    'production_gap_closure',
    'production_hardening',
    'production_release',
    'provider_activation'
  ]::text[],
  array[
    'commercial_readiness',
    'exact_snapshot',
    'independent_verification',
    'monetization_readiness',
    'observability',
    'post_release_readback',
    'production_readiness',
    'rollback_readback',
    'security',
    'technical_tests'
  ]::text[],
  array[
    'provider_write_certification_when_applicable',
    'money_movement_authority_when_applicable',
    'rights_authority_when_applicable',
    'credential_custody_when_applicable',
    'legal_signatory_authority_when_applicable',
    'privacy_compliance_when_applicable'
  ]::text[]
)
on conflict (window_id) do nothing;

do $$
begin
  if not exists (
    select 1
    from penta_runtime.d3_founder_approval_windows_v1
    where window_id = 'ct.d3.founder-production-window.20260827.v1'
      and directive_id = 'ct-founder-directive-d3-commercial-production-20260827-v1'
      and campaign_id = 'ct.penta.flow-control.20260826.v1'
      and founder_ref = 'ct.person.founder.kavonte-jones-sr'
      and starts_at = '2026-08-27T01:23:52.144189Z'::timestamptz
      and expires_at = '2026-09-10T01:23:52.144189Z'::timestamptz
      and approval_effect = 'human_approval_predicate_only'
      and production_only is true
      and exact_candidate_required is true
      and independent_evidence_required is true
      and independent_evidence_substitution_allowed is false
      and nonrenewing is true
  ) then raise exception 'd3_founder_approval_window_conflict'; end if;
end;
$$;

comment on table penta_runtime.d3_founder_approval_windows_v1 is
  'Immutable, nonrenewing Founder-human approval windows. A window satisfies only the exact D3 human-approval predicate.';
comment on table penta_runtime.d3_founder_approval_receipts_v1 is
  'Append-only exact-candidate receipts. These receipts create no release, provider, money, rights, credential, legal, privacy, or evidence authority.';
comment on function penta_runtime.consume_d3_founder_approval_v1(text, text, text, text, text, text, text, uuid) is
  'Consumes the active Founder window for one exact D3 candidate; returns human approval only and never substitutes for release evidence.';
