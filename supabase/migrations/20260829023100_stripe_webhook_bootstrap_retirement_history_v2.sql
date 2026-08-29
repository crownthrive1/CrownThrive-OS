create or replace function public.stripe_webhook_record_bootstrap_v2(p_target_key text,p_provider_endpoint_id text,p_provider_state text,p_canary_http_status integer,p_retired_ids text[],p_evidence jsonb)
returns jsonb language plpgsql security definer set search_path=pg_catalog,integration_control,extensions,penta_self,chlom_runtime as $$
declare v_sha text; v_receipt uuid; v_title text; v_state text; v_retired_all text[];
begin
  v_state:=case when p_provider_state='enabled' and p_canary_http_status between 200 and 299 then 'PRODUCTION_HEALTHY' else 'HOLD' end;
  v_sha:=encode(extensions.digest(coalesce(p_evidence,'{}'::jsonb)::text,'sha256'),'hex');
  select coalesce(array_agg(distinct x order by x),'{}'::text[]) into v_retired_all
  from (
    select unnest(coalesce(retired_provider_endpoint_ids,'{}'::text[])) x from integration_control.stripe_webhook_targets_v2 where target_key=p_target_key
    union all
    select unnest(coalesce(p_retired_ids,'{}'::text[]))
  ) s;
  update integration_control.stripe_webhook_targets_v2
     set provider_endpoint_id=p_provider_endpoint_id,provider_state=p_provider_state,ingress_state=v_state,last_provider_sync_at=now(),last_local_canary_at=case when p_canary_http_status between 200 and 299 then now() else last_local_canary_at end,retired_provider_endpoint_ids=v_retired_all,metadata=metadata||jsonb_build_object('bootstrap_evidence_sha256',v_sha,'local_signed_canary_http_status',p_canary_http_status,'provider_endpoint_id',p_provider_endpoint_id,'broken_predecessors_retired_total',coalesce(array_length(v_retired_all,1),0),'secret_exposed',false),updated_at=now()
   where target_key=p_target_key;
  insert into integration_control.stripe_webhook_receipts_v2(receipt_kind,target_key,provider_endpoint_id,state,evidence,evidence_sha256)
  values('ENDPOINT_BOOTSTRAP',p_target_key,p_provider_endpoint_id,v_state,coalesce(p_evidence,'{}'::jsonb)||jsonb_build_object('canary_http_status',p_canary_http_status,'retired_ids_this_run',coalesce(to_jsonb(p_retired_ids),'[]'::jsonb),'retired_ids_total',coalesce(to_jsonb(v_retired_all),'[]'::jsonb),'secret_exposed',false),v_sha) returning receipt_id into v_receipt;
  begin
    perform chlom_runtime.append_dail_event('stripe.webhook.endpoint.bootstrap','provider_configuration','stripe:'||p_provider_endpoint_id,jsonb_build_object('target_key',p_target_key,'provider_state',p_provider_state,'ingress_state',v_state,'canary_http_status',p_canary_http_status,'retired_count_total',coalesce(array_length(v_retired_all,1),0),'evidence_sha256',v_sha,'money_movement_authority',false),'PentaHook/PentaCredentials/PentaCertify',null,'PentaHook','2.0.1',v_sha,null,'ct.stripe.webhook-ingress.v2',null,'internal');
  exception when others then null;
  end;
  if v_state='PRODUCTION_HEALTHY' then
    v_title:=case when p_target_key='thrivetickets' then 'ThriveTickets Stripe webhook returning HTTP 404' else 'KJV/Sermon Toolkit Stripe webhook returning HTTP 503' end;
    perform penta_self.resolve_problem_verified_v2(v_title,'Broken Stripe webhook endpoint replaced by a provider-enabled centralized signed ingress; predecessor endpoint(s) retired after a valid signed local canary returned 2xx.',jsonb_build_object('target_key',p_target_key,'provider_endpoint_id',p_provider_endpoint_id,'provider_state',p_provider_state,'local_signed_canary_http_status',p_canary_http_status,'retired_provider_endpoint_ids',coalesce(to_jsonb(v_retired_all),'[]'::jsonb),'event_ledger','integration_control.stripe_webhook_events_v2','money_movement_authority',false),'stripe-api+supabase-edge:ct.stripe.webhook-ingress.v2','NEWER_PROVIDER_ENDPOINT_FAILURE_ONLY');
  end if;
  return jsonb_build_object('target_key',p_target_key,'state',v_state,'receipt_id',v_receipt,'retired_ids_total',coalesce(to_jsonb(v_retired_all),'[]'::jsonb),'evidence_sha256',v_sha,'secret_exposed',false);
end $$;
revoke all on function public.stripe_webhook_record_bootstrap_v2(text,text,text,integer,text[],jsonb) from public,anon,authenticated;
grant execute on function public.stripe_webhook_record_bootstrap_v2(text,text,text,integer,text[],jsonb) to service_role;
