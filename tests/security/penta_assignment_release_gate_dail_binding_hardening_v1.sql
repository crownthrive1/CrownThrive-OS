-- Negative/adversarial test for exact DAIL receipt binding.
-- All test-local DAIL rows and candidate bindings roll back.

begin;

do $$
declare
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_unrelated jsonb;
  v_event_id uuid;
  v_event_hash text;
  v_rejected boolean:=false;
begin
  select * into a from integration_control.penta_assignment_contracts_v1
  where source_pr_number=2078 and state='AWAITING_CERTIFICATION' and independent_certification_required
  order by updated_at desc,created_at desc limit 1;
  if not found then raise exception 'current #2078 certification fixture missing'; end if;

  -- A real DAIL event id/hash is not sufficient: this event deliberately lacks the
  -- canonical release-gate receipt envelope and must never be accepted as PASS.
  v_unrelated:=chlom_runtime.append_dail_event(
    'penta.assignment.release-gate.negative-test.v1','penta_assignment_negative_test',a.assignment_id::text,
    jsonb_build_object('test','unrelated-valid-dail-event','authority_created',false),
    'PentaSecurity',null,'penta.security','1.0.0','test:release-gate:'||a.assignment_id::text,null,
    'transactional negative test only',null,'internal'
  );
  v_event_id:=(v_unrelated->>'event_id')::uuid;
  select event_hash into v_event_hash from chlom_runtime.dail_events where event_id=v_event_id;
  if v_event_hash is null then raise exception 'negative-test DAIL readback missing'; end if;

  begin
    perform integration_control.penta_assignment_bind_release_gate_v1(
      a.assignment_id,'PENTASECURITY','PASS','penta.security',a.exact_head_sha,a.exact_artifact_sha256,
      'transactional-negative-unrelated-dail',repeat('a',64),v_event_id,v_event_hash,null,
      jsonb_build_object('test','unrelated-dail-substitution')
    );
  exception when others then
    if sqlerrm='release_gate_dail_payload_contract_mismatch' then v_rejected:=true; else raise; end if;
  end;
  if not v_rejected then raise exception 'unrelated valid DAIL event must not bind as release-gate PASS'; end if;

  if exists(select 1 from integration_control.penta_assignment_release_gate_bindings_v1 where assignment_id=a.assignment_id and evidence_ref='transactional-negative-unrelated-dail') then
    raise exception 'rejected unrelated DAIL event created a gate binding';
  end if;
end
$$;

rollback;
