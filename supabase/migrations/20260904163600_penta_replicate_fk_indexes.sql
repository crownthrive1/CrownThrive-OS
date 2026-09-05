-- Exact remaining PentaReplicate FK performance gaps after inspecting production indexes.
-- Existing left-prefix indexes already cover jobs.surface_id, manifests.surface_id,
-- receipts.surface_id and targets.surface_id.
create index if not exists penta_replicate_jobs_event_idx
  on integration_control.penta_replicate_jobs_v1(event_id)
  where event_id is not null;

create index if not exists penta_replicate_receipts_job_idx
  on integration_control.penta_replicate_receipts_v1(job_id)
  where job_id is not null;
