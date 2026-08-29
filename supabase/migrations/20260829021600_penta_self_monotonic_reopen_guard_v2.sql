-- PentaSELF monotonic problem-state guard v2
-- A verified resolution may reopen only on newer independently timestamped failure evidence.

create table if not exists penta_self.problem_reopen_candidates_v2 (
  candidate_id uuid primary key default gen_random_uuid(),
  fingerprint text not null,
  problem_id uuid,
  title text not null,
  candidate_state text not null default 'PENDING_INDEPENDENT_VERIFICATION',
  proposed_problem_state text not null,
  proposed_evidence jsonb not null default '{}'::jsonb,
  proposed_evidence_sha256 text not null,
  explicit_failure_observed_at timestamptz,
  resolution_verified_at timestamptz not null,
  resolution_verification_sha256 text not null,
  reason text not null,
  created_at timestamptz not null default now(),
  unique(fingerprint,proposed_evidence_sha256,resolution_verification_sha256)
);
alter table penta_self.problem_reopen_candidates_v2 enable row level security;
revoke all on penta_self.problem_reopen_candidates_v2 from public,anon,authenticated;
grant select,insert,update on penta_self.problem_reopen_candidates_v2 to service_role;
drop policy if exists problem_reopen_candidates_service_v2 on penta_self.problem_reopen_candidates_v2;
create policy problem_reopen_candidates_service_v2 on penta_self.problem_reopen_candidates_v2 for all to service_role using(true) with check(true);

create or replace function penta_self.try_timestamptz_v2(p_value text)
returns timestamptz language plpgsql immutable set search_path=pg_catalog as $$
begin
  if p_value is null or btrim(p_value)='' then return null; end if;
  return p_value::timestamptz;
exception when others then return null;
end $$;
revoke all on function penta_self.try_timestamptz_v2(text) from public,anon,authenticated;
grant execute on function penta_self.try_timestamptz_v2(text) to service_role;

update penta_self.problem_resolution_watermarks_v2 w
set metadata=w.metadata||jsonb_build_object(
  'superseded_problem_evidence_sha256',encode(extensions.digest((coalesce(p.evidence,'{}'::jsonb)-'attempts'-'latest_attempt_sha256'-'latest_attempt_result'-'next_attempt_at'-'last_attempt_at')::text,'sha256'),'hex'),
  'superseded_problem_last_seen_at',p.last_seen_at,
  'reopen_requires_explicit_newer_failure_timestamp',true
),updated_at=now()
from penta_self.problem_ledger_v1 p
where p.fingerprint=w.fingerprint;

create or replace function penta_self.enforce_monotonic_problem_state_v2()
returns trigger language plpgsql security definer set search_path=pg_catalog,penta_self,extensions as $$
declare
  v_watermark penta_self.problem_resolution_watermarks_v2%rowtype;
  v_explicit_failure_at timestamptz;
  v_candidate_evidence jsonb;
  v_candidate_sha text;
  v_superseded_sha text;
  v_reason text;
begin
  if new.state in ('resolved','closed','dismissed') then return new; end if;
  select * into v_watermark from penta_self.problem_resolution_watermarks_v2 where fingerprint=new.fingerprint and active=true limit 1;
  if not found then return new; end if;

  v_explicit_failure_at:=coalesce(
    penta_self.try_timestamptz_v2(new.evidence->>'provider_observed_at'),
    penta_self.try_timestamptz_v2(new.evidence->>'failed_at'),
    penta_self.try_timestamptz_v2(new.evidence->>'observed_at'),
    penta_self.try_timestamptz_v2(new.evidence->>'event_at'),
    penta_self.try_timestamptz_v2(new.evidence->>'event_time'),
    penta_self.try_timestamptz_v2(new.evidence->>'received_at'),
    penta_self.try_timestamptz_v2(new.evidence#>>'{provider,observed_at}'),
    penta_self.try_timestamptz_v2(new.evidence#>>'{readback,observed_at}')
  );
  v_candidate_evidence:=coalesce(new.evidence,'{}'::jsonb)-'attempts'-'latest_attempt_sha256'-'latest_attempt_result'-'next_attempt_at'-'last_attempt_at';
  v_candidate_sha:=encode(extensions.digest(v_candidate_evidence::text,'sha256'),'hex');
  v_superseded_sha:=v_watermark.metadata->>'superseded_problem_evidence_sha256';

  if v_explicit_failure_at is not null and v_explicit_failure_at>v_watermark.verified_at then
    new.resolved_at:=null;
    new.verification_evidence:=coalesce(new.verification_evidence,'{}'::jsonb)||jsonb_build_object('monotonic_reopen_v2',jsonb_build_object('allowed',true,'new_failure_observed_at',v_explicit_failure_at,'prior_resolution_verified_at',v_watermark.verified_at,'candidate_evidence_sha256',v_candidate_sha,'evaluated_at',now()));
    return new;
  end if;

  v_reason:=case
    when v_explicit_failure_at is null then 'explicit_newer_independent_failure_timestamp_missing'
    when v_explicit_failure_at<=v_watermark.verified_at then 'failure_observation_not_newer_than_verified_resolution'
    when v_superseded_sha=v_candidate_sha then 'superseded_failure_evidence_replayed'
    else 'reopen_not_independently_verified'
  end;
  insert into penta_self.problem_reopen_candidates_v2(fingerprint,problem_id,title,proposed_problem_state,proposed_evidence,proposed_evidence_sha256,explicit_failure_observed_at,resolution_verified_at,resolution_verification_sha256,reason)
  values(new.fingerprint,new.problem_id,new.title,new.state,coalesce(new.evidence,'{}'::jsonb),v_candidate_sha,v_explicit_failure_at,v_watermark.verified_at,v_watermark.verification_sha256,v_reason)
  on conflict(fingerprint,proposed_evidence_sha256,resolution_verification_sha256) do nothing;

  new.state:='resolved';
  new.resolved_at:=coalesce(old.resolved_at,v_watermark.verified_at);
  new.next_attempt_at:=null;
  new.blocked_reason:=null;
  new.last_error:=null;
  new.verification_evidence:=coalesce(new.verification_evidence,'{}'::jsonb)||jsonb_build_object('monotonic_reopen_v2',jsonb_build_object('allowed',false,'reason',v_reason,'candidate_evidence_sha256',v_candidate_sha,'explicit_failure_observed_at',v_explicit_failure_at,'prior_resolution_verified_at',v_watermark.verified_at,'quarantined_at',now()));
  return new;
end $$;
revoke all on function penta_self.enforce_monotonic_problem_state_v2() from public,anon,authenticated;
grant execute on function penta_self.enforce_monotonic_problem_state_v2() to service_role;
drop trigger if exists enforce_monotonic_problem_state_v2 on penta_self.problem_ledger_v1;
create trigger enforce_monotonic_problem_state_v2 before insert or update of state,evidence,last_seen_at on penta_self.problem_ledger_v1 for each row execute function penta_self.enforce_monotonic_problem_state_v2();

select penta_self.append_persistence_receipt_v2('pentaself.problem-reopen-guard','INSTALL_MONOTONIC_REOPEN_GUARD','active',jsonb_build_object('policy','newer independently timestamped failure required','unverified_reopen_action','quarantine','automatic_rollback',false,'history_deleted',false));
