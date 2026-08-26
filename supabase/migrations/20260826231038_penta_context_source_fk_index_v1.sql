-- Applied to production as migration 20260826231038.
create index if not exists penta_context_records_source_idx on public.penta_context_records_v1(source_id);
