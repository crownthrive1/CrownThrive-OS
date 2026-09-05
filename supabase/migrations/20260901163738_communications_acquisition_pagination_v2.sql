-- Normalize Brilliant Directories opaque next_page tokens at the canonical queue boundary.
-- Prevents any current or future acquisition implementation from sending the opaque token as page=.

create or replace function crm.bd_next_page_descriptor_v1(p_cursor text)
returns jsonb
language plpgsql
immutable
strict
set search_path to 'pg_catalog','crm'
as $function$
declare
  v_decoded text;
  v_match text[];
  v_page integer;
  v_page_size integer;
begin
  if btrim(p_cursor) ~ '^[0-9]{1,9}$' then
    return jsonb_build_object(
      'valid',true,
      'page',(btrim(p_cursor))::integer,
      'page_size',null,
      'format','numeric'
    );
  end if;

  begin
    v_decoded:=convert_from(decode(btrim(p_cursor),'base64'),'UTF8');
  exception when others then
    return jsonb_build_object('valid',false,'reason','base64_decode_failed');
  end;

  v_match:=regexp_match(v_decoded,'^([0-9]{1,9})\*_\*([0-9]{1,3})$');
  if v_match is null then
    return jsonb_build_object('valid',false,'reason','descriptor_shape_invalid');
  end if;

  v_page:=v_match[1]::integer;
  v_page_size:=v_match[2]::integer;
  if v_page<1 or v_page_size<1 or v_page_size>100 then
    return jsonb_build_object('valid',false,'reason','descriptor_bounds_invalid');
  end if;

  return jsonb_build_object(
    'valid',true,
    'page',v_page,
    'page_size',v_page_size,
    'format','bd_base64_page_descriptor'
  );
end;
$function$;

create or replace function crm.normalize_bd_provider_page_cursor_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','crm'
as $function$
declare
  v_descriptor jsonb;
begin
  if new.campaign_id<>'ct.pentamarketer.locticians.claim.20260827.v1'
     or new.provider_page_cursor is null
     or btrim(new.provider_page_cursor)='' then
    return new;
  end if;

  v_descriptor:=crm.bd_next_page_descriptor_v1(new.provider_page_cursor);
  if coalesce((v_descriptor->>'valid')::boolean,false) is not true then
    raise exception using
      errcode='22023',
      message='bd_provider_page_cursor_rejected:'||coalesce(v_descriptor->>'reason','unknown');
  end if;

  new.provider_page_cursor:=v_descriptor->>'page';
  if v_descriptor->>'page_size' is not null then
    new.provider_ingest_limit:=(v_descriptor->>'page_size')::integer;
  end if;
  return new;
end;
$function$;

drop trigger if exists normalize_bd_provider_page_cursor_v1
on crm.penta_marketer_queue_policy_v1;
create trigger normalize_bd_provider_page_cursor_v1
before insert or update of provider_page_cursor
on crm.penta_marketer_queue_policy_v1
for each row execute function crm.normalize_bd_provider_page_cursor_v1();

-- Normalize the existing provider cursor transactionally.
update crm.penta_marketer_queue_policy_v1
set provider_page_cursor=provider_page_cursor,
    updated_at=clock_timestamp()
where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1'
  and provider_page_cursor is not null;