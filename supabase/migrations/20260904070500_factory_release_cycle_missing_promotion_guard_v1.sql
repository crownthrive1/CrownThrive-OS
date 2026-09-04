create or replace function integration_control.penta_factory_pressure_catalog_promotion_counts_v1()
returns jsonb
language plpgsql
stable
security definer
set search_path to 'pg_catalog','integration_control'
as $$
declare
  v_total bigint:=0;
  v_ready bigint:=0;
  v_published bigint:=0;
begin
  if to_regclass('integration_control.penta_factory_pressure_catalog_promotions_v1') is null then
    return jsonb_build_object('relation_present',false,'total',0,'release_ready',0,'published',0,'state','HOLD_FACTORY_CATALOG_PROMOTION_BINDING_MISSING');
  end if;
  execute 'select count(*),count(*) filter(where promotion_state in (''release_ready'',''published'')),count(*) filter(where promotion_state=''published'') from integration_control.penta_factory_pressure_catalog_promotions_v1'
    into v_total,v_ready,v_published;
  return jsonb_build_object('relation_present',true,'total',v_total,'release_ready',v_ready,'published',v_published,'state','PASS');
end;
$$;

DO $$
declare
  v_def text;
  v_old text;
  v_new text;
begin
  select pg_get_functiondef(p.oid) into v_def
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control' and p.proname='penta_factory_pressure_release_cycle_v1' and p.prokind='f';
  if v_def is null then raise exception 'release_cycle_not_found'; end if;

  v_old := E'  begin v_promotion:=integration_control.penta_factory_pressure_promote_catalog_v1(1);\n  exception when others then v_promotion:=jsonb_build_object(''state'',''WORKING'',''error_code'',sqlstate,''error_sha256'',encode(extensions.digest(convert_to(sqlstate||'':''||sqlerrm,''UTF8''),''sha256''),''hex'')); end;';
  v_new := E'  if to_regprocedure(''integration_control.penta_factory_pressure_promote_catalog_v1(integer)'') is null then\n    v_promotion:=jsonb_build_object(''state'',''WORKING'',''hold_code'',''HOLD_FACTORY_CATALOG_PROMOTION_BINDING_MISSING'',''promotion_function_present'',false,''provider_write'',false);\n  else\n    begin execute ''select integration_control.penta_factory_pressure_promote_catalog_v1($1)'' into v_promotion using 1;\n    exception when others then v_promotion:=jsonb_build_object(''state'',''WORKING'',''error_code'',sqlstate,''error_sha256'',encode(extensions.digest(convert_to(sqlstate||'':''||sqlerrm,''UTF8''),''sha256''),''hex'')); end;\n  end if;';
  if position(v_old in v_def)=0 then raise exception 'promotion_call_fragment_not_found'; end if;
  v_def:=replace(v_def,v_old,v_new);

  v_old := E'  update integration_control.penta_factory_pressure_catalog_promotions_v1 p\n  set candidate_id=c.candidate_id,\n      promotion_state=case when c.candidate_state=''published'' then ''published''\n                           when c.candidate_state=''admitted'' then ''release_ready''\n                           else ''candidate_seeded'' end,\n      provider_readback_state=case when c.candidate_state in (''admitted'',''published'') then ''pass'' else ''working'' end,\n      updated_at=clock_timestamp()\n  from integration_control.thriveevergreen_publisher_candidates_v2 c\n  where c.release_id=p.governed_release_id and c.offer_code=p.offer_code\n    and c.asset_version_id=p.asset_version_id\n    and c.exact_version_ref=p.exact_version_ref and c.content_sha256=p.content_sha256\n    and p.promotion_state<>''failed'';';
  v_new := E'  if to_regclass(''integration_control.penta_factory_pressure_catalog_promotions_v1'') is not null then\n    execute $q$update integration_control.penta_factory_pressure_catalog_promotions_v1 p\n      set candidate_id=c.candidate_id,\n          promotion_state=case when c.candidate_state=''published'' then ''published'' when c.candidate_state=''admitted'' then ''release_ready'' else ''candidate_seeded'' end,\n          provider_readback_state=case when c.candidate_state in (''admitted'',''published'') then ''pass'' else ''working'' end,\n          updated_at=clock_timestamp()\n      from integration_control.thriveevergreen_publisher_candidates_v2 c\n      where c.release_id=p.governed_release_id and c.offer_code=p.offer_code and c.asset_version_id=p.asset_version_id\n        and c.exact_version_ref=p.exact_version_ref and c.content_sha256=p.content_sha256 and p.promotion_state<>''failed''$q$;\n  else\n    v_promotion:=coalesce(v_promotion,''{}''::jsonb)||jsonb_build_object(''state'',''WORKING'',''hold_code'',''HOLD_FACTORY_CATALOG_PROMOTION_BINDING_MISSING'',''promotion_relation_present'',false);\n  end if;';
  if position(v_old in v_def)=0 then raise exception 'promotion_update_fragment_not_found'; end if;
  v_def:=replace(v_def,v_old,v_new);

  v_def:=replace(v_def,E'''catalog_promotions_total'',(select count(*) from integration_control.penta_factory_pressure_catalog_promotions_v1),\n    ''catalog_promotions_release_ready'',(select count(*) from integration_control.penta_factory_pressure_catalog_promotions_v1 where promotion_state in (''release_ready'',''published'')),\n    ''catalog_promotions_published'',(select count(*) from integration_control.penta_factory_pressure_catalog_promotions_v1 where promotion_state=''published''),',E'''catalog_promotions_total'',coalesce((integration_control.penta_factory_pressure_catalog_promotion_counts_v1()->>''total'')::bigint,0),\n    ''catalog_promotions_release_ready'',coalesce((integration_control.penta_factory_pressure_catalog_promotion_counts_v1()->>''release_ready'')::bigint,0),\n    ''catalog_promotions_published'',coalesce((integration_control.penta_factory_pressure_catalog_promotion_counts_v1()->>''published'')::bigint,0),');
  v_def:=replace(v_def,E'''readback'',''pass'',v_evidence',E'''readback'',case when coalesce(v_promotion->>''state'',''PASS'')=''PASS'' then ''pass'' else ''working'' end,v_evidence');
  v_def:=replace(v_def,E'return v_evidence||jsonb_build_object(''state'',''PASS'',''evidence_sha256'',v_sha);',E'return v_evidence||jsonb_build_object(''state'',case when coalesce(v_promotion->>''state'',''PASS'')=''PASS'' then ''PASS'' else ''WORKING'' end,''evidence_sha256'',v_sha);');
  execute v_def;
end $$;