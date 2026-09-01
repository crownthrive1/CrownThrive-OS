do $migration$
declare
  v_def text;
  v_after text;
  v_pre_sha text;
  v_post_sha text;
  v_old_decl text := E'  v_parent_descendant_ok boolean := false;\n  v_activation_parent text;';
  v_new_decl text := E'  v_parent_descendant_ok boolean := false;\n  v_child_descendant_ok boolean := false;\n  v_activation_parent text;';
  v_old_parent text := E'  v_parent_descendant_ok := case\n    when p_expected_parent_head=v_activation_parent then true\n    else coalesce(v_link.evidence->>''github_compare_status'','''')=''ahead''\n      and v_link.evidence->>''github_compare_base_sha''=v_activation_parent\n      and v_link.evidence->>''github_compare_head_sha''=p_expected_parent_head\n      and coalesce((v_link.evidence->>''github_compare_behind_by'')::integer,-1)=0\n      and coalesce((v_link.evidence->>''github_compare_ahead_by'')::integer,0)>=1\n  end;';
  v_new_parent text := E'  v_parent_descendant_ok := case\n    when p_expected_parent_head=v_activation_parent then true\n    else coalesce(v_link.evidence#>>''{parent_compare,status}'',v_link.evidence->>''github_compare_status'','''') in (''ahead'',''identical'')\n      and coalesce(v_link.evidence#>>''{parent_compare,base_sha}'',v_link.evidence->>''github_compare_base_sha'')=v_activation_parent\n      and coalesce(v_link.evidence#>>''{parent_compare,head_sha}'',v_link.evidence->>''github_compare_head_sha'')=p_expected_parent_head\n      and coalesce((coalesce(v_link.evidence#>>''{parent_compare,behind_by}'',v_link.evidence->>''github_compare_behind_by''))::integer,-1)=0\n      and (\n        coalesce(v_link.evidence#>>''{parent_compare,status}'',v_link.evidence->>''github_compare_status'','''')=''identical''\n        or coalesce((coalesce(v_link.evidence#>>''{parent_compare,ahead_by}'',v_link.evidence->>''github_compare_ahead_by''))::integer,0)>=1\n      )\n  end;\n\n  v_child_descendant_ok := case\n    when p_expected_child_head=v_pkg.metadata->>''production_child_head'' then true\n    else coalesce(v_link.evidence#>>''{child_compare,status}'','''') in (''ahead'',''identical'')\n      and v_link.evidence#>>''{child_compare,base_sha}''=v_pkg.metadata->>''production_child_head''\n      and v_link.evidence#>>''{child_compare,head_sha}''=p_expected_child_head\n      and coalesce((v_link.evidence#>>''{child_compare,behind_by}'')::integer,-1)=0\n      and (\n        coalesce(v_link.evidence#>>''{child_compare,status}'','''')=''identical''\n        or coalesce((v_link.evidence#>>''{child_compare,ahead_by}'')::integer,0)>=1\n      )\n  end;';
  v_old_prod text := E'  v_production_receipt_ok := v_prod.receipt_id is not null\n    and v_prod.authority_mode=''founder_direct''\n    and v_prod.rollback_state=''ready''\n    and coalesce(v_prod.canary_result->>''verdict'','''')=''PASS''\n    and coalesce(v_prod.canary_result->>''score'','''')<>''''\n    and v_pkg.metadata->>''production_child_head''=p_expected_child_head\n    and v_activation_parent ~ ''^[0-9a-f]{40}$''\n    and v_prod.exact_version_ref=v_pkg.metadata->>''production_exact_version_ref''\n    and v_prod.content_sha256=v_pkg.metadata->>''production_content_sha256''\n    and v_prod.founder_request_id::text=v_pkg.metadata->>''production_authority_request_id''\n    and v_link.evidence->>''activation_receipt_id''=v_prod.receipt_id::text\n    and v_link.evidence->>''activation_child_head''=p_expected_child_head\n    and v_link.evidence->>''activation_parent_head''=v_activation_parent\n    and not coalesce((v_link.evidence->>''production_authority_rewritten'')::boolean,false)\n    and v_parent_descendant_ok;';
  v_new_prod text := E'  v_production_receipt_ok := v_prod.receipt_id is not null\n    and v_prod.authority_mode=''founder_direct''\n    and v_prod.rollback_state=''ready''\n    and coalesce(v_prod.canary_result->>''verdict'','''')=''PASS''\n    and coalesce(v_prod.canary_result->>''score'','''')<>''''\n    and v_activation_parent ~ ''^[0-9a-f]{40}$''\n    and coalesce(v_pkg.metadata->>''production_child_head'','''') ~ ''^[0-9a-f]{40}$''\n    and v_prod.exact_version_ref=v_pkg.metadata->>''production_exact_version_ref''\n    and v_prod.content_sha256=v_pkg.metadata->>''production_content_sha256''\n    and v_prod.founder_request_id::text=v_pkg.metadata->>''production_authority_request_id''\n    and not coalesce((v_link.evidence->>''production_authority_rewritten'')::boolean,false)\n    and not coalesce((v_link.evidence->>''package_production_authority_rewritten'')::boolean,false)\n    and not coalesce((v_link.evidence->>''authority_effect'')::boolean,false)\n    and not coalesce((v_link.evidence->>''operational_activation'')::boolean,false)\n    and v_parent_descendant_ok\n    and v_child_descendant_ok\n    and (\n      (\n        v_link.evidence->>''activation_receipt_id''=v_prod.receipt_id::text\n        and v_link.evidence->>''activation_child_head''=p_expected_child_head\n        and v_link.evidence->>''activation_parent_head''=v_activation_parent\n      )\n      or coalesce((v_link.evidence->>''technical_assurance_only'')::boolean,false)\n    );';
  v_old_return text := E'    ''external_observations_ok'',v_observations_ok,''parent_descendant_ok'',v_parent_descendant_ok,\n    ''parent_certified_exact_snapshot'',v_parent_certified';
  v_new_return text := E'    ''external_observations_ok'',v_observations_ok,''parent_descendant_ok'',v_parent_descendant_ok,''child_descendant_ok'',v_child_descendant_ok,\n    ''parent_certified_exact_snapshot'',v_parent_certified';
begin
  select pg_get_functiondef(p.oid) into v_def
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='cie_production_source_integration_gate_v2'
    and pg_get_function_identity_arguments(p.oid)='p_expected_child_head text, p_expected_parent_head text, p_candidate_public_contract_digest text';
  if v_def is null then raise exception 'cie_source_gate_v2_missing'; end if;
  v_pre_sha := encode(extensions.digest(convert_to(v_def,'UTF8'),'sha256'),'hex');
  if v_pre_sha <> '555dd34cbd5cce94cfbc5bad15c79e57a50530e6915afffde8932e68e476e049' then
    raise exception 'cie_source_gate_v2_prestate_mismatch:%',v_pre_sha;
  end if;
  if position(v_old_decl in v_def)=0 or position(v_old_parent in v_def)=0 or position(v_old_prod in v_def)=0 or position(v_old_return in v_def)=0 then
    raise exception 'cie_source_gate_v2_patch_anchor_missing';
  end if;
  v_after := replace(replace(replace(replace(v_def,v_old_decl,v_new_decl),v_old_parent,v_new_parent),v_old_prod,v_new_prod),v_old_return,v_new_return);
  execute v_after;
  select pg_get_functiondef(p.oid) into v_after
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='cie_production_source_integration_gate_v2'
    and pg_get_function_identity_arguments(p.oid)='p_expected_child_head text, p_expected_parent_head text, p_candidate_public_contract_digest text';
  v_post_sha := encode(extensions.digest(convert_to(v_after,'UTF8'),'sha256'),'hex');
  if v_post_sha=v_pre_sha then raise exception 'cie_source_gate_v2_patch_noop'; end if;
  if position('v_child_descendant_ok' in v_after)=0 or position('technical_assurance_only' in v_after)=0 then
    raise exception 'cie_source_gate_v2_poststate_validation_failed';
  end if;
end
$migration$;
