-- CrownThrive COS V1 sprint certifier critical-path repair.
-- Certification previously invoked the full mutation-heavy convergence cycle
-- synchronously before reading status, even though v_cycle is not used in the
-- certification decision. This created broad writes, provider/census refreshes
-- and DAIL contention inside the certifier transaction.
-- Convergence remains owned by its native cycle; certification now evaluates
-- current materialized truth and holds naturally when that truth is stale.
-- Rollback: restore predecessor function digest from source history.

do $repair$
declare
  v_definition text;
  v_pre_sha text;
  v_post_sha text;
  v_old constant text := $$  begin v_cycle:=public.cos_v1_convergence_cycle_v3();
  exception when others then
    v_component_errors:=v_component_errors||jsonb_build_array(jsonb_build_object(
      'component','cos_convergence_cycle','sqlstate',sqlstate,
      'error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex')));
  end;$$;
  v_new constant text := $$  v_cycle:=jsonb_build_object(
    'ok',true,
    'state','externalized_from_certifier',
    'cycle_mode','native_convergence_owner',
    'step_failures','[]'::jsonb,
    'certifier_synchronous_mutation',false,
    'reason','certification evaluates current materialized truth; convergence runs outside certifier critical path');$$;
begin
  select pg_get_functiondef('public.cos_v1_certify_v2(text,text,boolean)'::regprocedure)
    into v_definition;
  v_pre_sha := encode(extensions.digest(v_definition,'sha256'),'hex');
  if v_pre_sha <> '7cfdfde47d787fc2fc4dd90ea2c0a5b311b160a568b7b6b499ffbe66b2352ac1' then
    raise exception 'cos_v1_certify_v2 predecessor drift: expected %, found %',
      '7cfdfde47d787fc2fc4dd90ea2c0a5b311b160a568b7b6b499ffbe66b2352ac1', v_pre_sha;
  end if;
  if position(v_old in v_definition)=0 then
    raise exception 'expected synchronous convergence fragment absent';
  end if;
  v_definition := replace(v_definition,v_old,v_new);
  execute v_definition;
  select encode(extensions.digest(pg_get_functiondef('public.cos_v1_certify_v2(text,text,boolean)'::regprocedure),'sha256'),'hex')
    into v_post_sha;
  if v_post_sha=v_pre_sha then raise exception 'certifier decoupling produced no function change'; end if;
end
$repair$;

comment on function public.cos_v1_certify_v2(text,text,boolean) is
  'COS V1 certification v2. Evaluates current materialized truth without running mutation-heavy convergence inline; native convergence remains separately owned. Final DAIL append remains bounded to certification result.';
