create or replace function integration_control.penta_identity_alias_evidence_reconcile_v1(
  p_source_ref text default 'penta-identity-alias-evidence-reconcile-v1'
) returns jsonb
language plpgsql
security definer
set search_path to 'integration_control','pentamocracy','public','extensions','pg_temp'
as $fn$
declare
  r record;
  v_promoted integer := 0;
  v_activation text;
  v_labels text[];
begin
  for r in
    select a.identity_key,
           bool_or(e.lifecycle_state='production'
                   and coalesce(e.attributes->>'maturity','')='production'
                   and e.source_ref is distinct from 'integration_control.penta_identity_registry_v1') as has_external_production
    from integration_control.penta_identity_aliases_v1 a
    join integration_control.penta_census_entities_v1 e
      on e.entity_key=a.alias_key and e.current
    group by a.identity_key
    having count(distinct a.alias_key)>1
  loop
    if not coalesce(r.has_external_production,false) then
      continue;
    end if;

    select case when family_key='PROVISIONAL_UNASSIGNED' then 'HOLD_FAMILY' else 'ACTIVE' end,
           array(select l from unnest(coalesce(labels,'{}'::text[])) l
                 where l not like 'maturity:%' and l not like 'activation:%' and l not like 'runtime:%')
    into v_activation,v_labels
    from integration_control.penta_identity_registry_v1
    where identity_key=r.identity_key and current;

    if not found then
      continue;
    end if;

    v_labels := v_labels || array['maturity:production','activation:'||lower(v_activation),'runtime:runtime_present'];

    update integration_control.penta_identity_registry_v1
       set maturity='production',
           runtime_state='RUNTIME_PRESENT',
           activation_state=v_activation,
           labels=v_labels,
           source_refs=source_refs || jsonb_build_object('alias_runtime_evidence',p_source_ref),
           metadata=metadata || jsonb_build_object('alias_evidence_reconciled',true,'alias_evidence_source',p_source_ref),
           updated_at=now()
     where identity_key=r.identity_key and current;

    update integration_control.penta_identity_labels_v1
       set active=false,last_seen_at=now()
     where identity_key=r.identity_key and label_class in ('maturity','activation','runtime');

    insert into integration_control.penta_identity_labels_v1(identity_key,label,label_class,source_ref,active)
    values
      (r.identity_key,'maturity:production','maturity',p_source_ref,true),
      (r.identity_key,'activation:'||lower(v_activation),'activation',p_source_ref,true),
      (r.identity_key,'runtime:runtime_present','runtime',p_source_ref,true)
    on conflict(identity_key,label) do update
      set active=true,source_ref=excluded.source_ref,last_seen_at=now();

    update pentamocracy.penta_job_assignments_v1 j
       set activation_state=v_activation,
           metadata=j.metadata || jsonb_build_object('canonical_alias_runtime_evidence',p_source_ref,'canonical_identity_key',r.identity_key)
      from pentamocracy.citizens_v1 c
      join integration_control.penta_identity_aliases_v1 a on a.alias_key=c.penta_identity
     where j.citizen_id=c.citizen_id and c.active and a.identity_key=r.identity_key;

    update integration_control.penta_census_entities_v1
       set lifecycle_state=case when v_activation='ACTIVE' then 'production' else 'hold' end,
           attributes=attributes || jsonb_build_object('maturity','production','runtime_state','RUNTIME_PRESENT','activation_state',v_activation,'alias_evidence_source',p_source_ref),
           last_seen_at=now()
     where current and entity_key=r.identity_key and source_ref='integration_control.penta_identity_registry_v1';

    v_promoted := v_promoted + 1;
  end loop;

  return jsonb_build_object('identities_reconciled',v_promoted,'source_ref',p_source_ref);
end
$fn$;

do $patch$
declare
  v_def text;
  v_anchor constant text := '  insert into integration_control.penta_identity_projection_receipts_v1';
  v_call constant text := '  perform integration_control.penta_identity_alias_evidence_reconcile_v1(p_source_ref);' || E'\n\n' || '  insert into integration_control.penta_identity_projection_receipts_v1';
begin
  v_def := pg_get_functiondef('integration_control.penta_identity_refresh_v1(text)'::regprocedure);
  if strpos(v_def,'perform integration_control.penta_identity_alias_evidence_reconcile_v1(p_source_ref);') > 0 then
    return;
  end if;
  if strpos(v_def,v_anchor)=0 then
    raise exception 'penta_identity_refresh_v1 receipt anchor missing; refusing drifted patch';
  end if;
  execute replace(v_def,v_anchor,v_call);
end
$patch$;
