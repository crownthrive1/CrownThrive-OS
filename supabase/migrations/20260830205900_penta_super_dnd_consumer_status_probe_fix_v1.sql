begin;

-- Follow-up to the consumer-only acceptance conversion.
-- Never register a synthetic PentaDND scope from PentaSuper. Read the canonical scope registry/status instead.
-- Runtime function replacements are CAS-guarded to the exact deployed v4 bodies.

do $repair$
declare
  v_def text;
  v_sha text;
  v_old_call text := $$v_dnd_preflight:=penta_dnd.preflight_v1('penta_super_acceptance_consumer',v_scope,p_actor_ref,'dnd.scope',false,false,false);$$;
  v_new_call text := $$v_dnd_preflight:=penta_dnd.scope_status_v1();$$;
  v_old_assert text := $$coalesce((v_dnd_preflight->>'allowed')::boolean,false) and v_dnd_preflight->>'decision'='PASS_NO_DND_SCOPE'$$;
  v_new_assert text := $$v_dnd_preflight->>'service'='ct.penta.dnd.scope-registry.v1' and coalesce((v_dnd_preflight->>'authority_created')::boolean,true)=false and coalesce((v_dnd_preflight->>'d3_human_reserved')::boolean,false)$$;
begin
  select pg_get_functiondef(p.oid),encode(extensions.digest(convert_to(pg_get_functiondef(p.oid),'UTF8'),'sha256'),'hex')
    into v_def,v_sha
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='penta_task_runtime' and p.proname='run_acceptance_canary_v2';
  if v_sha is distinct from '857690c446eabba19eb24f9a2a622f58cfe0eb8acc6ae70102a62876b021b76a' then
    raise exception 'PENTASUPER_ACCEPTANCE_CANARY_CAS_MISMATCH:%',coalesce(v_sha,'missing');
  end if;
  if position(v_old_call in v_def)=0 or position(v_old_assert in v_def)=0 then
    raise exception 'PENTASUPER_ACCEPTANCE_CANARY_PATCH_TARGET_MISSING';
  end if;
  v_def:=replace(v_def,v_old_call,v_new_call);
  v_def:=replace(v_def,v_old_assert,v_new_assert);
  execute v_def;
end
$repair$;

do $repair$
declare
  v_def text;
  v_sha text;
  v_old_call text := $$v_dnd_preflight:=penta_dnd.preflight_v1('penta_super_full_acceptance_consumer','ct.penta.super.v1:full-matrix-consumer:'||v_run::text,p_actor_ref,'dnd.scope',false,false,false);$$;
  v_new_call text := $$v_dnd_preflight:=penta_dnd.scope_status_v1();$$;
  v_old_assert text := $$coalesce((v_dnd_preflight->>'allowed')::boolean,false) and v_dnd_preflight->>'decision'='PASS_NO_DND_SCOPE'$$;
  v_new_assert text := $$v_dnd_preflight->>'service'='ct.penta.dnd.scope-registry.v1' and coalesce((v_dnd_preflight->>'authority_created')::boolean,true)=false and coalesce((v_dnd_preflight->>'d3_human_reserved')::boolean,false)$$;
begin
  select pg_get_functiondef(p.oid),encode(extensions.digest(convert_to(pg_get_functiondef(p.oid),'UTF8'),'sha256'),'hex')
    into v_def,v_sha
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='penta_task_runtime' and p.proname='run_full_acceptance_matrix_v3';
  if v_sha is distinct from 'a083d816b86594ecc7efabe52ff5fdae3f19384f1d26ade6ea632b693f624cdb' then
    raise exception 'PENTASUPER_FULL_MATRIX_CAS_MISMATCH:%',coalesce(v_sha,'missing');
  end if;
  if position(v_old_call in v_def)=0 or position(v_old_assert in v_def)=0 then
    raise exception 'PENTASUPER_FULL_MATRIX_PATCH_TARGET_MISSING';
  end if;
  v_def:=replace(v_def,v_old_call,v_new_call);
  v_def:=replace(v_def,v_old_assert,v_new_assert);
  execute v_def;
end
$repair$;

revoke all on function penta_task_runtime.run_acceptance_canary_v2(text) from public, anon, authenticated;
revoke all on function penta_task_runtime.run_full_acceptance_matrix_v3(text) from public, anon, authenticated;
grant execute on function penta_task_runtime.run_acceptance_canary_v2(text) to service_role;
grant execute on function penta_task_runtime.run_full_acceptance_matrix_v3(text) to service_role;

commit;
