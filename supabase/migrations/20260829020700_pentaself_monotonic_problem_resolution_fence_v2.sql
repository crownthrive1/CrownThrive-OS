-- Prevent stale observations from reopening resolved problems.

create table if not exists penta_self.problem_resolution_fences_v2 (
  problem_id uuid primary key references penta_self.problem_ledger_v1(problem_id),
  fingerprint text not null,
  resolution_generation bigint not null,
  resolved_at timestamptz not null,
  resolution_evidence_sha256 text not null,
  verification_evidence jsonb not null default '{}'::jsonb,
  stale_reopen_blocks bigint not null default 0,
  last_stale_reopen_at timestamptz,
  updated_at timestamptz not null default now()
);
alter table penta_self.problem_resolution_fences_v2 enable row level security;
revoke all on penta_self.problem_resolution_fences_v2 from public,anon,authenticated;
grant select,insert,update on penta_self.problem_resolution_fences_v2 to service_role;
do $$ begin
 if not exists(select 1 from pg_policies where schemaname='penta_self' and tablename='problem_resolution_fences_v2' and policyname='problem_resolution_fences_service_role_v2') then
   create policy problem_resolution_fences_service_role_v2 on penta_self.problem_resolution_fences_v2 for all to service_role using(true) with check(true);
 end if;
end $$;

create or replace function penta_self.problem_resolution_fence_before_v2()
returns trigger language plpgsql security definer
set search_path=pg_catalog,penta_self,extensions
as $$
declare v_observed_at timestamptz; v_is_fresh boolean:=false; v_incoming_state text:=new.state;
begin
  if old.state='resolved' and new.state<>'resolved' then
    begin v_observed_at:=coalesce(nullif(new.evidence->>'observed_at','')::timestamptz,new.last_seen_at,new.updated_at); exception when others then v_observed_at:=coalesce(new.last_seen_at,new.updated_at); end;
    v_is_fresh:=v_observed_at is not null and old.resolved_at is not null and v_observed_at>old.resolved_at;
    if not v_is_fresh then
      new.state:='resolved'; new.resolved_at:=old.resolved_at; new.blocked_reason:=null; new.last_error:=null;
      new.verification_evidence:=coalesce(old.verification_evidence,'{}'::jsonb)||jsonb_build_object('stale_reopen_blocked',true,'stale_reopen_blocked_at',now(),'incoming_observed_at',v_observed_at,'resolution_fence_at',old.resolved_at,'incoming_state',v_incoming_state,'guard','penta_self.problem_resolution_fence_before_v2');
      update penta_self.problem_resolution_fences_v2 set stale_reopen_blocks=stale_reopen_blocks+1,last_stale_reopen_at=now(),updated_at=now() where problem_id=old.problem_id;
    end if;
  end if;
  return new;
end $$;
revoke all on function penta_self.problem_resolution_fence_before_v2() from public,anon,authenticated;
grant execute on function penta_self.problem_resolution_fence_before_v2() to service_role;
drop trigger if exists problem_resolution_fence_before_v2 on penta_self.problem_ledger_v1;
create trigger problem_resolution_fence_before_v2 before update on penta_self.problem_ledger_v1 for each row execute function penta_self.problem_resolution_fence_before_v2();

create or replace function penta_self.problem_resolution_fence_after_v2()
returns trigger language plpgsql security definer
set search_path=pg_catalog,penta_self,extensions
as $$
declare v_sha text; v_generation bigint;
begin
  if new.state='resolved' and (old.state is distinct from 'resolved' or old.resolved_at is distinct from new.resolved_at or old.verification_evidence is distinct from new.verification_evidence) then
    v_generation:=floor(extract(epoch from coalesce(new.resolved_at,now()))*1000)::bigint;
    v_sha:=encode(extensions.digest(convert_to(jsonb_build_object('problem_id',new.problem_id,'fingerprint',new.fingerprint,'resolved_at',new.resolved_at,'verification_evidence',new.verification_evidence,'generation',v_generation)::text,'UTF8'),'sha256'),'hex');
    insert into penta_self.problem_resolution_fences_v2(problem_id,fingerprint,resolution_generation,resolved_at,resolution_evidence_sha256,verification_evidence,updated_at)
    values(new.problem_id,new.fingerprint,v_generation,coalesce(new.resolved_at,now()),v_sha,coalesce(new.verification_evidence,'{}'::jsonb),now())
    on conflict(problem_id) do update set fingerprint=excluded.fingerprint,resolution_generation=greatest(penta_self.problem_resolution_fences_v2.resolution_generation,excluded.resolution_generation),resolved_at=greatest(penta_self.problem_resolution_fences_v2.resolved_at,excluded.resolved_at),resolution_evidence_sha256=excluded.resolution_evidence_sha256,verification_evidence=penta_self.problem_resolution_fences_v2.verification_evidence||excluded.verification_evidence,updated_at=now()
    where excluded.resolution_generation>=penta_self.problem_resolution_fences_v2.resolution_generation;
  end if;
  return new;
end $$;
revoke all on function penta_self.problem_resolution_fence_after_v2() from public,anon,authenticated;
grant execute on function penta_self.problem_resolution_fence_after_v2() to service_role;
drop trigger if exists problem_resolution_fence_after_v2 on penta_self.problem_ledger_v1;
create trigger problem_resolution_fence_after_v2 after update on penta_self.problem_ledger_v1 for each row execute function penta_self.problem_resolution_fence_after_v2();

insert into penta_self.problem_resolution_fences_v2(problem_id,fingerprint,resolution_generation,resolved_at,resolution_evidence_sha256,verification_evidence)
select problem_id,fingerprint,floor(extract(epoch from resolved_at)*1000)::bigint,resolved_at,encode(extensions.digest(convert_to(jsonb_build_object('problem_id',problem_id,'fingerprint',fingerprint,'resolved_at',resolved_at,'verification_evidence',verification_evidence)::text,'UTF8'),'sha256'),'hex'),coalesce(verification_evidence,'{}'::jsonb)
from penta_self.problem_ledger_v1 where state='resolved' and resolved_at is not null
on conflict(problem_id) do update set resolution_generation=greatest(penta_self.problem_resolution_fences_v2.resolution_generation,excluded.resolution_generation),resolved_at=greatest(penta_self.problem_resolution_fences_v2.resolved_at,excluded.resolved_at),resolution_evidence_sha256=excluded.resolution_evidence_sha256,verification_evidence=penta_self.problem_resolution_fences_v2.verification_evidence||excluded.verification_evidence,updated_at=now();
