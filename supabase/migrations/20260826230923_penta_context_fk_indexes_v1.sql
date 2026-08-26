-- Applied to production as migration 20260826230923.
create index if not exists penta_context_records_supersedes_idx on public.penta_context_records_v1(supersedes_context_id) where supersedes_context_id is not null;
create index if not exists penta_context_receipts_context_idx on public.penta_context_receipts_v1(context_id) where context_id is not null;
create index if not exists penta_context_receipts_source_idx on public.penta_context_receipts_v1(source_id) where source_id is not null;
