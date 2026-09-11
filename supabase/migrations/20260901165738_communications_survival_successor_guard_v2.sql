-- Repair explicit JSONB operator precedence in the Communications Survival successor comparator.
-- Generation 1 runtime behavior is unchanged; this only makes future strictly-better admission testable.

create or replace function integration_control.guard_communications_survival_contract_insert_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','extensions'
as $function$
declare
  v_computed_sha text;
  v_prev integration_control.communications_survival_contract_versions_v1%rowtype;
  v_has_prev boolean:=false;
  v_key text;
  v_old_rank integer;
  v_new_rank integer;
  v_old_safety_rank bigint;
  v_new_safety_rank bigint;
  v_max_keys constant text[]:=array[
    'planner_max_silence_seconds','scheduler_max_silence_seconds',
    'provider_probe_max_age_seconds','capability_probe_max_age_seconds',
    'outbox_stale_seconds','terminal_projection_stale_seconds',
    'max_auth_failovers','max_cursor_resets','max_ambiguous_resends'
  ];
begin
  v_computed_sha:=encode(extensions.digest(convert_to(new.policy::text,'UTF8'),'sha256'),'hex');
  if new.contract_key<>'ct.communications.survival.v1' then
    raise exception using errcode='55000',message='communications_survival_contract_key_rejected';
  end if;
  if new.policy_sha256 is distinct from v_computed_sha then
    raise exception using errcode='55000',message='communications_survival_policy_sha_mismatch';
  end if;
  if jsonb_typeof(new.policy->'stages')<>'array'
     or jsonb_typeof(new.policy->'invariants')<>'object'
     or jsonb_typeof(new.policy->'thresholds')<>'object'
     or jsonb_typeof(new.policy->'tests')<>'object' then
    raise exception using errcode='55000',message='communications_survival_policy_shape_rejected';
  end if;

  foreach v_key in array array[
    'acquisition','research','promotion','eligibility','scheduling','outbox',
    'provider_transport','provider_readback','terminal_projection','reply_suppression'
  ] loop
    if not (new.policy->'stages' @> jsonb_build_array(v_key)) then
      raise exception using errcode='55000',message='communications_survival_required_stage_missing:'||v_key;
    end if;
  end loop;

  foreach v_key in array array[
    'penta_mail_is_sole_transport','penta_mailer_is_transport_subcomponent',
    'final_eligibility_required','suppression_required','authority_required',
    'provider_readback_required','ambiguous_outcome_no_blind_retry',
    'gmail_outlook_send_fallback_forbidden','credential_presence_not_health',
    'capability_specific_provider_health','credential_hopping_on_429_forbidden',
    'flow_health_required','no_silent_green','append_only_repair_evidence',
    'destructive_repair_forbidden','d3_human_reserved'
  ] loop
    if coalesce((new.policy->'invariants'->>v_key)::boolean,false) is not true then
      raise exception using errcode='55000',message='communications_survival_required_invariant_missing_or_false:'||v_key;
    end if;
  end loop;

  foreach v_key in array array[
    'scheduler_restore','stale_cursor_recovery','unsafe_ready_quarantine',
    'final_eligibility','mailgun_readback','terminal_projection',
    'ambiguous_outcome_no_blind_retry','no_direct_send'
  ] loop
    if coalesce((new.policy->'tests'->>v_key)::boolean,false) is not true then
      raise exception using errcode='55000',message='communications_survival_required_test_missing_or_false:'||v_key;
    end if;
  end loop;

  foreach v_key in array v_max_keys loop
    if nullif(new.policy->'thresholds'->>v_key,'') is null then
      raise exception using errcode='55000',message='communications_survival_threshold_missing:'||v_key;
    end if;
  end loop;

  if nullif(new.policy->'thresholds'->>'queue_low_watermark','') is null
     or nullif(new.policy->'thresholds'->>'queue_target_depth','') is null
     or nullif(new.policy->>'safety_rank','') is null then
    raise exception using errcode='55000',message='communications_survival_quality_fields_missing';
  end if;

  if (new.policy->'thresholds'->>'planner_max_silence_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'scheduler_max_silence_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'provider_probe_max_age_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'capability_probe_max_age_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'outbox_stale_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'terminal_projection_stale_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'queue_low_watermark')::bigint<=0
     or (new.policy->'thresholds'->>'queue_target_depth')::bigint < (new.policy->'thresholds'->>'queue_low_watermark')::bigint
     or (new.policy->'thresholds'->>'max_auth_failovers')::bigint not between 0 and 1
     or (new.policy->'thresholds'->>'max_cursor_resets')::bigint not between 0 and 1
     or (new.policy->'thresholds'->>'max_ambiguous_resends')::bigint<>0
     or (new.policy->>'safety_rank')::bigint<=0 then
    raise exception using errcode='55000',message='communications_survival_thresholds_rejected';
  end if;

  select * into v_prev
  from integration_control.communications_survival_contract_versions_v1
  where contract_key=new.contract_key order by generation desc limit 1;
  v_has_prev:=found;

  if not v_has_prev then
    if new.generation<>1 or new.predecessor_sha256 is not null then
      raise exception using errcode='55000',message='communications_survival_initial_generation_rejected';
    end if;
  else
    if new.generation<=v_prev.generation then
      raise exception using errcode='55000',message='communications_survival_non_monotonic_generation_rejected';
    end if;
    if new.predecessor_sha256 is distinct from v_prev.policy_sha256 then
      raise exception using errcode='55000',message='communications_survival_predecessor_mismatch';
    end if;
    if not ((v_prev.policy->'stages') <@ (new.policy->'stages')) then
      raise exception using errcode='55000',message='communications_survival_stage_regression_rejected';
    end if;
    for v_key in
      select e.key
      from jsonb_each(v_prev.policy->'invariants') as e(key,value)
      where e.value='true'::jsonb
    loop
      if coalesce((new.policy->'invariants'->>v_key)::boolean,false) is not true then
        raise exception using errcode='55000',message='communications_survival_invariant_regression_rejected:'||v_key;
      end if;
    end loop;
    foreach v_key in array v_max_keys loop
      if (new.policy->'thresholds'->>v_key)::bigint > (v_prev.policy->'thresholds'->>v_key)::bigint then
        raise exception using errcode='55000',message='communications_survival_threshold_regression_rejected:'||v_key;
      end if;
    end loop;
    v_old_safety_rank:=(v_prev.policy->>'safety_rank')::bigint;
    v_new_safety_rank:=(new.policy->>'safety_rank')::bigint;
    if v_new_safety_rank<=v_old_safety_rank then
      raise exception using errcode='55000',message='communications_survival_safety_rank_must_increase';
    end if;
    v_old_rank:=case v_prev.authority_ceiling when 'D0' then 0 when 'D1' then 1 else 2 end;
    v_new_rank:=case new.authority_ceiling when 'D0' then 0 when 'D1' then 1 else 2 end;
    if v_new_rank>v_old_rank then
      raise exception using errcode='55000',message='communications_survival_authority_expansion_rejected';
    end if;
  end if;
  return new;
end;
$function$;