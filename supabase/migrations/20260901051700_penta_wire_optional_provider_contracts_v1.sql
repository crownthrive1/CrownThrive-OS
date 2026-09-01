-- COS sprint repair: preserve exact provider holds while preventing explicitly optional
-- provider integrations from blocking core PentaWire/COS convergence.
-- Convergence-safe: if the semantic repair is already live, validate it without
-- overwriting a newer function definition. No provider writes, credential operations,
-- money movement, rights, or external side effects.

DO $migration$
DECLARE
  v_expected_sha constant text := '9589a9bdbc0561743860ffbb9f44d3eb3566adcc8b84758e804cfb961fe8095c';
  v_before text;
  v_after text;
  v_def text;
  v_old text;
  v_new text;
  v_rows integer;
  v_service_count integer;
  v_already_patched boolean;
BEGIN
  SELECT count(*)
    INTO v_service_count
  FROM integration_control.services
  WHERE service_id IN (
    'google_analytics_ga4',
    'google_maps_javascript',
    'meta_facebook_login',
    'openai_crownthrive_api',
    'unsplash_crownthrive_studios'
  );

  IF v_service_count <> 5 THEN
    RAISE EXCEPTION 'expected exactly 5 optional provider services, found %', v_service_count;
  END IF;

  SELECT pg_get_functiondef('integration_control.penta_wire_scan_v1()'::regprocedure)
    INTO v_def;
  SELECT encode(extensions.digest(v_def,'sha256'),'hex')
    INTO v_before;

  v_already_patched :=
       position('v_certification_required' in v_def) > 0
   AND position('penta_wire_certification_required' in v_def) > 0
   AND position('if v_certification_required then v_hold:=v_hold+1; end if;' in v_def) > 0
   AND position('''certification_required'',v_certification_required' in v_def) > 0;

  UPDATE integration_control.services
  SET metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
      'penta_wire_certification_required', false,
      'penta_wire_optional_contract_reason', 'configured optional provider integration; local exact-contract HOLD retained but excluded from core COS blocker count',
      'penta_wire_optional_contract_v1', true,
      'penta_wire_optional_contract_classified_at', coalesce(metadata->'penta_wire_optional_contract_classified_at', to_jsonb(clock_timestamp()))
    ),
    updated_at = now()
  WHERE service_id IN (
    'google_analytics_ga4',
    'google_maps_javascript',
    'meta_facebook_login',
    'openai_crownthrive_api',
    'unsplash_crownthrive_studios'
  )
    AND (
      coalesce((metadata->>'penta_wire_certification_required')::boolean,true)
      OR NOT coalesce((metadata->>'penta_wire_optional_contract_v1')::boolean,false)
    );

  GET DIAGNOSTICS v_rows = ROW_COUNT;
  IF v_rows < 0 OR v_rows > 5 THEN
    RAISE EXCEPTION 'optional provider metadata update count out of range: %', v_rows;
  END IF;

  IF EXISTS (
    SELECT 1 FROM integration_control.services
    WHERE service_id IN ('google_analytics_ga4','google_maps_javascript','meta_facebook_login','openai_crownthrive_api','unsplash_crownthrive_studios')
      AND (
        coalesce((metadata->>'penta_wire_certification_required')::boolean,true)
        OR NOT coalesce((metadata->>'penta_wire_optional_contract_v1')::boolean,false)
      )
  ) THEN
    RAISE EXCEPTION 'optional provider classification readback failed';
  END IF;

  IF NOT v_already_patched THEN
    IF v_before <> v_expected_sha THEN
      RAISE EXCEPTION 'penta_wire_scan_v1 predecessor digest mismatch: expected % or validated already-patched semantics, got %', v_expected_sha, v_before;
    END IF;

    v_old := '  v_adapter_kind text; v_adapter_state text; v_secure jsonb; v_prior_probe_state text;';
    v_new := '  v_adapter_kind text; v_adapter_state text; v_secure jsonb; v_prior_probe_state text;' || E'\n' || '  v_certification_required boolean;';
    IF position(v_old in v_def)=0 THEN RAISE EXCEPTION 'declaration patch anchor missing'; END IF;
    v_def := replace(v_def,v_old,v_new);

    v_old := '    v_superseded:=coalesce((s.metadata->>''historical_contract'')::boolean,false)' || E'\n' ||
             '      or nullif(s.metadata->>''superseded_by'','''') is not null or s.integration_state=''retired'';';
    v_new := v_old || E'\n' ||
             '    v_certification_required:=coalesce((s.metadata->>''penta_wire_certification_required'')::boolean,true);';
    IF position(v_old in v_def)=0 THEN RAISE EXCEPTION 'required-scope patch anchor missing'; END IF;
    v_def := replace(v_def,v_old,v_new);

    v_old := '    elsif v_tools=0 and v_adapter_kind is null then' || E'\n' ||
             '      v_binding:=''hold_exact_contract'';v_gap:=''exact_provider_contract_required'';v_probe_method:=''REGISTRY'';v_probe_url:=null;' || E'\n' ||
             '      v_hold:=v_hold+1;';
    v_new := '    elsif v_tools=0 and v_adapter_kind is null then' || E'\n' ||
             '      v_binding:=''hold_exact_contract'';v_gap:=''exact_provider_contract_required'';v_probe_method:=''REGISTRY'';v_probe_url:=null;' || E'\n' ||
             '      if v_certification_required then v_hold:=v_hold+1; end if;';
    IF position(v_old in v_def)=0 THEN RAISE EXCEPTION 'provider-hold patch anchor missing'; END IF;
    v_def := replace(v_def,v_old,v_new);

    v_old := '''tool_accounting_pass'',v_tools=v_active+v_gated+v_retired_tools+v_unresolved,' || E'\n' ||
             '      ''public_read_safe'',v_public,''binding_state'',v_binding,''gap_state'',v_gap,';
    v_new := '''tool_accounting_pass'',v_tools=v_active+v_gated+v_retired_tools+v_unresolved,' || E'\n' ||
             '      ''certification_required'',v_certification_required,' || E'\n' ||
             '      ''public_read_safe'',v_public,''binding_state'',v_binding,''gap_state'',v_gap,';
    IF position(v_old in v_def)=0 THEN RAISE EXCEPTION 'evidence patch anchor missing'; END IF;
    v_def := replace(v_def,v_old,v_new);

    EXECUTE v_def;

    SELECT encode(extensions.digest(pg_get_functiondef('integration_control.penta_wire_scan_v1()'::regprocedure),'sha256'),'hex')
      INTO v_after;
    IF v_after = v_before THEN RAISE EXCEPTION 'penta_wire_scan_v1 digest did not change'; END IF;
  END IF;

  SELECT pg_get_functiondef('integration_control.penta_wire_scan_v1()'::regprocedure)
    INTO v_def;
  IF NOT (
       position('v_certification_required' in v_def) > 0
   AND position('penta_wire_certification_required' in v_def) > 0
   AND position('if v_certification_required then v_hold:=v_hold+1; end if;' in v_def) > 0
   AND position('''certification_required'',v_certification_required' in v_def) > 0
  ) THEN
    RAISE EXCEPTION 'penta_wire_scan_v1 semantic readback failed';
  END IF;
END
$migration$;
