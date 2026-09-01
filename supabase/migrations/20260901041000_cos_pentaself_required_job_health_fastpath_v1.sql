-- COS V1 sprint: bound PentaSELF required-job health reads used by public.cos_v1_status_v3.
-- Pre-change EXPLAIN ANALYZE for the unrecovered-required-job predicate scanned
-- cron.job_run_details in parallel (~257k rows observed, 18,502 blocks read) and
-- sequentially scanned penta_self.action_receipts_v1 (~31k rows), taking ~213 ms.
-- Additive indexes only; no history deletion or authority changes.

DO $preflight$
BEGIN
  IF to_regclass('cron.job_run_details') IS NULL THEN
    RAISE EXCEPTION 'cron_job_run_details_missing';
  END IF;
  IF to_regclass('penta_self.action_receipts_v1') IS NULL THEN
    RAISE EXCEPTION 'penta_self_action_receipts_v1_missing';
  END IF;
END
$preflight$;

CREATE INDEX IF NOT EXISTS job_run_details_jobid_start_time_desc_idx
  ON cron.job_run_details (jobid, start_time DESC);

CREATE INDEX IF NOT EXISTS action_receipts_recover_required_job_idx
  ON penta_self.action_receipts_v1
  (action_key, result_state, target_ref, completed_at DESC);

DO $verify$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='cron' AND tablename='job_run_details'
      AND indexname='job_run_details_jobid_start_time_desc_idx'
  ) THEN
    RAISE EXCEPTION 'job_run_details_jobid_start_time_desc_idx_missing';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='penta_self' AND tablename='action_receipts_v1'
      AND indexname='action_receipts_recover_required_job_idx'
  ) THEN
    RAISE EXCEPTION 'action_receipts_recover_required_job_idx_missing';
  END IF;
END
$verify$;

-- Rollback only if independently required:
-- DROP INDEX IF EXISTS cron.job_run_details_jobid_start_time_desc_idx;
-- DROP INDEX IF EXISTS penta_self.action_receipts_recover_required_job_idx;
