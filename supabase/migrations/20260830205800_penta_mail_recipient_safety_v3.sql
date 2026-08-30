-- PentaMail/PentaMarketer recipient safety v3
-- Builder: PentaBuild + PentaMail + PentaMarketer
-- Independent certification: PentaCertifier
-- Incident: UNSAFE_PLACEHOLDER_RECIPIENT_ACCEPTED
-- Rollback doctrine: never restore the unsafe validator. If this repair causes an
-- operational regression, fail closed by disabling governed cold outreach via
-- crm.outbound_config.cold_outreach_enabled until a superseding repair certifies.

create or replace function crm.public_business_email_safe_v2(p_email text)
returns boolean
language sql
immutable
set search_path to 'pg_catalog'
as $function$
  with e as (
    select lower(btrim(coalesce(p_email,''))) as email
  ), parts as (
    select email,split_part(email,'@',1) as local_part,split_part(email,'@',2) as domain
    from e
  ), parsed as (
    select email,local_part,domain,reverse(split_part(reverse(domain),'.',1)) as tld
    from parts
  )
  select
    email ~ '^[a-z0-9.!#$%&''*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,63}$'
    and local_part !~ '^[.-]|[.-]$'
    and domain !~ '\.\.|^-|-$'
    and email not in ('user@domain.com','email@example.com','name@example.com')
    and local_part not in ('filler','placeholder','test','testing','sample','fake','dummy')
    and domain !~ '(wixpress|sentry|ndiscovered|example|domain\.com|w3\.org|cloudflare|schema\.org|wordpress|shopify)'
    and tld not in ('png','jpg','jpeg','gif','svg','webp','ico','css','js','json','xml','pdf','woff','woff2','ttf','eot','map')
    and local_part !~ '^(instagram|facebook|twitter|x|linkedin|youtube|tiktok|pinterest)[._+\-]*$'
  from parsed;
$function$;

create or replace function crm.penta_marketer_external_recipient_allowed_v1(p_recipient text, p_work_id uuid)
returns boolean
language plpgsql
stable security definer
set search_path to 'pg_catalog','crm','public'
as $function$
declare
  v_recipient text := lower(btrim(coalesce(p_recipient,'')));
  v_required integer;
  v_ceiling integer;
begin
  if current_user not in ('postgres','service_role') then return false; end if;
  if v_recipient !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then return false; end if;
  if not crm.public_business_email_safe_v2(v_recipient) then return false; end if;
  if public.penta_marketer_suppressed_v1(v_recipient) then return false; end if;

  select substring(w.authority_class from 2)::integer,
         substring(a.risk_ceiling from 2)::integer
    into v_required,v_ceiling
  from crm.penta_marketer_work_queue_v1 w
  join crm.penta_marketer_agents_v2 a on a.agent_id=w.assigned_agent_id
  join crm.penta_marketer_personas_v1 p on p.persona_id=w.assigned_persona_id
  where w.work_id=p_work_id
    and lower(w.recipient)=v_recipient
    and w.channel='email'
    and w.state in ('routed','queued','dispatching')
    and w.authority_class in ('D0','D1','D2')
    and a.enabled=true and a.state='active'
    and p.state='approved'
  limit 1;

  if v_required is null or v_ceiling is null then return false; end if;
  return v_required <= v_ceiling;
end
$function$;

create or replace function crm.penta_recipient_safety_regression_v3()
returns jsonb
language plpgsql
stable security definer
set search_path to 'pg_catalog','crm','public'
as $function$
declare
  v_placeholder boolean;
  v_image boolean;
  v_normal boolean;
  v_gate_bound boolean;
  v_total integer:=4;
  v_pass integer:=0;
begin
  v_placeholder := not crm.public_business_email_safe_v2('filler@godaddy.com');
  v_image := not crm.public_business_email_safe_v2('asset@2x.png');
  v_normal := crm.public_business_email_safe_v2('owner@businessmail.net');
  v_gate_bound := position('public_business_email_safe_v2' in pg_get_functiondef('crm.penta_marketer_external_recipient_allowed_v1(text,uuid)'::regprocedure))>0;
  if v_placeholder then v_pass:=v_pass+1; end if;
  if v_image then v_pass:=v_pass+1; end if;
  if v_normal then v_pass:=v_pass+1; end if;
  if v_gate_bound then v_pass:=v_pass+1; end if;
  return jsonb_build_object(
    'contract','ct.pentamail.recipient-safety.v3',
    'cases',v_total,'passed',v_pass,'failed',v_total-v_pass,'all_passed',v_pass=v_total,
    'placeholder_rejected',v_placeholder,'asset_tld_rejected',v_image,
    'normal_business_format_allowed',v_normal,'final_send_gate_bound_to_safe_validator',v_gate_bound,
    'provider_send_performed',false,'observed_at',now()
  );
end;
$function$;
