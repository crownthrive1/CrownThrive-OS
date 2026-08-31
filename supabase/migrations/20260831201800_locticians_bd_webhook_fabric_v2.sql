-- CrownThrive / Locticians Brilliant Directories universal webhook fabric v2
-- Rebuild-safe source contract. No API tokens or production hook IDs are stored here.
-- Runtime creates an opaque hook binding and must certify before activation.

begin;

create table if not exists integration_control.locticians_bd_webhook_bindings_v1 (
  binding_key text primary key,
  endpoint_slug text not null,
  public_base_url text not null,
  secret_vault_alias text not null,
  secret_sha256 text not null,
  state text not null check (state in ('staged','active','degraded','retired')),
  auth_mode text not null,
  login_token_payload_allowed boolean not null default false,
  raw_secret_projected boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  hook_id uuid not null default gen_random_uuid()
);

create table if not exists integration_control.locticians_bd_webhook_routes_v1 (
  event_code text primary key,
  provider_event_name text not null,
  category text not null,
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  aliases text[] not null default '{}',
  targets jsonb not null default '[]'::jsonb,
  enabled boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.locticians_bd_webhook_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  event_code text not null,
  raw_event_hint text,
  provider_event_name text,
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  payload_sha256 text not null,
  body_bytes integer not null,
  idempotency_key text not null,
  sanitized_payload jsonb not null default '{}'::jsonb,
  route_targets jsonb not null default '[]'::jsonb,
  source_fingerprint_sha256 text,
  user_agent_sha256 text,
  state text not null,
  raw_secret_projected boolean not null default false,
  received_at timestamptz not null default now()
);
create index if not exists locticians_bd_webhook_receipts_idem_idx on integration_control.locticians_bd_webhook_receipts_v1(idempotency_key,received_at desc);

create table if not exists integration_control.locticians_bd_webhook_dispatch_v1 (
  dispatch_id uuid primary key default gen_random_uuid(),
  receipt_id uuid not null references integration_control.locticians_bd_webhook_receipts_v1(receipt_id) on delete cascade,
  event_code text not null,
  target_ref text not null,
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  state text not null default 'queued',
  authority_note text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  unique(receipt_id,target_ref)
);

create table if not exists integration_control.locticians_bd_webhook_intake_v1 (
  intake_id uuid primary key default gen_random_uuid(),
  event_hint text,
  sanitized_payload jsonb not null default '{}'::jsonb,
  body_sha256 text not null check (body_sha256 ~ '^[0-9a-f]{64}$'),
  body_bytes integer not null check (body_bytes>=0 and body_bytes<=1048576),
  source_fingerprint_sha256 text,
  user_agent_sha256 text,
  request_key text not null,
  state text not null default 'queued' check (state in ('queued','processing','processed','duplicate','retry','failed')),
  attempt_count integer not null default 0,
  next_attempt_at timestamptz not null default now(),
  receipt_id uuid,
  last_error text,
  received_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);
create index if not exists locticians_bd_webhook_intake_ready_idx on integration_control.locticians_bd_webhook_intake_v1(state,next_attempt_at,received_at);
create index if not exists locticians_bd_webhook_intake_request_idx on integration_control.locticians_bd_webhook_intake_v1(request_key,received_at desc);

-- One generated opaque binding per environment; never hardcode the production hook ID in source.
do $block$
declare v_hook uuid:=gen_random_uuid();
begin
  insert into integration_control.locticians_bd_webhook_bindings_v1(
    binding_key,endpoint_slug,public_base_url,secret_vault_alias,secret_sha256,state,auth_mode,
    login_token_payload_allowed,raw_secret_projected,metadata,hook_id
  ) values(
    'ct.locticians.bd.webhook.v1','locticians-bd-webhook-v1',
    'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/locticians-bd-webhook-v1',
    'not_applicable_public_hook_binding_id',
    encode(extensions.digest(convert_to(v_hook::text,'UTF8'),'sha256'),'hex'),
    'staged','opaque high-entropy hook binding id in provider URL',false,false,
    jsonb_build_object('contract','ct.locticians.brilliant-directories.webhook-fabric.v1','route_count',34,'max_body_bytes',1048576,'idempotency_window_minutes',10,'login_token_payload_allowed',false,'provider_signature_documented',false,'raw_secret_projected',false),
    v_hook
  ) on conflict(binding_key) do nothing;
end $block$;

-- Hardcoded BD event topology. Financial/admin/delete events are evidence/queue inputs only.
insert into integration_control.locticians_bd_webhook_routes_v1(event_code,provider_event_name,category,risk_class,aliases,targets,enabled)
values
('member_review','Member Review Submitted','Frontend Forms','D1',array['member_review','member_review_submitted'],'["ct.platform.locticians","crm.penta_marketer","penta.persona-execution","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('contact_form','Contact Us Form Submitted','Frontend Forms','D1',array['contact_form','contact_us_form_submitted'],'["ct.platform.locticians","crm.penta_marketer","penta.persona-execution","penta.mail","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('newsletter_modal_signup','Newsletter Signup','Frontend Forms','D1',array['newsletter_modal_signup','newsletter_signup'],'["crm.penta_marketer","penta.mail","penta.persona-execution","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('unsubscribe_email','Unsubscribed Form Submitted','Unsubscribed form','D1',array['unsubscribe_email','unsubscribed_form_submitted','unsubscribe'],'["penta.mail.suppression","crm.penta_marketer","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('bootstrap_get_match','Lead Submitted','Frontend Forms','D1',array['bootstrap_get_match','lead_submitted','lead'],'["ct.platform.locticians","crm.penta_marketer","penta.persona-execution","penta.mail","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('whmcs_signup_paid','Paid Plan Signup (On-Site Payment Gateway)','Plan Sign Up','D2',array['whmcs_signup_paid','paid_plan_signup_onsite'],'["ct.platform.locticians","penta.persona-execution","crm.penta_marketer","penta.commerce.evidence","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('whmcs_signup_external','Paid Plan Signup (Off-Site Payment Gateway)','Plan Sign Up','D2',array['whmcs_signup_external','paid_plan_signup_offsite'],'["ct.platform.locticians","penta.persona-execution","crm.penta_marketer","penta.commerce.evidence","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('signup_free','Free Plan Signup','Plan Sign Up','D1',array['signup_free','free_plan_signup'],'["ct.platform.locticians","penta.persona-execution","crm.penta_marketer","penta.mail","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('admin_member_mutation','Members Imported / Added / Updated / Deleted Via Admin','Admin Imports / Adds / Updates / Deletes Members','D2',array['admin_member_mutation','members_imported_added_updated_deleted_via_admin','member_admin_action'],'["ct.platform.locticians","penta.census","penta.persona-execution","ct.platform.crownlytics","chlom.dail"]',true),
('post_standard','Post - Standard','Post Forms','D1',array['post_standard','post_standard_form'],'["ct.platform.locticians","ct.framework.pentamedia","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('post_photo_album','Post - Photo Album','Post Forms','D1',array['post_photo_album','photo_album'],'["ct.platform.locticians","ct.framework.pentamedia","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('post_standard_deleted','Post - Standard Deleted','Post Delete','D2',array['post_standard_deleted','standard_post_deleted'],'["ct.platform.locticians","ct.framework.pentamedia","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('post_photo_album_deleted','Post - Photo Album Deleted','Post Delete','D2',array['post_photo_album_deleted','photo_album_deleted'],'["ct.platform.locticians","ct.framework.pentamedia","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('sub_accounts_form','Sub Account Form Submitted','Member Sub Account','D1',array['sub_accounts_form','sub_account_form_submitted'],'["ct.platform.locticians","penta.persona-execution","penta.census","ct.platform.crownlytics","chlom.dail"]',true),
('member_contact_details','Contact Details Form Submitted','Member Profile Forms','D1',array['member_contact_details','contact_general_user','contact_details_form_submitted'],'["ct.platform.locticians","penta.persona-execution","crm.penta_marketer","penta.census","ct.platform.crownlytics","chlom.dail"]',true),
('member_listing_details','Additional Details Form Submitted','Member Profile Forms','D1',array['member_listing_details','additional_details_form_submitted'],'["ct.platform.locticians","penta.persona-execution","crm.penta_marketer","penta.census","ct.platform.crownlytics","chlom.dail"]',true),
('about','About Me Form Submitted','Member Profile Forms','D1',array['about','about_me_form_submitted'],'["ct.platform.locticians","penta.persona-execution","crm.penta_marketer","penta.census","ct.platform.crownlytics","chlom.dail"]',true),
('member_profile_photos','Profile Photos Form Submitted','Member Profile Photos','D1',array['member_profile_photos','profile_photos_form_submitted','profile_photo'],'["ct.platform.locticians","penta.persona-execution","penta.census","ct.platform.crownlytics","chlom.dail"]',true),
('member_email_verified','Member Clicked Email Verification Link','Member Profile Forms','D1',array['member_email_verified','member_clicked_email_verification_link','basic_validation'],'["ct.platform.locticians","penta.persona-execution","penta.census","crm.penta_marketer","ct.platform.crownlytics","chlom.dail"]',true),
('member_plan_changed','Member Plan Changed','Plan Change','D2',array['member_plan_changed','plan_changed'],'["ct.platform.locticians","penta.persona-execution","crm.penta_marketer","penta.commerce.evidence","penta.census","ct.platform.crownlytics","chlom.dail"]',true),
('member_plan_cancelled','Member Plan Cancelled','Plan Cancel','D2',array['member_plan_cancelled','plan_cancelled','member_plan_canceled'],'["ct.platform.locticians","penta.persona-execution","crm.penta_marketer","penta.commerce.evidence","penta.census","ct.platform.crownlytics","chlom.dail"]',true),
('one_time_purchase','One-Time Purchase','One-Time Purchase','D2',array['one_time_purchase','one_time_payment'],'["ct.platform.locticians","penta.commerce.evidence","penta.persona-execution","crm.penta_marketer","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('post_comment','Post Comment Submitted','Post Comments','D1',array['post_comment','post_comment_submitted'],'["ct.platform.locticians","ct.framework.pentamedia","penta.persona-execution","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('smart_form_inquiries','Form Inquiries Smart Lists','Smart Lists','D1',array['smart_form_inquiries','form_inquiries_smart_lists'],'["crm.penta_marketer","penta.persona-execution","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('smart_reviews','Reviews Smart Lists','Smart Lists','D1',array['smart_reviews','reviews_smart_lists'],'["ct.platform.locticians","crm.penta_marketer","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('smart_leads','Leads Smart Lists','Smart Lists','D1',array['smart_leads','leads_smart_lists'],'["crm.penta_marketer","penta.persona-execution","penta.mail","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('smart_members','Members Smart Lists','Smart Lists','D1',array['smart_members','members_smart_lists'],'["ct.platform.locticians","penta.persona-execution","crm.penta_marketer","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('smart_transactions','Transactions Smart Lists','Smart Lists','D2',array['smart_transactions','transactions_smart_lists'],'["penta.commerce.evidence","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('chat_message_actions','Chat Message Actions','Chat Messages','D1',array['chat_message_actions','chat_message','private_member_chat'],'["ct.platform.locticians","penta.persona-execution","crm.penta_marketer","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('admin_invoice_action','Admin Subscription / Invoice Action','Admin Invoice Transaction','D2',array['admin_invoice_action','admin_subscription_invoice_action'],'["penta.commerce.evidence","ct.platform.locticians","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('system_invoice_action','System Invoice Action','System Invoice Transaction','D2',array['system_invoice_action','system_invoice_transaction'],'["penta.commerce.evidence","ct.platform.locticians","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('member_dashboard_payment','Member Dashboard Payment','Finance','D2',array['member_dashboard_payment','dashboard_payment'],'["penta.commerce.evidence","ct.platform.locticians","penta.persona-execution","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('lead_accept_decline','Lead Accept / Decline','Leads','D1',array['lead_accept_decline','lead_accept','lead_decline'],'["ct.platform.locticians","crm.penta_marketer","penta.persona-execution","ct.platform.crownlytics","penta.census","chlom.dail"]',true),
('custom_form','Custom Forms','Custom Forms','D1',array['custom_form','custom_forms'],'["ct.platform.locticians","crm.penta_marketer","penta.persona-execution","ct.platform.crownlytics","penta.census","chlom.dail"]',true)
on conflict(event_code) do update set provider_event_name=excluded.provider_event_name,category=excluded.category,risk_class=excluded.risk_class,aliases=excluded.aliases,targets=excluded.targets,enabled=excluded.enabled,updated_at=now();

create or replace function integration_control.locticians_bd_webhook_normalize_event_v1(p_hint text,p_payload jsonb)
returns text language plpgsql stable security definer set search_path to 'pg_catalog','integration_control' as $function$
declare v_raw text; v_norm text; v_event text;
begin
  v_raw:=nullif(trim(coalesce(p_hint,'')),'');
  if v_raw is null or lower(v_raw)='auto' then
    v_raw:=coalesce(nullif(p_payload->>'event',''),nullif(p_payload->>'event_name',''),nullif(p_payload->>'event_type',''),nullif(p_payload->>'webhook_event',''),nullif(p_payload->>'form',''),nullif(p_payload->>'form_name',''),nullif(p_payload->>'form_id',''),nullif(p_payload->>'action',''),nullif(p_payload->>'category',''));
  end if;
  v_norm:=trim(both '_' from regexp_replace(lower(trim(coalesce(v_raw,''))),'[^a-z0-9]+','_','g'));
  select r.event_code into v_event from integration_control.locticians_bd_webhook_routes_v1 r where r.enabled and (r.event_code=v_norm or v_norm=any(r.aliases)) order by case when r.event_code=v_norm then 0 else 1 end limit 1;
  return coalesce(v_event,'unclassified');
end $function$;

create or replace function integration_control.locticians_bd_webhook_ingest_v1(p_hook_token text,p_event_hint text,p_payload jsonb,p_body_sha256 text,p_body_bytes integer,p_source_fingerprint_sha256 text default null,p_user_agent_sha256 text default null)
returns jsonb language plpgsql security definer set search_path to 'pg_catalog','integration_control','extensions','chlom_runtime' as $function$
declare v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),''); v_expected text; v_event text; v_provider_name text; v_risk text; v_targets jsonb; v_state text; v_idem text; v_existing uuid; v_receipt uuid; v_target text; v_dail jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if p_hook_token is null or length(p_hook_token)<30 then raise exception 'invalid_webhook_binding'; end if;
  if p_body_sha256 is null or p_body_sha256!~'^[0-9a-f]{64}$' then raise exception 'invalid_payload_sha256'; end if;
  if p_body_bytes is null or p_body_bytes<0 or p_body_bytes>1048576 then raise exception 'payload_size_rejected'; end if;
  select hook_id::text into v_expected from integration_control.locticians_bd_webhook_bindings_v1 where binding_key='ct.locticians.bd.webhook.v1' and state in ('staged','active') limit 1;
  if v_expected is null or p_hook_token<>v_expected then raise exception 'invalid_webhook_binding'; end if;
  v_event:=integration_control.locticians_bd_webhook_normalize_event_v1(p_event_hint,coalesce(p_payload,'{}'::jsonb));
  select provider_event_name,risk_class,targets into v_provider_name,v_risk,v_targets from integration_control.locticians_bd_webhook_routes_v1 where event_code=v_event and enabled;
  if not found then v_event:='unclassified'; v_provider_name:='Unclassified Brilliant Directories Webhook'; v_risk:='D1'; v_targets='["ct.platform.locticians","penta.webhook.triage","penta.census","ct.platform.crownlytics","chlom.dail"]'::jsonb; v_state:='accepted_unclassified'; else v_state:='accepted'; end if;
  v_idem:=encode(extensions.digest(convert_to(coalesce(v_event,'')||':'||p_body_sha256||':'||coalesce(p_payload->>'id',p_payload->>'event_id',p_payload->>'user_id',p_payload->>'lead_id',p_payload->>'transaction_id',''),'UTF8'),'sha256'),'hex');
  perform pg_advisory_xact_lock(hashtext('ct.locticians.bd.webhook:'||v_idem));
  select receipt_id into v_existing from integration_control.locticians_bd_webhook_receipts_v1 where idempotency_key=v_idem and received_at>now()-interval '10 minutes' order by received_at desc limit 1;
  if v_existing is not null then return jsonb_build_object('ok',true,'duplicate',true,'receipt_id',v_existing,'event_code',v_event,'state','duplicate','raw_secret_projected',false); end if;
  insert into integration_control.locticians_bd_webhook_receipts_v1(event_code,raw_event_hint,provider_event_name,risk_class,payload_sha256,body_bytes,idempotency_key,sanitized_payload,route_targets,source_fingerprint_sha256,user_agent_sha256,state,raw_secret_projected)
  values(v_event,nullif(p_event_hint,''),v_provider_name,v_risk,p_body_sha256,p_body_bytes,v_idem,coalesce(p_payload,'{}'::jsonb),v_targets,p_source_fingerprint_sha256,p_user_agent_sha256,v_state,false) returning receipt_id into v_receipt;
  for v_target in select value from jsonb_array_elements_text(v_targets) loop
    insert into integration_control.locticians_bd_webhook_dispatch_v1(receipt_id,event_code,target_ref,risk_class,state,authority_note,payload)
    values(v_receipt,v_event,v_target,v_risk,'queued',case when v_risk='D2' then 'Webhook event may inform governed D2 processing; receipt does not authorize money movement, provider mutation, destructive delete, refund, payout, settlement, or D3.' else 'Webhook event is evidence/input only; downstream authority remains bounded by target contract.' end,jsonb_build_object('receipt_id',v_receipt,'event_code',v_event,'payload_sha256',p_body_sha256,'sanitized_payload',coalesce(p_payload,'{}'::jsonb))) on conflict(receipt_id,target_ref) do nothing;
  end loop;
  v_dail:=chlom_runtime.append_dail_event('locticians.bd.webhook.received','provider_webhook',v_event,jsonb_build_object('receipt_id',v_receipt,'event_code',v_event,'provider_event_name',v_provider_name,'risk_class',v_risk,'payload_sha256',p_body_sha256,'body_bytes',p_body_bytes,'targets',v_targets,'state',v_state,'raw_secret_projected',false,'raw_payload_projected_to_dail',false),'Brilliant Directories / PentaWebhook',null,'PentaWire','1.0.0',v_idem,null,'ct.locticians.brilliant-directories.webhook-fabric.v1',null,'restricted');
  return jsonb_build_object('ok',true,'duplicate',false,'receipt_id',v_receipt,'event_code',v_event,'provider_event_name',v_provider_name,'risk_class',v_risk,'targets',v_targets,'state',v_state,'dail_event_id',v_dail->>'event_id','raw_secret_projected',false);
end $function$;

create or replace function integration_control.locticians_bd_webhook_enqueue_v1(p_hook_token text,p_event_hint text,p_payload jsonb,p_body_sha256 text,p_body_bytes integer,p_source_fingerprint_sha256 text default null,p_user_agent_sha256 text default null)
returns jsonb language plpgsql security definer set search_path to 'pg_catalog','integration_control','extensions' as $function$
declare v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),''); v_expected text; v_request_key text; v_intake uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if p_hook_token is null or length(p_hook_token)<30 then raise exception 'invalid_webhook_binding'; end if;
  if p_body_sha256 is null or p_body_sha256!~'^[0-9a-f]{64}$' then raise exception 'invalid_payload_sha256'; end if;
  if p_body_bytes is null or p_body_bytes<0 or p_body_bytes>1048576 then raise exception 'payload_size_rejected'; end if;
  select hook_id::text into v_expected from integration_control.locticians_bd_webhook_bindings_v1 where binding_key='ct.locticians.bd.webhook.v1' and state in ('staged','active') limit 1;
  if v_expected is null or p_hook_token<>v_expected then raise exception 'invalid_webhook_binding'; end if;
  v_request_key:=encode(extensions.digest(convert_to(coalesce(trim(p_event_hint),'')||':'||p_body_sha256||':'||coalesce(p_payload->>'id',p_payload->>'event_id',p_payload->>'user_id',p_payload->>'member_id',p_payload->>'lead_id',p_payload->>'transaction_id',''),'UTF8'),'sha256'),'hex');
  insert into integration_control.locticians_bd_webhook_intake_v1(event_hint,sanitized_payload,body_sha256,body_bytes,source_fingerprint_sha256,user_agent_sha256,request_key,state)
  values(nullif(trim(p_event_hint),''),coalesce(p_payload,'{}'::jsonb),p_body_sha256,p_body_bytes,p_source_fingerprint_sha256,p_user_agent_sha256,v_request_key,'queued') returning intake_id into v_intake;
  return jsonb_build_object('ok',true,'accepted',true,'intake_id',v_intake,'state','queued','request_key',v_request_key,'raw_secret_projected',false);
end $function$;

create or replace function public.locticians_bd_webhook_enqueue_v1(p_hook_token text,p_event_hint text,p_payload jsonb,p_body_sha256 text,p_body_bytes integer,p_source_fingerprint_sha256 text default null,p_user_agent_sha256 text default null)
returns jsonb language sql security definer set search_path to 'pg_catalog','integration_control' as $function$
select integration_control.locticians_bd_webhook_enqueue_v1(p_hook_token,p_event_hint,p_payload,p_body_sha256,p_body_bytes,p_source_fingerprint_sha256,p_user_agent_sha256);
$function$;
revoke all on function public.locticians_bd_webhook_enqueue_v1(text,text,jsonb,text,integer,text,text) from public,anon,authenticated;
grant execute on function public.locticians_bd_webhook_enqueue_v1(text,text,jsonb,text,integer,text,text) to service_role;

create or replace function integration_control.locticians_bd_webhook_process_intake_v1(p_limit integer default 50)
returns jsonb language plpgsql security definer set search_path to 'pg_catalog','integration_control' as $function$
declare v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),''); r record; v_hook text; v_result jsonb; v_processed int:=0; v_duplicates int:=0; v_retries int:=0; v_failed int:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if coalesce(p_limit,0)<1 or p_limit>500 then raise exception 'invalid_limit'; end if;
  select hook_id::text into v_hook from integration_control.locticians_bd_webhook_bindings_v1 where binding_key='ct.locticians.bd.webhook.v1' and state in ('staged','active') limit 1;
  if v_hook is null then return jsonb_build_object('state','hold','reason','webhook_binding_unavailable','processed',0); end if;
  for r in select * from integration_control.locticians_bd_webhook_intake_v1 where state in ('queued','retry') and next_attempt_at<=now() order by received_at for update skip locked limit p_limit loop
    update integration_control.locticians_bd_webhook_intake_v1 set state='processing',attempt_count=attempt_count+1,updated_at=now(),last_error=null where intake_id=r.intake_id;
    begin
      v_result:=integration_control.locticians_bd_webhook_ingest_v1(v_hook,r.event_hint,r.sanitized_payload,r.body_sha256,r.body_bytes,r.source_fingerprint_sha256,r.user_agent_sha256);
      if coalesce((v_result->>'duplicate')::boolean,false) then update integration_control.locticians_bd_webhook_intake_v1 set state='duplicate',receipt_id=nullif(v_result->>'receipt_id','')::uuid,completed_at=now(),updated_at=now() where intake_id=r.intake_id; v_duplicates:=v_duplicates+1;
      else update integration_control.locticians_bd_webhook_intake_v1 set state='processed',receipt_id=nullif(v_result->>'receipt_id','')::uuid,completed_at=now(),updated_at=now() where intake_id=r.intake_id; v_processed:=v_processed+1; end if;
    exception when others then
      if r.attempt_count+1>=5 then update integration_control.locticians_bd_webhook_intake_v1 set state='failed',last_error=left(sqlerrm,1000),completed_at=now(),updated_at=now() where intake_id=r.intake_id; v_failed:=v_failed+1;
      else update integration_control.locticians_bd_webhook_intake_v1 set state='retry',last_error=left(sqlerrm,1000),next_attempt_at=now()+make_interval(secs=>least(300,15*(r.attempt_count+1))),updated_at=now() where intake_id=r.intake_id; v_retries:=v_retries+1; end if;
    end;
  end loop;
  return jsonb_build_object('state','ok','processed',v_processed,'duplicates',v_duplicates,'retries',v_retries,'failed',v_failed,'raw_secret_projected',false,'at',clock_timestamp());
end $function$;

create or replace function public.locticians_bd_webhook_process_intake_v1(p_limit integer default 50)
returns jsonb language sql security definer set search_path to 'pg_catalog','integration_control' as $function$ select integration_control.locticians_bd_webhook_process_intake_v1(p_limit); $function$;
revoke all on function public.locticians_bd_webhook_process_intake_v1(integer) from public,anon,authenticated;
grant execute on function public.locticians_bd_webhook_process_intake_v1(integer) to service_role;

select cron.schedule('ct-locticians-bd-webhook-intake-worker-v1','* * * * *',$$select integration_control.locticians_bd_webhook_process_intake_v1(100);$$)
where not exists(select 1 from cron.job where jobname='ct-locticians-bd-webhook-intake-worker-v1');

-- Provider record identities are metadata only; token equality is intentionally not asserted because BD does not re-return one-time tokens.
update integration_control.locticians_provider_key_lanes_v1 set metadata=metadata||jsonb_build_object(
  'provider_key_id',case lane_id when 'ct.locticians.bd.personas.hot.v1' then 19 when 'ct.locticians.bd.personas.warm.v1' then 21 when 'ct.locticians.bd.personas.cold.v1' then 22 when 'ct.locticians.bd.personas.emergency.1.v1' then 23 when 'ct.locticians.bd.personas.emergency.2.v1' then 24 end,
  'provider_record_name',case lane_id when 'ct.locticians.bd.personas.hot.v1' then 'Personas 1' when 'ct.locticians.bd.personas.warm.v1' then 'Personas 2' when 'ct.locticians.bd.personas.cold.v1' then 'Personas 3' when 'ct.locticians.bd.personas.emergency.1.v1' then 'Emergency Penta Fallback' when 'ct.locticians.bd.personas.emergency.2.v1' then 'Emergency Penta Fallback 2' end,
  'provider_identity_mapping_basis','provider record identity/name/creation sequence; provider does not re-return one-time token after creation','token_equality_asserted',false,'secret_material_exposed',false
),updated_at=now() where lane_id in ('ct.locticians.bd.personas.hot.v1','ct.locticians.bd.personas.warm.v1','ct.locticians.bd.personas.cold.v1','ct.locticians.bd.personas.emergency.1.v1','ct.locticians.bd.personas.emergency.2.v1');

insert into integration_control.penta_wire_read_adapters_v1(service_id,adapter_kind,exact_contract,transport_ref,allowed_operations,public_projection,provider_write,credential_forwarding,authority_effect,state,evidence,created_at,updated_at)
values('locticians_bd_webhook','PUBLIC_HTTP','ct.locticians.bd.webhook.health.v1','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/locticians-bd-webhook-v1',jsonb_build_array('health.read'),true,false,false,'none','active',jsonb_build_object('projection','unauthenticated GET health only','inbound_post_contract','ct.locticians.brilliant-directories.webhook-fabric.v1','inbound_post_public_safe',false,'provider_write',false,'credential_forwarding',false,'authority_expansion',false,'raw_hook_projected',false),now(),now())
on conflict(service_id) do update set adapter_kind=excluded.adapter_kind,exact_contract=excluded.exact_contract,transport_ref=excluded.transport_ref,allowed_operations=excluded.allowed_operations,public_projection=true,provider_write=false,credential_forwarding=false,authority_effect='none',state='active',evidence=excluded.evidence,updated_at=now();

commit;
