-- Rollback for 20260901180135_cos_release_candidate_scoped_runtime_boundary_v1.sql
-- Historical candidate rows/events/DAIL evidence are intentionally untouched.

drop function if exists integration_control.cos_release_candidate_dependency_status_v2(text);
drop function if exists integration_control.cos_release_candidate_manifest_validate_v3(jsonb);
