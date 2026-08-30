-- Transactional acceptance tests for CHLOM + PentaSecurity assurance fabric v1.
-- Intended for a database where migration 20260830084500 has been applied.
-- All test data rolls back.

begin;

do $$
declare
  v_case uuid;
  v_failed boolean;
begin
  insert into penta_runtime.security_assurance_cases_v1(
    subject_ref, subject_version, requires_cie, originator_ref, certifier_ref, metadata
  ) values (
    'test:security-fabric', '1.0.0', true, 'ct.test.originator', 'ct.test.independent-certifier', '{"test":true}'::jsonb
  ) returning case_id into v_case;

  perform penta_runtime.security_assurance_transition_v1(v_case,'scanned','ct.test.scanner','sha256:test-scan','machine','evidence','{}');
  perform penta_runtime.security_assurance_transition_v1(v_case,'threat_modeled','ct.test.threat','sha256:test-threat','hybrid','decision','{}');
  perform penta_runtime.security_assurance_transition_v1(v_case,'tested','ct.test.runner','sha256:test-suite','machine','evidence','{}');
  perform penta_runtime.security_assurance_transition_v1(v_case,'security_pass','ct.test.security-verifier','sha256:test-security','hybrid','decision','{}');
  perform penta_runtime.security_assurance_transition_v1(v_case,'chlom_pass','ct.test.chlom-authority','sha256:test-chlom','hybrid','decision','{}');
  perform penta_runtime.security_assurance_transition_v1(v_case,'cie_pass','ct.test.cie','sha256:test-cie','human','decision','{}');
  perform penta_runtime.security_assurance_transition_v1(v_case,'certification_pending','ct.test.router','sha256:test-pending','machine','execution','{}');
  perform penta_runtime.security_assurance_transition_v1(v_case,'certified','ct.test.independent-certifier','sha256:test-cert','human','decision','{}');
  perform penta_runtime.security_assurance_transition_v1(v_case,'released','ct.test.release','sha256:test-release','machine','execution','{}');

  if (select current_state from penta_runtime.security_assurance_cases_v1 where case_id=v_case) <> 'released' then
    raise exception 'happy path failed';
  end if;

  -- Originator must never certify its own work.
  insert into penta_runtime.security_assurance_cases_v1(
    subject_ref, subject_version, current_state, originator_ref, certifier_ref
  ) values (
    'test:self-cert', '1.0.0', 'certification_pending', 'ct.test.originator', 'ct.test.originator'
  ) returning case_id into v_case;
  v_failed := false;
  begin
    perform penta_runtime.security_assurance_transition_v1(v_case,'certified','ct.test.originator','sha256:self-cert','human','decision','{}');
  exception when others then
    v_failed := true;
  end;
  if not v_failed then raise exception 'self-certification negative test failed'; end if;

  -- Cannot skip scan/threat-model/test/security/CHLOM gates.
  insert into penta_runtime.security_assurance_cases_v1(
    subject_ref, subject_version, originator_ref, certifier_ref
  ) values (
    'test:skip-gates', '1.0.0', 'ct.test.originator', 'ct.test.certifier'
  ) returning case_id into v_case;
  v_failed := false;
  begin
    perform penta_runtime.security_assurance_transition_v1(v_case,'released','ct.test.release','sha256:skip','machine','execution','{}');
  exception when others then
    v_failed := true;
  end;
  if not v_failed then raise exception 'gate-skip negative test failed'; end if;

  -- Canonical DAIL lane and semantic-stage vocabularies are independently constrained.
  v_failed := false;
  begin
    perform penta_runtime.security_assurance_transition_v1(v_case,'scanned','ct.test.scanner','sha256:bad-lane','evidence','machine','{}');
  exception when others then
    v_failed := true;
  end;
  if not v_failed then raise exception 'DAIL lane semantic inversion negative test failed'; end if;

  -- Assurance chronology is append-only.
  select case_id into v_case from penta_runtime.security_assurance_cases_v1 where subject_ref='test:security-fabric';
  v_failed := false;
  begin
    update penta_runtime.security_assurance_events_v1 set evidence_ref='mutated' where case_id=v_case;
  exception when others then
    v_failed := true;
  end;
  if not v_failed then raise exception 'append-only negative test failed'; end if;
end
$$;

rollback;
