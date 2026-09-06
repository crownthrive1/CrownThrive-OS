create or replace function crm.penta_marketer_rowan_html_finalize_v1(p_render jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path to 'pg_catalog','crm','integration_control','public'
as $$
declare
  v_html text:=coalesce(p_render->>'html','');
  v_coffee_url text;
  v_refill_url text;
  v_support_html text;
  v_suffix text:='</td></tr></table></td></tr></table></body></html>';
begin
  if coalesce((p_render->>'ready')::boolean,false) is not true
     or coalesce(p_render->>'persona_id','') <> 'ct.persona.crownthrive.ops.rowan.v1' then
    return p_render;
  end if;

  select nullif(btrim(metadata->>'coffee_url'),''),nullif(btrim(metadata->>'refill_url'),'')
    into v_coffee_url,v_refill_url
  from integration_control.penta_persona_email_html_profiles_v1
  where persona_id='ct.persona.crownthrive.ops.rowan.v1'
    and template_state='active';

  v_html:=replace(v_html,'font-family:Arial,Helvetica,sans-serif','font-family:''Comic Sans MS'',''Comic Sans'',cursive');

  if position('data-rowan-developer-footer="v1"' in v_html)=0 then
    v_support_html:='<div data-rowan-developer-footer="v1" style="font-family:''Comic Sans MS'',''Comic Sans'',cursive;margin-top:18px;padding-top:16px;border-top:1px solid #2D3748"><div style="font-size:12px;line-height:1.6;color:#D7DCE4;font-weight:700">Developer fuel ☕ — keep the builds moving.</div><div style="margin-top:12px">'
      ||case when v_coffee_url is not null then '<a href="'||crm.html_escape_v1(v_coffee_url)||'" style="display:inline-block;margin:4px;padding:10px 15px;border-radius:999px;background:#D4A72C;color:#0B1220;text-decoration:none;font-weight:900">Buy us a coffee ☕</a>' else '' end
      ||case when v_refill_url is not null then '<a href="'||crm.html_escape_v1(v_refill_url)||'" style="display:inline-block;margin:4px;padding:10px 15px;border-radius:999px;border:2px solid #D4A72C;color:#FFFFFF;text-decoration:none;font-weight:900">Refill Crown Credits ↻</a>' else '' end
      ||'</div><div style="font-size:10px;line-height:1.5;color:#818A96;margin-top:10px">Voluntary support / credit funding only. No additional rights or authority are conferred by the coffee link.</div></div>';
    if right(v_html,length(v_suffix))=v_suffix then
      v_html:=left(v_html,length(v_html)-length(v_suffix))||v_support_html||v_suffix;
    else
      v_html:=v_html||v_support_html;
    end if;
  end if;

  return p_render||jsonb_build_object(
    'html',v_html,
    'html_length',length(v_html),
    'rowan_developer_html',true,
    'rowan_font_stack','Comic Sans MS, Comic Sans, cursive',
    'rowan_support_footer',true
  );
end;
$$;

update integration_control.penta_persona_email_html_profiles_v1
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'font_stack','Comic Sans MS, Comic Sans, cursive',
      'coffee_url','https://donate.stripe.com/28E7sKfU02tkbmi3SLbAs0h',
      'coffee_product','Buy CrownThrive a Coffee ☕',
      'refill_url','https://buy.stripe.com/aFaeVc7nu5Fw2PMgFxbAs0G',
      'refill_product','Crown Credits',
      'refill_credit_amount',1000,
      'developer_footer_version','v1',
      'developer_html_required',true
    ),
    template_version='1.1.0',
    updated_at=clock_timestamp()
where persona_id='ct.persona.crownthrive.ops.rowan.v1';

create or replace function public.penta_mail_apply_persona_html_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','public','crm','integration_control'
as $$
declare
  v_persona_id text:=nullif(btrim(coalesce(new.metadata->>'assigned_persona_id','')),'');
  v_old_persona_id text;
  v_render jsonb;
  v_needs_render boolean:=false;
begin
  if v_persona_id is null or v_persona_id='ct.persona.locticians.member-success.avery.v1' then
    return new;
  end if;

  if tg_op='INSERT' then
    v_needs_render:=coalesce(length(btrim(new.body_html)),0)=0;
  else
    v_old_persona_id:=nullif(btrim(coalesce(old.metadata->>'assigned_persona_id','')),'');
    v_needs_render:=coalesce(length(btrim(new.body_html)),0)=0
      or new.subject is distinct from old.subject
      or new.body_text is distinct from old.body_text
      or v_persona_id is distinct from v_old_persona_id
      or lower(coalesce(new.metadata->>'force_html_rerender','false')) in ('true','1','yes');
  end if;

  if not v_needs_render then return new; end if;

  v_render:=crm.penta_marketer_persona_email_html_render_v1(v_persona_id,new.subject,new.body_text,new.message_type,new.metadata);
  if v_persona_id='ct.persona.crownthrive.ops.rowan.v1' and coalesce((v_render->>'ready')::boolean,false) then
    v_render:=crm.penta_marketer_rowan_html_finalize_v1(v_render);
  end if;

  if coalesce((v_render->>'ready')::boolean,false) then
    new.body_html:=v_render->>'html';
    new.metadata:=new.metadata||jsonb_build_object(
      'body_format','multipart_alternative',
      'html_standard_key',v_render->>'standard_key',
      'html_template_version',v_render->>'template_version',
      'html_persona_id',v_persona_id,
      'html_rendered_at',clock_timestamp(),
      'pentaads_decision',v_render->'pentaads_decision',
      'rowan_developer_html',coalesce((v_render->>'rowan_developer_html')::boolean,false),
      'rowan_support_footer',coalesce((v_render->>'rowan_support_footer')::boolean,false)
    ) - 'force_html_rerender';
  else
    new.metadata:=new.metadata||jsonb_build_object('html_render_hold',v_render,'html_render_checked_at',clock_timestamp());
  end if;
  return new;
end;
$$;