do $migration$
declare
  v_def text;
  v_old text := $old$      else
        raise exception 'unsupported_control_target:%',v_contract.target_key;
      end if;$old$;
  v_new text := $new$      elsif v_contract.target_key='crown_affiliates_cos_bridge' then
        select jsonb_build_object(
          'service_exists',s.service_id is not null,
          'service_id',s.service_id,
          'service_integration_state',s.integration_state,
          'service_version',s.metadata->>'version',
          'service_contract',s.metadata->>'contract',
          'application_uuid',s.metadata->>'application_uuid',
          'authority_ceiling',s.metadata->>'authority_ceiling',
          'provider_write',coalesce((s.metadata->>'provider_writes_enabled')::boolean,false),
          'money_movement',coalesce((s.metadata->>'money_movement_enabled')::boolean,false),
          'd3_effect',coalesce((s.metadata->>'d3_effect_enabled')::boolean,false),
          'secret_values_exposed',coalesce((s.metadata->>'secret_values_exposed')::boolean,false),
          'wire_binding_state',b.binding_state,
          'wire_gap_state',b.gap_state,
          'wire_integration_state',b.current_integration_state,
          'system_exists',ps.system_key is not null,
          'system_maturity',ps.maturity,
          'system_risk_ceiling',ps.risk_ceiling,
          'system_application_uuid',ps.metadata->>'cos_application_uuid',
          'system_contract',ps.metadata->>'cos_bridge_contract',
          'system_capability_prefix',ps.metadata->>'cos_capability_prefix',
          'chlom_exists',ci.system_id is not null,
          'chlom_lifecycle_state',ci.lifecycle_state,
          'chlom_read_state',ci.read_state,
          'chlom_identity_subject_id',ci.identity_subject_id,
          'capability_count',coalesce((select count(*) from jsonb_array_elements_text(coalesce(s.metadata->'capabilities','[]'::jsonb))),0),
          'capability_prefix_mismatch_count',coalesce((select count(*) from jsonb_array_elements_text(coalesce(s.metadata->'capabilities','[]'::jsonb)) c where c not like (v_contract.desired_state->>'required_capability_prefix')||'%'),0),
          'runtime_boundary','external_phase_gate'
        ) into v_observed
        from integration_control.services s
        left join integration_control.penta_wire_service_bindings_v1 b on b.service_id=s.service_id
        left join public.penta_system_registry ps on ps.system_key=(v_contract.desired_state->>'system_key')
        left join chlom_runtime.interop_system_registry ci on ci.system_id=(v_contract.desired_state->>'system_key')
        where s.service_id=v_contract.target_key;

        if v_observed is null
           or coalesce((v_observed->>'service_exists')::boolean,false) is not true
           or v_observed->>'service_integration_state' is distinct from v_contract.desired_state->>'integration_state'
           or v_observed->>'service_version' is distinct from v_contract.desired_state->>'version'
           or v_observed->>'service_contract' is distinct from v_contract.desired_state->>'contract'
           or v_observed->>'application_uuid' is distinct from v_contract.desired_state->>'application_uuid'
           or v_observed->>'authority_ceiling' is distinct from v_contract.desired_state->>'authority_ceiling'
           or coalesce((v_observed->>'provider_write')::boolean,true) is distinct from coalesce((v_contract.desired_state->>'provider_write')::boolean,false)
           or coalesce((v_observed->>'money_movement')::boolean,true) is distinct from coalesce((v_contract.desired_state->>'money_movement')::boolean,false)
           or coalesce((v_observed->>'d3_effect')::boolean,true) is distinct from coalesce((v_contract.desired_state->>'d3_effect')::boolean,false)
           or coalesce((v_observed->>'secret_values_exposed')::boolean,true)
           or v_observed->>'wire_binding_state' is distinct from v_contract.desired_state->>'wire_binding_state'
           or v_observed->>'wire_gap_state' is distinct from v_contract.desired_state->>'wire_gap_state'
           or coalesce((v_observed->>'system_exists')::boolean,false) is not true
           or v_observed->>'system_maturity' is distinct from v_contract.desired_state->>'lifecycle_state'
           or v_observed->>'system_risk_ceiling' is distinct from v_contract.desired_state->>'authority_ceiling'
           or v_observed->>'system_application_uuid' is distinct from v_contract.desired_state->>'application_uuid'
           or v_observed->>'system_contract' is distinct from v_contract.desired_state->>'contract'
           or v_observed->>'system_capability_prefix' is distinct from v_contract.desired_state->>'required_capability_prefix'
           or coalesce((v_observed->>'chlom_exists')::boolean,false) is not true
           or v_observed->>'chlom_lifecycle_state' is distinct from 'active'
           or v_observed->>'chlom_read_state' is distinct from 'verified'
           or v_observed->>'chlom_identity_subject_id' is distinct from 'urn:uuid:'||(v_contract.desired_state->>'application_uuid')
           or coalesce((v_observed->>'capability_count')::integer,0) < 1
           or coalesce((v_observed->>'capability_prefix_mismatch_count')::integer,1) <> 0
        then
          raise exception 'crown_affiliates_cos_bridge_drift';
        end if;
      else
        raise exception 'unsupported_control_target:%',v_contract.target_key;
      end if;$new$;
begin
  select pg_get_functiondef('penta_self.enforce_desired_state_v1()'::regprocedure) into v_def;
  if position($needle$elsif v_contract.target_key='crown_affiliates_cos_bridge'$needle$ in v_def)=0 then
    if position(v_old in v_def)=0 then
      raise exception 'phase01_patch_anchor_not_found';
    end if;
    execute replace(v_def,v_old,v_new);
  end if;
end
$migration$;