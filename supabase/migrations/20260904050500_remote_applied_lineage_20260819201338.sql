-- CrownThrive migration-lineage restoration marker v2.
-- Historical remote version 20260819201338 is already owned in production ThriveBase by
-- `collab_project_swagger_contract_inspector`; this marker MUST NOT reuse that production key.
-- The prior source-only marker reused 20260819201338 and caused Supabase Preview to collide
-- on the schema_migrations primary key during reconciliation.
--
-- remote_applied_version: 20260819201338
-- canonical_remote_name: collab_project_swagger_contract_inspector
-- source_marker_version: 20260904050500
--
-- Exact historical SQL remains under protected ThriveBase migration-ledger custody and is not
-- reconstructed here. This migration is intentionally a no-op and exists only to preserve the
-- source provenance note without claiming the production-owned migration identity.

do $$
begin
  null;
end
$$;
