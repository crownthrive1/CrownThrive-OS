-- CrownThrive Penta Identity Source Lineage — current-ref repair v1
-- Purpose: remove the stale hard-coded Penta OS registry commit from the refresh path
-- while preserving predecessor lineage append-only.
-- Authority boundary: identity/source metadata only; no provider, credential, financial,
-- certification, deployment, dispatch, D3, vote, or quorum authority is created.

DO $migration$
DECLARE
  v_def text;
  v_new_def text;
  v_expected_sha constant text := '052a9bdcdd31e6f10f2c95ea56d4486366b6b125a9c0122036061c3ede10227b';
  v_old_ref constant text := 'crownthrive1/CrownThrive-OS@845deac432b3210e73f61dffde8e335a84d24837:data/penta/os-v1.registry.json';
  v_new_ref constant text := 'crownthrive1/CrownThrive-OS@1930801e83c8720f6f3222e17ce174d100a36c27:data/penta/os-v1.registry.json';
BEGIN
  SELECT pg_get_functiondef('integration_control.penta_identity_refresh_v1(text)'::regprocedure)
    INTO v_def;

  IF position('snap jsonb; snap_sha text; snap_version text; run_id uuid:=gen_random_uuid();' in v_def) = 0
     OR position('select payload,source_sha256,source_version into snap,snap_sha,snap_version from integration_control.penta_identity_source_snapshots_v1' in v_def) = 0
     OR position('''penta_os_registry'',''crownthrive1/CrownThrive-OS@845deac432b3210e73f61dffde8e335a84d24837''' in v_def) = 0
     OR position('source_refs=integration_control.penta_identity_registry_v1.source_refs||excluded.source_refs' in v_def) = 0 THEN
    RAISE EXCEPTION 'penta_identity_refresh_v1 source contract drifted; refusing non-exact patch';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM integration_control.penta_identity_source_snapshots_v1
    WHERE source_type = 'github_penta_os_registry'
      AND source_sha256 = v_expected_sha
  ) THEN
    RAISE EXCEPTION 'expected Penta OS registry source snapshot missing';
  END IF;

  INSERT INTO integration_control.penta_identity_source_snapshots_v1(
    snapshot_id, source_type, source_ref, source_version,
    source_sha256, source_count, payload, observed_at
  )
  SELECT gen_random_uuid(), source_type, v_new_ref, source_version,
         source_sha256, source_count, payload, clock_timestamp()
  FROM integration_control.penta_identity_source_snapshots_v1
  WHERE source_type = 'github_penta_os_registry'
    AND source_sha256 = v_expected_sha
  ORDER BY observed_at DESC
  LIMIT 1
  ON CONFLICT DO NOTHING;

  v_new_def := v_def;
  v_new_def := replace(v_new_def,'snap jsonb; snap_sha text; snap_version text; run_id uuid:=gen_random_uuid();','snap jsonb; snap_sha text; snap_version text; snap_ref text; run_id uuid:=gen_random_uuid();');
  v_new_def := replace(v_new_def,'select payload,source_sha256,source_version into snap,snap_sha,snap_version from integration_control.penta_identity_source_snapshots_v1','select payload,source_sha256,source_version,source_ref into snap,snap_sha,snap_version,snap_ref from integration_control.penta_identity_source_snapshots_v1');
  v_new_def := replace(v_new_def,'''penta_os_registry'',''crownthrive1/CrownThrive-OS@845deac432b3210e73f61dffde8e335a84d24837''','''penta_os_registry'',snap_ref');
  v_new_def := replace(v_new_def,'source_refs=integration_control.penta_identity_registry_v1.source_refs||excluded.source_refs','source_refs=integration_control.penta_identity_registry_v1.source_refs||jsonb_strip_nulls(jsonb_build_object(''penta_os_registry_previous'',case when integration_control.penta_identity_registry_v1.source_refs->>''penta_os_registry'' is distinct from excluded.source_refs->>''penta_os_registry'' then integration_control.penta_identity_registry_v1.source_refs->>''penta_os_registry'' else integration_control.penta_identity_registry_v1.source_refs->>''penta_os_registry_previous'' end))||excluded.source_refs');

  IF v_new_def = v_def OR position('snap_ref text' in v_new_def)=0 OR position('''penta_os_registry'',snap_ref' in v_new_def)=0 OR position('penta_os_registry_previous' in v_new_def)=0 THEN
    RAISE EXCEPTION 'penta_identity_refresh_v1 exact patch failed';
  END IF;

  EXECUTE v_new_def;
END
$migration$;

COMMENT ON FUNCTION integration_control.penta_identity_refresh_v1(text) IS
'Penta identity/family refresh v1. Source lineage uses the latest exact source snapshot ref and preserves the predecessor ref append-only when it changes. Family routers remain coordination-only and inherit no member authority.';