-- CrownThrive CHLOM / PentaSecurity
-- Direct-callable SECURITY DEFINER write-surface hardening expansion v2.
--
-- Fresh independent PentaCertifier and ThriveBase catalog readback on 2026-08-31
-- established a broader 182-function role-EXECUTE least-privilege surface. Most
-- private-schema functions are not directly callable by anon/authenticated because
-- those roles lack schema USAGE. This bounded expansion does NOT claim universal
-- closure. It hardens four verified public-schema state-changing mirror callbacks
-- that are directly role-callable today and were outside the prior 22-function PR
-- #1962 cohort.
--
-- Authority boundary: ACL-only. No function body, credential, provider write,
-- money movement, D3/sovereign state, rights/legal commitment, or authority
-- expansion is created by this migration.

begin;

do $$
declare
  v_sig text;
  v_required text[] := array[
    'public.thrivebase_sheet_mirror_record_failure_v1(uuid,uuid,text,text,jsonb)',
    'public.thrivebase_sheet_mirror_record_folder_v1(text,text,text,jsonb)',
    'public.thrivebase_sheet_mirror_record_progress_v1(uuid,uuid,text,text,integer,integer,bigint,boolean,text,text,jsonb)',
    'public.thrivebase_sheet_mirror_record_provision_v1(uuid,uuid,integer,text,text,text,jsonb)'
  ];
begin
  foreach v_sig in array v_required loop
    if to_regprocedure(v_sig) is null then
      raise exception 'PentaSecurity direct-write ACL expansion source/runtime drift: required function missing: %', v_sig;
    end if;
    if not (select p.prosecdef from pg_proc p where p.oid=to_regprocedure(v_sig)) then
      raise exception 'PentaSecurity direct-write ACL expansion expected SECURITY DEFINER function: %', v_sig;
    end if;
  end loop;
end
$$;

revoke execute on function public.thrivebase_sheet_mirror_record_failure_v1(uuid,uuid,text,text,jsonb) from public, anon, authenticated;
revoke execute on function public.thrivebase_sheet_mirror_record_folder_v1(text,text,text,jsonb) from public, anon, authenticated;
revoke execute on function public.thrivebase_sheet_mirror_record_progress_v1(uuid,uuid,text,text,integer,integer,bigint,boolean,text,text,jsonb) from public, anon, authenticated;
revoke execute on function public.thrivebase_sheet_mirror_record_provision_v1(uuid,uuid,integer,text,text,text,jsonb) from public, anon, authenticated;

grant execute on function public.thrivebase_sheet_mirror_record_failure_v1(uuid,uuid,text,text,jsonb) to service_role;
grant execute on function public.thrivebase_sheet_mirror_record_folder_v1(text,text,text,jsonb) to service_role;
grant execute on function public.thrivebase_sheet_mirror_record_progress_v1(uuid,uuid,text,text,integer,integer,bigint,boolean,text,text,jsonb) to service_role;
grant execute on function public.thrivebase_sheet_mirror_record_provision_v1(uuid,uuid,integer,text,text,text,jsonb) to service_role;

commit;
