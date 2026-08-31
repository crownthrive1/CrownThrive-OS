-- Transactional deterministic / negative / adversarial acceptance for
-- 20260831135000_penta_assignment_release_gate_bridge_v1.sql.
--
-- This test does not manufacture PentaSecurity, CHLOM, CIE or PentaCertifier PASS.
-- It proves that the bridge stays fail-closed until authentic exact-subject receipts
-- are bound, rejects authority/head/digest mismatches, and queues no certifier work
-- while upstream release gates are missing. All test-local state is rolled back.

begin;

do $$
declare
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_pre jsonb;
  v_enqueue jsonb;
  v_before bigint;
  v_after bigint;
  v_rejected boolean;
begin
  select * into a
  from integration_control.penta_assignment_contracts_v1
  where source_pr_number=2078
    and state='AWAITING_CERTIFICATION'
    and independent_certification_required
  order by updated_at desc,created_at desc
  limit 1;

  if not found then raise exception 'current #2078 AWAITING_CERTIFICATION assignment fixture missing'; end if;
  if a.exact_head_sha !~ '^[0-9a-f]{40}$' then raise exception 'fixture exact head missing'; end if;
  if a.exact_artifact_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'fixture exact subject digest missing'; end if;

  v_pre:=integration_control.penta_assignment_certifier_preflight_v1(a.assignment_id);
  if coalesce((v_pre->>'ready')::boolean,true) then raise exception 'preflight must not become ready without authentic upstream release-gate receipts: %',v_pre; end if;
  if not exists(select 1 from jsonb_array_elements_text(coalesce(v_pre->'missing','[]'::jsonb)) x where x='PENTASECURITY_EXACT_SUBJECT_PASS') then raise exception 'preflight must require exact-subject PentaSecurity PASS: %',v_pre; end if;
  if not exists(select 1 from jsonb_array_elements_text(coalesce(v_pre->'missing','[]'::jsonb)) x where x='CHLOM_RIGHTS_AUTHORITY') then raise exception 'preflight must require CHLOM rights/authority disposition: %',v_pre; end if;
  if not exists(select 1 from jsonb_array_elements_text(coalesce(v_pre->'missing','[]'::jsonb)) x where x='CIE_APPLICABILITY_OR_PASS') then raise exception 'preflight must require CIE applicability/PASS disposition: %',v_pre; end if;
  if coalesce((v_pre->>'authority_created')::boolean,true) or coalesce((v_pre->>'certification_issued')::boolean,true) or coalesce((v_pre->>'release_authorized')::boolean,true) then raise exception 'preflight must be authority-neutral: %',v_pre; end if;

  select count(*) into v_before from integration_control.penta_certify_tasks_v3 where evidence->>'assignment_id'=a.assignment_id::text;
  v_enqueue:=integration_control.penta_assignment_enqueue_independent_certifier_v1(a.assignment_id);
  if v_enqueue->>'state'<>'HOLD' or v_enqueue->>'reason'<>'UPSTREAM_RELEASE_GATES_MISSING' then raise exception 'enqueue must fail closed while upstream release gates are missing: %',v_enqueue; end if;
  select count(*) into v_after from integration_control.penta_certify_tasks_v3 where evidence->>'assignment_id'=a.assignment_id::text;
  if v_after<>v_before then raise exception 'held preflight must not queue certifier work: before %, after %',v_before,v_after; end if;

  v_rejected:=false;
  begin
    perform integration_control.penta_assignment_bind_release_gate_v1(a.assignment_id,'PENTASECURITY','PASS','penta.build',a.exact_head_sha,a.exact_artifact_sha256,'synthetic-negative-test',repeat('a',64),gen_random_uuid(),repeat('b',64),null,jsonb_build_object('test','authority-mismatch'));
  exception when others then if sqlerrm='release_gate_authority_mismatch' then v_rejected:=true; else raise; end if; end;
  if not v_rejected then raise exception 'authority mismatch must be rejected'; end if;

  v_rejected:=false;
  begin
    perform integration_control.penta_assignment_bind_release_gate_v1(a.assignment_id,'PENTASECURITY','PASS','penta.security',repeat('0',40),a.exact_artifact_sha256,'synthetic-negative-test',repeat('a',64),gen_random_uuid(),repeat('b',64),null,jsonb_build_object('test','head-mismatch'));
  exception when others then if sqlerrm='release_gate_exact_head_mismatch' then v_rejected:=true; else raise; end if; end;
  if not v_rejected then raise exception 'wrong exact head must be rejected'; end if;

  -- Use the canonical CHLOM authority identity so this negative test reaches the
  -- exact-subject digest predicate instead of failing earlier on authority identity.
  v_rejected:=false;
  begin
    perform integration_control.penta_assignment_bind_release_gate_v1(a.assignment_id,'CHLOM_RIGHTS','PASS','chlom_core',a.exact_head_sha,repeat('0',64),'synthetic-negative-test',repeat('a',64),gen_random_uuid(),repeat('b',64),null,jsonb_build_object('test','subject-mismatch'));
  exception when others then if sqlerrm='release_gate_subject_digest_mismatch' then v_rejected:=true; else raise; end if; end;
  if not v_rejected then raise exception 'wrong exact subject digest must be rejected'; end if;
end
$$;

do $$
begin
  if has_function_privilege('public','integration_control.penta_assignment_certifier_preflight_v1(uuid)','EXECUTE') or has_function_privilege('anon','integration_control.penta_assignment_certifier_preflight_v1(uuid)','EXECUTE') or has_function_privilege('authenticated','integration_control.penta_assignment_certifier_preflight_v1(uuid)','EXECUTE') then raise exception 'preflight v1 must not be publicly executable'; end if;
  if not has_function_privilege('service_role','integration_control.penta_assignment_certifier_preflight_v1(uuid)','EXECUTE') then raise exception 'service_role must retain preflight v1 execution'; end if;

  if has_function_privilege('public','integration_control.penta_assignment_enqueue_independent_certifier_v1(uuid)','EXECUTE') or has_function_privilege('anon','integration_control.penta_assignment_enqueue_independent_certifier_v1(uuid)','EXECUTE') or has_function_privilege('authenticated','integration_control.penta_assignment_enqueue_independent_certifier_v1(uuid)','EXECUTE') then raise exception 'independent-certifier enqueue v1 must not be publicly executable'; end if;
  if not has_function_privilege('service_role','integration_control.penta_assignment_enqueue_independent_certifier_v1(uuid)','EXECUTE') then raise exception 'service_role must retain independent-certifier enqueue v1 execution'; end if;

  if has_function_privilege('public','integration_control.penta_assignment_bind_release_gate_v1(uuid,text,text,text,text,text,text,text,uuid,text,uuid,jsonb)','EXECUTE') or has_function_privilege('anon','integration_control.penta_assignment_bind_release_gate_v1(uuid,text,text,text,text,text,text,text,uuid,text,uuid,jsonb)','EXECUTE') or has_function_privilege('authenticated','integration_control.penta_assignment_bind_release_gate_v1(uuid,text,text,text,text,text,text,text,uuid,text,uuid,jsonb)','EXECUTE') then raise exception 'release-gate binding v1 must not be publicly executable'; end if;
  if not has_function_privilege('service_role','integration_control.penta_assignment_bind_release_gate_v1(uuid,text,text,text,text,text,text,text,uuid,text,uuid,jsonb)','EXECUTE') then raise exception 'service_role must retain release-gate binding v1 execution'; end if;
end
$$;

rollback;
