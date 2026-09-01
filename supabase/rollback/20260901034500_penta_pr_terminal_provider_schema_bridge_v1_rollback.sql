-- Rollback for 20260901034500_penta_pr_terminal_provider_schema_bridge_v1.sql.
-- Pre-state readback confirmed these public wrappers did not exist; canonical implementations
-- remain in integration_control and are not modified by this rollback.

drop function if exists public.penta_pr_closeout_result_v1(
  uuid,boolean,integer,text,text,text,text,boolean,jsonb,text,bigint,text,text,text
);
drop function if exists public.penta_pr_closeout_claim_v1(uuid,text,text);
