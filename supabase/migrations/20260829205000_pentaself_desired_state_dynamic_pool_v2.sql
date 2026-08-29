begin;

create or replace function penta_self.enforce_desired_state_v1()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,cron,crm,integration_control,extensions,public,pg_temp
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_contract record;
  v_job record;
  v_checked integer:=0;
  v_repaired integer:=0;
  v_in_sync integer:=0;
  v_failed integer:=0;
  v_rowcount integer:=0;
  v_observed jsonb;
  v_disposition text;
  v_digest text;
  v_payload jsonb;
  v_schedule text;
  v_command text;
  v_expected_active boolean;
  v_failures jsonb:='[]'::jsonb;
  v_pool jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;

  for v_contract in
    select distinct on (contract_key)
      contract_key,generation,contract_kind,target_key,desired_state,
      source_ref,authority_ref,actor_ref,evidence_sha256
    from penta_self.desired_state_contracts_v1
    order by contract_key,generation desc
  loop
    v_checked:=v_checked+1;
    begin
      v_disposition:='in_sync';
      v_observed:='{}'::jsonb;
      v_rowcount:=0;

      if v_contract.contract_kind='cron_job' then
        v_schedule:=v_contract.desired_state->>'schedule';
        v_command:=v_contract.desired_state->>'command';
        v_expected_active:=coalesce((v_contract.desired_state->>'active')::boolean,true);
        if coalesce(v_schedule,'')='' or coalesce(v_command,'')='' then
          raise exception 'invalid_cron_desired_state';
        end if;

        select jsonb_build_object(
          'count',count(*),
          'schedules',coalesce(jsonb_agg(schedule order by jobid),'[]'::jsonb),
          'commands',coalesce(jsonb_agg(command order by jobid),'[]'::jsonb),
          'active',coalesce(jsonb_agg(active order by jobid),'[]'::jsonb)
        ) into v_observed
        from cron.job
        where jobname=v_contract.target_key;

        if v_expected_active then
          if (select count(*) from cron.job where jobname=v_contract.target_key)<>1
             or not exists(
               select 1
               from cron.job
               where jobname=v_contract.target_key
                 and schedule=v_schedule
                 and command=v_command
                 and active
             ) then
            for v_job in select jobid from cron.job where jobname=v_contract.target_key loop
              perform cron.unschedule(v_job.jobid);
            end loop;
            perform cron.schedule(v_contract.target_key,v_schedule,v_command);
            v_disposition:='repaired';
            v_repaired:=v_repaired+1;
          else
            v_in_sync:=v_in_sync+1;
          end if;
        else
          if exists(select 1 from cron.job where jobname=v_contract.target_key) then
            for v_job in select jobid from cron.job where jobname=v_contract.target_key loop
              perform cron.unschedule(v_job.jobid);
            end loop;
            v_disposition:='repaired';
            v_repaired:=v_repaired+1;
          else
            v_in_sync:=v_in_sync+1;
          end if;
        end if;

        insert into penta_self.required_jobs_v1(
          jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata
        ) values(
          v_contract.target_key,
          v_schedule,
          v_command,
          v_expected_active,
          coalesce(v_contract.desired_state->>'risk_class','D1'),
          jsonb_build_object(
            'monotonic_contract_key',v_contract.contract_key,
            'monotonic_generation',v_contract.generation,
            'source_ref',v_contract.source_ref,
            'authority_ref',v_contract.authority_ref,
            'rollback_rule','higher_generation_supersession_only',
            'persistent',true,
            'desired_active',v_expected_active
          )
        )
        on conflict(jobname) do update set
          expected_schedule=excluded.expected_schedule,
          expected_command=excluded.expected_command,
          auto_repair=excluded.auto_repair,
          risk_class=excluded.risk_class,
          metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,
          updated_at=now();

      elsif v_contract.target_key='persona_execution_default' then
        select to_jsonb(x) into v_observed
        from (
          select control_key,active,automation_enabled,kill_switch,
                 max_batch_size,max_attempts,component_version,certification_state
          from crm.penta_persona_execution_control_v1
          where control_key='default'
        ) x;

        update crm.penta_persona_execution_control_v1
        set active=coalesce((v_contract.desired_state->>'active')::boolean,true),
            automation_enabled=coalesce((v_contract.desired_state->>'automation_enabled')::boolean,true),
            kill_switch=coalesce((v_contract.desired_state->>'kill_switch')::boolean,false),
            metadata=metadata||jsonb_build_object(
              'monotonic_contract_key',v_contract.contract_key,
              'monotonic_generation',v_contract.generation,
              'rollback_rule','higher_generation_supersession_only'
            ),
            updated_at=now()
        where control_key='default'
          and (
            active is distinct from coalesce((v_contract.desired_state->>'active')::boolean,true)
            or automation_enabled is distinct from coalesce((v_contract.desired_state->>'automation_enabled')::boolean,true)
            or kill_switch is distinct from coalesce((v_contract.desired_state->>'kill_switch')::boolean,false)
            or case
                 when coalesce(metadata->>'monotonic_generation','')~'^[0-9]+$'
                   then (metadata->>'monotonic_generation')::bigint
                 else 0
               end < v_contract.generation
          );
        get diagnostics v_rowcount=row_count;

      elsif v_contract.target_key='locticians_growth_campaign' then
        select jsonb_build_object(
          'campaign_id',campaign_id,
          'state',state,
          'daily_cap',daily_cap,
          'monthly_cap',monthly_cap,
          'total_cap',total_cap,
          'provider_write_authority',provider_write_authority,
          'money_movement_authority',money_movement_authority,
          'rights_disposition_authority',rights_disposition_authority,
          'credential_authority',credential_authority
        ) into v_observed
        from crm.penta_marketer_campaign_v1
        where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';

        update crm.penta_marketer_campaign_v1
        set state=coalesce(v_contract.desired_state->>'state','active'),
            daily_cap=coalesce((v_contract.desired_state->>'daily_cap')::integer,daily_cap),
            monthly_cap=coalesce((v_contract.desired_state->>'monthly_cap')::integer,monthly_cap),
            total_cap=coalesce((v_contract.desired_state->>'total_cap')::integer,total_cap),
            nonrenewing=coalesce((v_contract.desired_state->>'nonrenewing')::boolean,nonrenewing),
            provider_write_authority=coalesce((v_contract.desired_state->>'provider_write_authority')::boolean,provider_write_authority),
            money_movement_authority=coalesce((v_contract.desired_state->>'money_movement_authority')::boolean,false),
            rights_disposition_authority=coalesce((v_contract.desired_state->>'rights_disposition_authority')::boolean,false),
            credential_authority=coalesce((v_contract.desired_state->>'credential_authority')::boolean,false),
            metadata=(metadata-'daily_cap_restored'-'wave5_gate_state'-'temporary_hourly_ceiling')||jsonb_build_object(
              'monotonic_contract_key',v_contract.contract_key,
              'monotonic_generation',v_contract.generation,
              'rollback_rule','higher_generation_supersession_only',
              'desired_state_driven',true,
              'pool_policy_key',coalesce(v_contract.desired_state->>'pool_policy_key','ct.pentamailer.pool.40k.v1'),
              'pool_policy_generation',coalesce((v_contract.desired_state->>'pool_policy_generation')::bigint,2026082913)
            )
        where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1'
          and (
            lower(state)<>lower(coalesce(v_contract.desired_state->>'state','active'))
            or daily_cap is distinct from coalesce((v_contract.desired_state->>'daily_cap')::integer,daily_cap)
            or monthly_cap is distinct from coalesce((v_contract.desired_state->>'monthly_cap')::integer,monthly_cap)
            or total_cap is distinct from coalesce((v_contract.desired_state->>'total_cap')::integer,total_cap)
            or provider_write_authority is distinct from coalesce((v_contract.desired_state->>'provider_write_authority')::boolean,provider_write_authority)
            or money_movement_authority is distinct from coalesce((v_contract.desired_state->>'money_movement_authority')::boolean,false)
            or rights_disposition_authority is distinct from coalesce((v_contract.desired_state->>'rights_disposition_authority')::boolean,false)
            or credential_authority is distinct from coalesce((v_contract.desired_state->>'credential_authority')::boolean,false)
            or case
                 when coalesce(metadata->>'monotonic_generation','')~'^[0-9]+$'
                   then (metadata->>'monotonic_generation')::bigint
                 else 0
               end < v_contract.generation
          );
        get diagnostics v_rowcount=row_count;

      elsif v_contract.target_key='locticians_queue_watermark' then
        select to_jsonb(x) into v_observed
        from (
          select campaign_id,active,low_watermark,target_depth,plan_batch_limit,
                 spacing_seconds,send_start_local,send_end_local
          from crm.penta_marketer_queue_policy_v1
          where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1'
        ) x;

        update crm.penta_marketer_queue_policy_v1
        set active=coalesce((v_contract.desired_state->>'active')::boolean,true),
            low_watermark=coalesce((v_contract.desired_state->>'low_watermark')::integer,40),
            target_depth=coalesce((v_contract.desired_state->>'target_depth')::integer,80),
            plan_batch_limit=coalesce((v_contract.desired_state->>'plan_batch_limit')::integer,40),
            send_start_local=coalesce((v_contract.desired_state->>'send_start_local')::time,'06:00'::time),
            send_end_local=coalesce((v_contract.desired_state->>'send_end_local')::time,'21:00'::time),
            updated_at=now()
        where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1'
          and (
            active is distinct from coalesce((v_contract.desired_state->>'active')::boolean,true)
            or low_watermark is distinct from coalesce((v_contract.desired_state->>'low_watermark')::integer,40)
            or target_depth is distinct from coalesce((v_contract.desired_state->>'target_depth')::integer,80)
            or plan_batch_limit is distinct from coalesce((v_contract.desired_state->>'plan_batch_limit')::integer,40)
            or send_start_local is distinct from coalesce((v_contract.desired_state->>'send_start_local')::time,'06:00'::time)
            or send_end_local is distinct from coalesce((v_contract.desired_state->>'send_end_local')::time,'21:00'::time)
          );
        get diagnostics v_rowcount=row_count;

      elsif v_contract.target_key='pentamail_growth_policy' then
        select jsonb_build_object(
          'policy_key',policy_key,
          'provider_monthly_cap',provider_monthly_cap,
          'marketing_monthly_cap',marketing_monthly_cap,
          'controlled_batch_per_minute',controlled_batch_per_minute,
          'state',state,
          'temporary_authorization_ceiling',crownthrive_temporary_authorization_ceiling,
          'provider_limit_removed_at',provider_limit_removed_at
        ) into v_observed
        from integration_control.penta_mail_growth_policy_v1
        where policy_key='mailgun-foundation-growth-v1';

        v_pool:=integration_control.penta_mail_pool_reconcile_v2();
        v_rowcount:=case when coalesce((v_pool->>'changed')::boolean,false) then 1 else 0 end;
        v_observed:=coalesce(v_observed,'{}'::jsonb)||jsonb_build_object('pool_reconcile',v_pool);

      else
        raise exception 'unsupported_control_target:%',v_contract.target_key;
      end if;

      if v_contract.contract_kind<>'cron_job' then
        if v_rowcount>0 then
          v_disposition:='repaired';
          v_repaired:=v_repaired+1;
        else
          v_disposition:='in_sync';
          v_in_sync:=v_in_sync+1;
        end if;
      end if;

      v_payload:=jsonb_build_object(
        'contract_key',v_contract.contract_key,
        'generation',v_contract.generation,
        'target_key',v_contract.target_key,
        'observed_state',coalesce(v_observed,'{}'::jsonb),
        'desired_state',v_contract.desired_state,
        'disposition',v_disposition,
        'source_ref',v_contract.source_ref,
        'authority_ref',v_contract.authority_ref,
        'observed_at',now()
      );
      v_digest:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');

      insert into penta_self.desired_state_receipts_v1(
        contract_key,generation,target_key,observed_state,desired_state,disposition,evidence_sha256
      ) values(
        v_contract.contract_key,
        v_contract.generation,
        v_contract.target_key,
        coalesce(v_observed,'{}'::jsonb),
        v_contract.desired_state,
        v_disposition,
        v_digest
      );

    exception when others then
      v_failed:=v_failed+1;
      v_payload:=jsonb_build_object(
        'contract_key',v_contract.contract_key,
        'generation',v_contract.generation,
        'target_key',v_contract.target_key,
        'desired_state',v_contract.desired_state,
        'disposition','failed',
        'sqlstate',sqlstate,
        'error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex'),
        'observed_at',now()
      );
      v_digest:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');

      insert into penta_self.desired_state_receipts_v1(
        contract_key,generation,target_key,observed_state,desired_state,disposition,evidence_sha256
      ) values(
        v_contract.contract_key,
        v_contract.generation,
        v_contract.target_key,
        jsonb_build_object('sqlstate',sqlstate,'error_sha256',v_payload->>'error_sha256'),
        v_contract.desired_state,
        'failed',
        v_digest
      );

      v_failures:=v_failures||jsonb_build_array(jsonb_build_object(
        'contract_key',v_contract.contract_key,
        'target_key',v_contract.target_key,
        'sqlstate',sqlstate,
        'error_sha256',v_payload->>'error_sha256'
      ));
    end;
  end loop;

  return jsonb_build_object(
    'service','ct.penta.self.monotonic-desired-state.v2',
    'state',case when v_failed=0 then 'healthy' else 'degraded' end,
    'contracts_checked',v_checked,
    'in_sync',v_in_sync,
    'repaired',v_repaired,
    'failed',v_failed,
    'failures',v_failures,
    'rollback_rule','higher_generation_supersession_only',
    'desired_state_driven',true,
    'observed_at',now()
  );
end;
$$;

commit;
