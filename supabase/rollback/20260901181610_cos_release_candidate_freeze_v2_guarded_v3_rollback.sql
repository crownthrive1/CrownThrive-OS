-- Guarded rollback for 20260901181610_cos_release_candidate_freeze_v2_guarded_v3.sql.
-- Historical v1 candidates, v3 manifests, DAIL events, and candidate rows are untouched.
-- Do not execute this rollback while any frozen v3 candidate requires freeze_v2 as an included dependency.

drop function if exists integration_control.cos_release_candidate_freeze_v2(text,text,text,text,text,text,text,text,text,text,jsonb,text,text);
