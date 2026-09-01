-- COS V1 sprint: bound latest PentaSELF cycle receipt lookup used by penta_self.status_v1.
-- Production pre-state: `SELECT to_jsonb(c) ... ORDER BY started_at DESC LIMIT 1`
-- sequentially scanned 5,062 wide cycle receipts / 16,472 shared blocks and took ~977 ms.
-- Additive index only; history and receipt bodies are unchanged.

DO $preflight$
BEGIN
  IF to_regclass('penta_self.cycle_receipts_v1') IS NULL THEN
    RAISE EXCEPTION 'penta_self_cycle_receipts_v1_missing';
  END IF;
END
$preflight$;

CREATE INDEX IF NOT EXISTS cycle_receipts_v1_started_at_desc_idx
  ON penta_self.cycle_receipts_v1 (started_at DESC);

DO $verify$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='penta_self'
      AND tablename='cycle_receipts_v1'
      AND indexname='cycle_receipts_v1_started_at_desc_idx'
  ) THEN
    RAISE EXCEPTION 'cycle_receipts_v1_started_at_desc_idx_missing';
  END IF;
END
$verify$;

-- Rollback only if independently required:
-- DROP INDEX IF EXISTS penta_self.cycle_receipts_v1_started_at_desc_idx;
