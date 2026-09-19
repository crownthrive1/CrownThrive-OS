-- ct.chlom.founder-continuity-request-structural-replay-bridge.v1
-- Purpose: restore only the empty founder continuity request relation required
-- as an FK/rowtype dependency by 20260823235410 on blank migration replay.
--
-- This is NOT the founder continuity layer. It creates no policy, vote, quorum,
-- surrogate attestation, human override, execution authority, D3 authority,
-- money movement, rights grant, credential capability, or durable DAIL write.
-- Current production already has the authoritative relation, so this migration
-- is a guaranteed no-op there.

begin;
do $bridge$
begin
  if to_regclass('chlom_runtime.founder_continuity_requests') is not null then
    return;
  end if;

  create schema if not exists chlom_runtime;
  revoke all on schema chlom_runtime from public, anon, authenticated;

  create table chlom_runtime.founder_continuity_requests (
    request_id uuid primary key default extensions.gen_random_uuid(),
    subject_ref text not null,
    exact_version_ref text not null,
    content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
    human_signal_state text not null default 'requested' check (human_signal_state in ('requested','approved','denied','cancelled')),
    human_authority_evidence_ref text,
    metadata jsonb not null default jsonb_build_object(
      'replay_only_structural_bridge',true,
      'authority_created',false,
      'vote_effect',false,
      'surrogate_authority',false,
      'execution_authority',false
    ),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
  );

  alter table chlom_runtime.founder_continuity_requests enable row level security;
  alter table chlom_runtime.founder_continuity_requests force row level security;
  revoke all on chlom_runtime.founder_continuity_requests from public, anon, authenticated, service_role;
end
$bridge$;

do $verify$
begin
  if to_regclass('chlom_runtime.founder_continuity_requests') is null then
    raise exception 'HOLD_FOUNDER_CONTINUITY_REQUEST_REPLAY_BRIDGE_INCOMPLETE';
  end if;
  if exists(select 1 from chlom_runtime.founder_continuity_requests) then
    raise exception 'HOLD_FOUNDER_CONTINUITY_REQUEST_REPLAY_BRIDGE_MUST_BE_EMPTY';
  end if;
end
$verify$;
commit;
