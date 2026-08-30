-- CrownThrive Penta Identity Source Snapshot Ref Lineage v1
-- Preserve identical registry bytes observed at newer exact source refs without rewriting
-- the historical snapshot row. This is metadata lineage only and creates no authority.

ALTER TABLE integration_control.penta_identity_source_snapshots_v1
  DROP CONSTRAINT IF EXISTS penta_identity_source_snapshots_v_source_type_source_sha256_key;

ALTER TABLE integration_control.penta_identity_source_snapshots_v1
  ADD CONSTRAINT penta_identity_source_snapshots_v1_source_ref_sha_key
  UNIQUE (source_type, source_ref, source_sha256);

DO $snapshot$
DECLARE
  v_expected_sha constant text := '052a9bdcdd31e6f10f2c95ea56d4486366b6b125a9c0122036061c3ede10227b';
  v_new_ref constant text := 'crownthrive1/CrownThrive-OS@1930801e83c8720f6f3222e17ce174d100a36c27:data/penta/os-v1.registry.json';
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM integration_control.penta_identity_source_snapshots_v1
    WHERE source_type='github_penta_os_registry'
      AND source_sha256=v_expected_sha
  ) THEN
    RAISE EXCEPTION 'expected Penta OS registry snapshot missing';
  END IF;

  INSERT INTO integration_control.penta_identity_source_snapshots_v1(
    snapshot_id,source_type,source_ref,source_version,source_sha256,source_count,payload,observed_at
  )
  SELECT gen_random_uuid(),source_type,v_new_ref,source_version,source_sha256,source_count,payload,clock_timestamp()
  FROM integration_control.penta_identity_source_snapshots_v1
  WHERE source_type='github_penta_os_registry'
    AND source_sha256=v_expected_sha
  ORDER BY observed_at DESC
  LIMIT 1
  ON CONFLICT (source_type,source_ref,source_sha256) DO NOTHING;
END
$snapshot$;

COMMENT ON CONSTRAINT penta_identity_source_snapshots_v1_source_ref_sha_key
ON integration_control.penta_identity_source_snapshots_v1 IS
'Allows append-only source-ref observations of identical verified bytes while deduplicating the exact source_type + source_ref + digest tuple.';
