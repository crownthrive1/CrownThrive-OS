-- Transactional acceptance for the #1962 direct-callable write-surface expansion.
-- The test is intentionally bounded to five newly classified public-schema writes.
-- It does not assert closure of the broader PentaCertifier/catalog role-EXECUTE
-- finding. Private-schema reachability and intentionally public/authenticated reads
-- remain separate owner-policy classification work.

begin;

do $$
declare
  v_sig text;
  v_oid oid;
  v_config text[];
  v_required text[] := array[
    'public.thrivebase_sheet_mirror_record_failure_v1(uuid,uuid,text,text,jsonb)',
    'public.thrivebase_sheet_mirror_record_folder_v1(text,text,text,jsonb)',
    'public.thrivebase_sheet_mirror_record_progress_v1(uuid,uuid,text,text,integer,integer,bigint,boolean,text,text,jsonb)',
    'public.thrivebase_sheet_mirror_record_provision_v1(uuid,uuid,integer,text,text,text,jsonb)',
    'public.penta_ads_scan_ingest_v1(bigint,text,integer,text,text,jsonb,text,jsonb)'
  ];
begin
  foreach v_sig in array v_required loop
    v_oid:=to_regprocedure(v_sig);
    if v_oid is null then raise exception 'missing direct-write SECURITY DEFINER function: %',v_sig; end if;
    if not (select p.prosecdef from pg_proc p where p.oid=v_oid) then raise exception 'SECURITY DEFINER posture lost: %',v_sig; end if;
    select p.proconfig into v_config from pg_proc p where p.oid=v_oid;
    if v_config is null or not exists(select 1 from unnest(v_config) cfg where cfg like 'search_path=%') then
      raise exception 'pinned search_path required: %',v_sig;
    end if;
    if has_function_privilege('public',v_oid,'EXECUTE') then raise exception 'PUBLIC execute remains: %',v_sig; end if;
    if has_function_privilege('anon',v_oid,'EXECUTE') then raise exception 'anon execute remains: %',v_sig; end if;
    if has_function_privilege('authenticated',v_oid,'EXECUTE') then raise exception 'authenticated execute remains: %',v_sig; end if;
    if not has_function_privilege('service_role',v_oid,'EXECUTE') then raise exception 'service_role execute missing: %',v_sig; end if;
  end loop;
end
$$;

rollback;
