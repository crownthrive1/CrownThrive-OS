-- CrownThrive COS V1 sprint performance repair.
-- cos_scheduler_census_refresh_v1 reads the latest cron run once per job.
-- cron.job_run_details previously had only a runid PK, causing ~23K filtered
-- rows per scheduler and ~8s for the 254-job census query.
-- This selective ordering index makes latest-run lookup bounded by jobid.
-- Rollback: DROP INDEX IF EXISTS cron.cos_job_run_details_jobid_runid_desc_idx;

create index if not exists cos_job_run_details_jobid_runid_desc_idx
  on cron.job_run_details (jobid, runid desc);

comment on index cron.cos_job_run_details_jobid_runid_desc_idx is
  'COS scheduler-census fast path: latest cron run by (jobid, runid desc). Sprint repair for certifier convergence timeout.';
