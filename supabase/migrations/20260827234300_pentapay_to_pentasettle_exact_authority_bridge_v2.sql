create or replace function public.penta_pay_prepare_live_settlement_v2(
 p_pay_entry_id uuid,
 p_adapter_key text,
 p_recipient_ref_kind text,
 p_recipient_ref text,
 p_exact_ecac_ref text,
 p_authority_evidence_ref text,
 p_ttl_seconds integer default 300,
 p_metadata jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path='pg_catalog','public','penta_runtime','penta_os20','integration_control','chlom_runtime','extensions'
as $$
declare
 v_pay public.penta_pay_entries%rowtype;
 v_issuer uuid;
 v_approver uuid;
 v_authority_id text;
 v_grant jsonb;
 v_intent jsonb;
 v_auth jsonb;
 v_grant_id uuid;
 v_intent_id uuid;
 v_grant_key text;
 v_intent_key text;
 v_idem text;
 v_exp timestamptz;
 v_dail jsonb;
begin
 if session_user<>'postgres' and coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required'; end if;
 if p_ttl_seconds < 30 or p_ttl_seconds > 900 then raise exception 'PENTAPAY_SETTLEMENT_TTL_OUT_OF_RANGE'; end if;
 if nullif(btrim(p_exact_ecac_ref),'') is null or nullif(btrim(p_authority_evidence_ref),'') is null then raise exception 'PENTAPAY_EXACT_AUTHORITY_REQUIRED'; end if;
 if nullif(btrim(p_recipient_ref),'') is null then raise exception 'PENTAPAY_RECIPIENT_REFERENCE_REQUIRED'; end if;
 select * into v_pay from public.penta_pay_entries where pay_entry_id=p_pay_entry_id for update;
 if not found or v_pay.state not in ('approved','eligible') then raise exception 'PENTAPAY_APPROVED_OR_ELIGIBLE_ENTRY_REQUIRED'; end if;
 if v_pay.gross_minor<=0 then raise exception 'PENTAPAY_LIVE_SETTLEMENT_POSITIVE_AMOUNT_REQUIRED'; end if;
 if v_pay.approved_by_assignment_id is null then raise exception 'PENTAPAY_WORKFORCE_APPROVAL_REQUIRED'; end if;
 if exists(select 1 from public.penta_workforce_assignments a where a.assignment_id=v_pay.approved_by_assignment_id and a.subject_ref=v_pay.beneficiary_subject_ref) then raise exception 'PENTAPAY_SELF_APPROVAL_PROHIBITED'; end if;
 select ra.id into v_issuer from penta_os20.role_assignments ra join penta_os20.pentas p on p.id=ra.penta_id where p.canonical_name='PentaTreasury' and ra.status='active' order by ra.assigned_at desc limit 1;
 select ra.id into v_approver from penta_os20.role_assignments ra join penta_os20.pentas p on p.id=ra.penta_id where p.canonical_name='PentaExecutive' and ra.status='active' order by ra.assigned_at desc limit 1;
 if v_issuer is null or v_approver is null or v_issuer=v_approver then raise exception 'PENTAPAY_CONSTITUTIONAL_ASSIGNMENTS_UNAVAILABLE'; end if;
 select authority_id into v_authority_id from integration_control.economic_money_movement_authority_v1 where authority_state='active' and environment='production' and money_movement_authorized and provider_write_authorized and requires_exact_ecac and d3_human_reserved and max_unattended_value_minor=0 order by created_at desc limit 1;
 if v_authority_id is null then raise exception 'PENTAPAY_FOUNDATIONAL_MONEY_MOVEMENT_AUTHORITY_UNAVAILABLE'; end if;
 v_exp:=now()+make_interval(secs=>p_ttl_seconds);
 v_grant_key:='ct.pentapay.grant.'||replace(p_pay_entry_id::text,'-','')||'.'||extract(epoch from clock_timestamp())::bigint;
 v_intent_key:='ct.pentapay.intent.'||replace(p_pay_entry_id::text,'-','')||'.'||extract(epoch from clock_timestamp())::bigint;
 v_idem:=encode(extensions.digest(convert_to(v_pay.pay_key||'|'||p_adapter_key||'|'||p_recipient_ref_kind||'|'||penta_runtime.penta_settle_recipient_digest_v2(p_recipient_ref_kind,p_recipient_ref)||'|'||v_pay.gross_minor::text||'|'||v_pay.currency||'|'||p_exact_ecac_ref,'UTF8'),'sha256'),'hex');
 if exists(select 1 from penta_runtime.settlement_intents_v2 where pay_entry_id=p_pay_entry_id and mode='live' and state in ('created','authorized','dispatch_claimed','provider_pending','hold','settled')) then raise exception 'PENTAPAY_LIVE_SETTLEMENT_ALREADY_EXISTS'; end if;
 v_grant:=penta_runtime.penta_settle_issue_exact_authority_v2(v_grant_key,p_pay_entry_id,p_adapter_key,p_recipient_ref_kind,p_recipient_ref,v_pay.gross_minor,v_pay.currency,v_exp,v_authority_id,p_authority_evidence_ref,p_exact_ecac_ref,v_issuer,v_approver,coalesce(p_metadata,'{}'::jsonb)||jsonb_build_object('source','PentaPay','obligation_scoped',true,'ttl_seconds',p_ttl_seconds));
 v_grant_id:=(v_grant->>'grant_id')::uuid;
 v_intent:=penta_runtime.penta_settle_create_intent_v2(v_intent_key,p_pay_entry_id,p_adapter_key,p_recipient_ref_kind,p_recipient_ref,v_pay.gross_minor,v_pay.currency,v_issuer,v_idem,'live',v_grant_id,v_pay.pay_key,coalesce(p_metadata,'{}'::jsonb)||jsonb_build_object('release_version','OS-2.0.0','source','PentaPay','obligation_scoped',true));
 v_intent_id:=(v_intent->>'intent_id')::uuid;
 v_auth:=penta_runtime.penta_settle_authorize_intent_v2(v_intent_id,v_approver,p_authority_evidence_ref);
 update public.penta_pay_obligation_links_v2 set metadata=metadata||jsonb_build_object('penta_settle_grant_id',v_grant_id,'penta_settle_intent_id',v_intent_id,'exact_ecac_ref',p_exact_ecac_ref,'settlement_ttl_seconds',p_ttl_seconds,'canonical_settlement_path','PentaSettle v2') where pay_entry_id=p_pay_entry_id;
 v_dail:=chlom_runtime.append_dail_event('penta.pay.live_settlement_prepared','penta_pay_entry',p_pay_entry_id::text,jsonb_build_object('grant_id',v_grant_id,'intent_id',v_intent_id,'adapter_key',p_adapter_key,'amount_minor',v_pay.gross_minor,'currency',v_pay.currency,'expires_at',v_exp,'idempotency_key',v_idem,'recipient_ref_projected',false,'generic_money_authority',false),'PentaPay',null,'PentaPay','2.0.0',v_pay.pay_key,v_intent_id::text,p_authority_evidence_ref,null,'restricted');
 return jsonb_build_object('prepared',true,'pay_entry_id',p_pay_entry_id,'grant_id',v_grant_id,'intent_id',v_intent_id,'adapter_key',p_adapter_key,'amount_minor',v_pay.gross_minor,'currency',v_pay.currency,'expires_at',v_exp,'idempotency_key',v_idem,'dispatch_claim_required',true,'provider_write_performed',false,'standing_money_authority',false,'dail_event_id',v_dail->>'event_id');
end $$;

revoke execute on function public.penta_pay_prepare_live_settlement_v2(uuid,text,text,text,text,text,integer,jsonb) from public,anon,authenticated;
grant execute on function public.penta_pay_prepare_live_settlement_v2(uuid,text,text,text,text,text,integer,jsonb) to service_role;

comment on table public.penta_pay_dispatch_authorizations_v1 is 'Compatibility canary lineage only. Canonical live dispatch authority is penta_runtime.settlement_authority_grants_v2 + settlement_intents_v2.';
revoke execute on function public.penta_pay_mint_dispatch_authorization_v1(uuid,text,text,text,text,integer,jsonb) from service_role;
revoke execute on function public.penta_pay_claim_dispatch_authorization_v1(uuid,text) from service_role;
revoke execute on function public.penta_pay_consume_dispatch_authorization_v1(uuid,text,text,boolean,text,jsonb) from service_role;
revoke execute on function public.penta_pay_revoke_dispatch_authorization_v1(uuid,text) from service_role;
