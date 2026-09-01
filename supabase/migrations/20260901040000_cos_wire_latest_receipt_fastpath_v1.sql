-- COS V1 sprint: bound latest PentaWire receipt lookup used by public.cos_v1_status_v3.
-- Pre-change EXPLAIN ANALYZE on 44,563 rows performed a sequential scan + top-N sort,
-- reading 6,676 shared blocks and taking ~275 ms for ORDER BY observed_at DESC LIMIT 1.
-- This additive index preserves receipt history and changes no provider, money, rights, or D3 authority.

DO $preflight$
BEGIN
  IF to_regclass('integration_control.penta_wire_scan_receipts_v1') IS NULL THEN
    RAISE EXCEPTION 'penta_wire_scan_receipts_v1_missing';
  END IF;
END
$preflight$;

CREATE INDEX IF NOT EXISTS penta_wire_scan_receipts_v1_observed_at_desc_idx
  ON integration_control.penta_wire_scan_receipts_v1 (observed_at DESC);

DO $verify$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'integration_control'
      AND tablename = 'penta_wire_scan_receipts_v1'
      AND indexname = 'penta_wire_scan_receipts_v1_observed_at_desc_idx'
  ) THEN
    RAISE EXCEPTION 'penta_wire_scan_receipts_v1_observed_at_desc_idx_missing';
  END IF;
END
$verify$;

-- Rollback (only if independently needed):
-- DROP INDEX IF EXISTS integration_control.penta_wire_scan_receipts_v1_observed_at_desc_idx;
