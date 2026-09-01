-- CrownThrive COS V1 certifier treasury latest-pass hot-path repair v1
-- PentaSELF problem: 54442882-e399-4a3e-ab1f-53f176ed7ff7
--
-- Goal: preserve exact COS status semantics while eliminating the full-history
-- DAIL scan used only to locate the latest penta.treasury.current_budget.pass.
-- DAIL sequence_id is the canonical append order, so a backward primary-key
-- scan with LIMIT 1 is equivalent for "latest appended matching event" and
-- avoids holding certification/convergence work on a 1M+ row scan.
--
-- Fail closed: this migration applies only to the exact predecessor function
-- digest observed for the active COS release-candidate dependency manifest.
-- It creates no certification, release, provider-write, money, rights, vote,
-- quorum, credential, D3, or authority expansion.
--
-- Rollback: restore the exact predecessor public.cos_v1_status_v3() definition
-- whose SHA-256 is 2317f42274645eb7d3963514f0fa89c372ba3aa98a12e5ef601574db58913bac.

do $repair$
declare
  v_definition text;
  v_original_definition text;
  v_predecessor_sha256 text;
  v_result_sha256 text;
  v_old_fragment constant text := $$  select max(created_at) into v_treasury_last_pass
  from chlom_runtime.dail_events where event_type='penta.treasury.current_budget.pass';$$;
  v_new_fragment constant text := $$  select created_at into v_treasury_last_pass
  from chlom_runtime.dail_events
  where event_type='penta.treasury.current_budget.pass'
  order by sequence_id desc
  limit 1;$$;
begin
  select pg_get_functiondef('public.cos_v1_status_v3()'::regprocedure)
    into v_definition;
  v_original_definition := v_definition;

  v_predecessor_sha256 := encode(extensions.digest(v_definition, 'sha256'), 'hex');
  if v_predecessor_sha256 <> '2317f42274645eb7d3963514f0fa89c372ba3aa98a12e5ef601574db58913bac' then
    raise exception 'cos_v1_status_v3 predecessor drift: expected %, found %',
      '2317f42274645eb7d3963514f0fa89c372ba3aa98a12e5ef601574db58913bac',
      v_predecessor_sha256;
  end if;

  if position(v_old_fragment in v_definition) = 0 then
    raise exception 'expected COS treasury latest-pass scan fragment is absent';
  end if;

  v_definition := replace(v_definition, v_old_fragment, v_new_fragment);
  if v_definition = v_original_definition then
    raise exception 'COS treasury latest-pass repair produced no definition change';
  end if;
  if position(v_old_fragment in v_definition) <> 0 then
    raise exception 'COS treasury latest-pass repair left predecessor fragment behind';
  end if;

  execute v_definition;

  select encode(extensions.digest(pg_get_functiondef('public.cos_v1_status_v3()'::regprocedure), 'sha256'), 'hex')
    into v_result_sha256;
  if v_result_sha256 = v_predecessor_sha256 then
    raise exception 'COS treasury latest-pass function digest did not change';
  end if;
end
$repair$;

comment on function public.cos_v1_status_v3() is
  'COS V1 convergence/status v3. Treasury latest-pass lookup uses canonical DAIL sequence ordering with backward primary-key scan; repair lineage problem 54442882-e399-4a3e-ab1f-53f176ed7ff7.';
