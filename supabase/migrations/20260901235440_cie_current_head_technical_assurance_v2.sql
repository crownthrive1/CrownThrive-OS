do $migration$
declare
  v_def text;
  v_after text;
  v_pre_sha text;
  v_post_sha text;
  v_old_integrity text := E'  if v_activation_parent !~ ''^[0-9a-f]{40}$''\n     or v_activation_child !~ ''^[0-9a-f]{40}$''\n     or v_activation_child <> p_child_head\n     or v_activation_request is distinct from v_prod.founder_request_id::text\n     or v_prod.exact_version_ref is distinct from v_pkg.metadata->>''production_exact_version_ref''\n     or v_prod.content_sha256 is distinct from v_pkg.metadata->>''production_content_sha256'' then\n    raise exception ''production_authority_snapshot_integrity_failure'';\n  end if;';
  v_new_integrity text := E'  if v_activation_parent !~ ''^[0-9a-f]{40}$''\n     or v_activation_child !~ ''^[0-9a-f]{40}$''\n     or v_activation_request is distinct from v_prod.founder_request_id::text\n     or v_prod.exact_version_ref is distinct from v_pkg.metadata->>''production_exact_version_ref''\n     or v_prod.content_sha256 is distinct from v_pkg.metadata->>''production_content_sha256'' then\n    raise exception ''production_authority_snapshot_integrity_failure'';\n  end if;';
  v_old_compare text := E'  if coalesce(p_evidence->>''github_compare_status'','''') <> ''ahead''\n     or coalesce(p_evidence->>''github_compare_base_sha'','''') <> v_activation_parent\n     or coalesce(p_evidence->>''github_compare_head_sha'','''') <> p_parent_head\n     or coalesce((p_evidence->>''github_compare_behind_by'')::integer,-1) <> 0\n     or coalesce((p_evidence->>''github_compare_ahead_by'')::integer,0) < 1 then\n    raise exception ''github_descendant_evidence_required'';\n  end if;';
  v_new_compare text := E'  if coalesce(p_evidence#>>''{parent_compare,status}'',p_evidence->>''github_compare_status'','''') not in (''ahead'',''identical'')\n     or coalesce(p_evidence#>>''{parent_compare,base_sha}'',p_evidence->>''github_compare_base_sha'','''') <> v_activation_parent\n     or coalesce(p_evidence#>>''{parent_compare,head_sha}'',p_evidence->>''github_compare_head_sha'','''') <> p_parent_head\n     or coalesce((coalesce(p_evidence#>>''{parent_compare,behind_by}'',p_evidence->>''github_compare_behind_by''))::integer,-1) <> 0\n     or (coalesce(p_evidence#>>''{parent_compare,status}'',p_evidence->>''github_compare_status'','''')=''ahead''\n         and coalesce((coalesce(p_evidence#>>''{parent_compare,ahead_by}'',p_evidence->>''github_compare_ahead_by''))::integer,0) < 1)\n     or coalesce(p_evidence#>>''{child_compare,status}'','''') not in (''ahead'',''identical'')\n     or coalesce(p_evidence#>>''{child_compare,base_sha}'','''') <> v_activation_child\n     or coalesce(p_evidence#>>''{child_compare,head_sha}'','''') <> p_child_head\n     or coalesce((p_evidence#>>''{child_compare,behind_by}'')::integer,-1) <> 0\n     or (coalesce(p_evidence#>>''{child_compare,status}'','''')=''ahead''\n         and coalesce((p_evidence#>>''{child_compare,ahead_by}'')::integer,0) < 1) then\n    raise exception ''github_parent_child_descendant_evidence_required'';\n  end if;';
  v_old_evidence text := E'      ''production_authority_rewritten'',false,\n      ''operational_activation'',false,\n      ''authority_effect'',false,';
  v_new_evidence text := E'      ''production_authority_rewritten'',false,\n      ''package_production_authority_rewritten'',false,\n      ''technical_assurance_only'',true,\n      ''operational_activation'',false,\n      ''authority_effect'',false,';
begin
  select pg_get_functiondef(p.oid) into v_def
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='refresh_cie_parent_child_production_assurance_v1'
    and pg_get_function_identity_arguments(p.oid)='p_parent_head text, p_child_head text, p_link_contract_sha256 text, p_source_ref text, p_evidence jsonb';
  if v_def is null then raise exception 'cie_refresh_assurance_v1_missing'; end if;
  v_pre_sha := encode(extensions.digest(convert_to(v_def,'UTF8'),'sha256'),'hex');
  if v_pre_sha <> '0f11c868f06e32afa2ccc83c8dbb905d0b130bdeae16f2c73aabbb693c779da7' then
    raise exception 'cie_refresh_assurance_prestate_mismatch:%',v_pre_sha;
  end if;
  if position(v_old_integrity in v_def)=0 or position(v_old_compare in v_def)=0 or position(v_old_evidence in v_def)=0 then
    raise exception 'cie_refresh_assurance_patch_anchor_missing';
  end if;
  v_after := replace(replace(replace(v_def,v_old_integrity,v_new_integrity),v_old_compare,v_new_compare),v_old_evidence,v_new_evidence);
  execute v_after;
  select pg_get_functiondef(p.oid) into v_after
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='refresh_cie_parent_child_production_assurance_v1'
    and pg_get_function_identity_arguments(p.oid)='p_parent_head text, p_child_head text, p_link_contract_sha256 text, p_source_ref text, p_evidence jsonb';
  v_post_sha := encode(extensions.digest(convert_to(v_after,'UTF8'),'sha256'),'hex');
  if v_post_sha=v_pre_sha then raise exception 'cie_refresh_assurance_patch_noop'; end if;
  if position('github_parent_child_descendant_evidence_required' in v_after)=0 or position('technical_assurance_only' in v_after)=0 then
    raise exception 'cie_refresh_assurance_poststate_validation_failed';
  end if;
end
$migration$;
