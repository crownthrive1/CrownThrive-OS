-- Transactional acceptance tests for CHLOM + PentaSecurity assurance fabric v1.
-- Intended for a database where migration 20260830084500 has been applied.
-- All test data rolls back.

begin;

do $$
declare
  v_case uuid;
  v_case2 uuid;
  v_failed boolean;
  v_open jsonb;
  v_result jsonb;
  v_dail_event uuid;
  v_dail_hash text;
begin
  v_open := penta_runtime.security_assurance_open_case_v1(
    'test:security-fabric',
    '1.0.0',
    'ct.test.originator',
    'ct.test.security-decider',
    'ct.test.independent-certifier',
    'ct.test.chlom-authority',
    'sha256:test-open',
    true,
    'ct.test.cie-decider',
    'sha256:test-case-digest',
    null,
    'ct.test.agent',
    '{"test":true}'::jsonb
  );
  v_case := (v_open->>'case_id')::uuid;

  perform penta_runtime.security_assurance_transition_v1(v_case,'scanned','ct.test.scanner','sha256:test-scan','evidence');
  perform penta_runtime.security_assurance_transition_v1(v_case,'threat_modeled','ct.test.threat','sha256:test-threat','evidence');
  perform penta_runtime.security_assurance_transition_v1(v_case,'tested','ct.test.runner','sha256:test-suite','evidence');
  perform penta_runtime.security_assurance_transition_v1(v_case,'security_pass','ct.test.security-decider','sha256:test-security','decision');
  perform penta_runtime.security_assurance_transition_v1(v_case,'chlom_pass','ct.test.chlom-authority','sha256:test-chlom','decision');
  perform penta_runtime.security_assurance_transition_v1(v_case,'cie_pass','ct.test.cie-decider','sha256:test-cie','decision');
  perform penta_runtime.security_assurance_transition_v1(v_case,'certification_pending','ct.test.router','sha256:test-pending','execution');
  perform penta_runtime.security_assurance_transition_v1(v_case,'certified','ct.test.independent-certifier','sha256:test-cert','decision');
  v_result := penta_runtime.security_assurance_transition_v1(v_case,'released','ct.test.release','sha256:test-release','execution');

  if (select current_state from penta_runtime.security_assurance_cases_v1 where case_id=v_case) <> 'released' then
    raise exception 'happy path failed';
  end if;

  -- Every local assurance event must be bound to an exact canonical DAIL event/hash.
  if exists (
    select 1
    from penta_runtime.security_assurance_events_v1 e
    left join chlom_runtime.dail_events d on d.event_id=e.canonical_dail_event_id
    where e.case_id=v_case
      and (d.event_id is null or d.event_hash is distinct from e.canonical_dail_event_hash)
  ) then
    raise exception 'canonical DAIL append/readback binding failed';
  end if;

  -- Decision events must be classified by canonical DAIL routing, not by caller-supplied lane labels.
  if not exists (
    select 1
    from penta_runtime.security_assurance_events_v1 e
    where e.case_id=v_case
      and e.semantic_stage='decision'
      and e.dail_classification->>'state'='CLASSIFIED'
      and coalesce((e.dail_classification->>'crossover')::boolean,false)=true
  ) then
    raise exception 'canonical DAIL decision/crossover classification failed';
  end if;

  -- Originator must never certify its own work.
  v_open := penta_runtime.security_assurance_open_case_v1(
    'test:self-cert',
    '1.0.0',
    'ct.test.originator',
    'ct.test.security-decider',
    'ct.test.independent-certifier',
    'ct.test.chlom-authority',
    'sha256:self-open'
  );
  v_case2 := (v_open->>'case_id')::uuid;
  perform penta_runtime.security_assurance_transition_v1(v_case2,'scanned','ct.test.scanner','sha256:self-scan','evidence');
  perform penta_runtime.security_assurance_transition_v1(v_case2,'threat_modeled','ct.test.threat','sha256:self-threat','evidence');
  perform penta_runtime.security_assurance_transition_v1(v_case2,'tested','ct.test.runner','sha256:self-test','evidence');
  perform penta_runtime.security_assurance_transition_v1(v_case2,'security_pass','ct.test.security-decider','sha256:self-sec','decision');
  perform penta_runtime.security_assurance_transition_v1(v_case2,'chlom_pass','ct.test.chlom-authority','sha256:self-chlom','decision');
  perform penta_runtime.security_assurance_transition_v1(v_case2,'certification_pending','ct.test.router','sha256:self-pending','execution');
  v_failed := false;
  begin
    perform penta_runtime.security_assurance_transition_v1(v_case2,'certified','ct.test.originator','sha256:self-cert','decision');
  exception when others then
    v_failed := true;
  end;
  if not v_failed then raise exception 'self-certification negative test failed'; end if;

  -- Cannot skip scan/threat-model/test/security/CHLOM gates.
  v_open := penta_runtime.security_assurance_open_case_v1(
    'test:skip-gates',
    '1.0.0',
    'ct.test.originator',
    'ct.test.security-decider',
    'ct.test.certifier',
    'ct.test.chlom-authority',
    'sha256:skip-open'
  );
  v_case2 := (v_open->>'case_id')::uuid;
  v_failed := false;
  begin
    perform penta_runtime.security_assurance_transition_v1(v_case2,'released','ct.test.release','sha256:skip','execution');
  exception when others then
    v_failed := true;
  end;
  if not v_failed then raise exception 'gate-skip negative test failed'; end if;

  -- Semantic stage must match the transition class.
  v_failed := false;
  begin
    perform penta_runtime.security_assurance_transition_v1(v_case2,'scanned','ct.test.scanner','sha256:bad-stage','decision');
  exception when others then
    v_failed := true;
  end;
  if not v_failed then raise exception 'semantic-stage mismatch negative test failed'; end if;

  -- Bound security/CHLOM actors cannot be substituted by another actor string.
  v_failed := false;
  begin
    perform penta_runtime.security_assurance_transition_v1(v_case2,'scanned','ct.test.scanner','sha256:scan-ok','evidence');
    perform penta_runtime.security_assurance_transition_v1(v_case2,'threat_modeled','ct.test.threat','sha256:threat-ok','evidence');
    perform penta_runtime.security_assurance_transition_v1(v_case2,'tested','ct.test.runner','sha256:test-ok','evidence');
    perform penta_runtime.security_assurance_transition_v1(v_case2,'security_pass','ct.test.wrong-security','sha256:wrong-sec','decision');
  exception when others then
    v_failed := true;
  end;
  if not v_failed then raise exception 'bound security-decider negative test failed'; end if;

  -- Assurance chronology is append-only even for the migration owner.
  select canonical_dail_event_id, canonical_dail_event_hash
    into v_dail_event, v_dail_hash
  from penta_runtime.security_assurance_events_v1
  where case_id=v_case
  order by created_at desc, event_id desc
  limit 1;

  v_failed := false;
  begin
    update penta_runtime.security_assurance_events_v1
    set evidence_ref='mutated'
    where canonical_dail_event_id=v_dail_event;
  exception when others then
    v_failed := true;
  end;
  if not v_failed then raise exception 'append-only negative test failed'; end if;

  if (select event_hash from chlom_runtime.dail_events where event_id=v_dail_event) <> v_dail_hash then
    raise exception 'canonical DAIL hash changed after append-only test';
  end if;
end
$$;

-- Runtime service role may read projections and invoke governed functions, but cannot
-- directly mutate assurance state or inject local chronology rows.
set local role service_role;

do $$
declare
  v_failed boolean := false;
begin
  begin
    update penta_runtime.security_assurance_cases_v1
    set current_state='released'
    where subject_ref='test:skip-gates';
  exception when insufficient_privilege then
    v_failed := true;
  when others then
    v_failed := true;
  end;
  if not v_failed then raise exception 'service_role direct state mutation unexpectedly succeeded'; end if;

  v_failed := false;
  begin
    insert into penta_runtime.security_assurance_events_v1(
      case_id,from_state,to_state,actor_ref,evidence_ref,semantic_stage,
      canonical_dail_event_id,canonical_dail_event_hash,dail_classification
    )
    select case_id,'candidate','released','ct.test.injector','sha256:inject','execution',
           gen_random_uuid(),'forged','{}'::jsonb
    from penta_runtime.security_assurance_cases_v1
    where subject_ref='test:skip-gates'
    limit 1;
  exception when insufficient_privilege then
    v_failed := true;
  when others then
    v_failed := true;
  end;
  if not v_failed then raise exception 'service_role direct chronology injection unexpectedly succeeded'; end if;
end
$$;

reset role;

rollback;
