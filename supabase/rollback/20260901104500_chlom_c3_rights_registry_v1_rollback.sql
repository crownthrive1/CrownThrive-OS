-- Rollback for CHLOM C3 Rights Registry v1.
-- Safe only before durable rights claim/decision history exists. Once evidence exists,
-- preserve it append-only and supersede forward instead of deleting history.

do $rollback_guard$
begin
  if to_regclass('chlom_runtime.rights_claims_v1') is not null then
    if exists(select 1 from chlom_runtime.rights_claims_v1 limit 1) then
      raise exception 'CHLOM_C3_ROLLBACK_BLOCKED_RIGHTS_HISTORY_EXISTS';
    end if;
  end if;
  if to_regclass('chlom_runtime.rights_claim_decisions_v1') is not null then
    if exists(select 1 from chlom_runtime.rights_claim_decisions_v1 limit 1) then
      raise exception 'CHLOM_C3_ROLLBACK_BLOCKED_DECISION_HISTORY_EXISTS';
    end if;
  end if;
end
$rollback_guard$;

drop function if exists chlom_runtime.rights_query_v1(text,text,text);
drop function if exists chlom_runtime.record_rights_claim_decision_v1(uuid,text,text,text,jsonb,text);
drop function if exists chlom_runtime.assert_rights_claim_v1(text,text,text,text,text,text[],text[],text[],jsonb,jsonb,text,text);
drop view if exists chlom_runtime.rights_claim_current_v1;
drop table if exists chlom_runtime.rights_claim_decisions_v1;
drop table if exists chlom_runtime.rights_claims_v1;
drop function if exists chlom_runtime.rights_norm_scope_v1(text[]);
drop function if exists chlom_runtime.rights_history_reject_mutation_v1();
