-- App Factory production-merge RPC least-privilege hardening v1.
--
-- Incident basis (2026-09-01): production readback proved that
-- public.app_factory_merge_production_pr(text,text,boolean) is SECURITY DEFINER,
-- resolves a vaulted GitHub token, performs provider GET/PUT calls, and can merge a bounded
-- allowlist of production PR branches. The public schema is usable by anon/authenticated and
-- both roles had direct EXECUTE grants. The function body itself has no caller-role guard.
--
-- This migration contracts authority only. It does not change function bytes, allowlisted
-- repositories/branches, provider credentials, merge predicates, rights, money, votes/quorum,
-- D3, or any provider state. PostgreSQL owner execution remains intact; service_role remains
-- the sole non-owner execution path.

DO $preflight$
DECLARE
  v_oid oid := to_regprocedure('public.app_factory_merge_production_pr(text,text,boolean)');
  v_definition_sha256 text;
BEGIN
  IF v_oid IS NULL THEN
    RAISE EXCEPTION 'APP_FACTORY_MERGE_RPC_NOT_FOUND';
  END IF;
  IF NOT (SELECT p.prosecdef FROM pg_proc p WHERE p.oid=v_oid) THEN
    RAISE EXCEPTION 'APP_FACTORY_MERGE_RPC_SECURITY_DEFINER_EXPECTED';
  END IF;
  SELECT encode(extensions.digest(convert_to(pg_get_functiondef(v_oid),'UTF8'),'sha256'),'hex')
    INTO v_definition_sha256;
  IF v_definition_sha256 <> '29af46e774a7fd6fadec29f063928bc96950a6a4021d185f07dbf69ceb02f394' THEN
    RAISE EXCEPTION 'APP_FACTORY_MERGE_RPC_DEFINITION_DRIFT:%',v_definition_sha256;
  END IF;
END
$preflight$;

REVOKE ALL ON FUNCTION public.app_factory_merge_production_pr(text,text,boolean)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_merge_production_pr(text,text,boolean)
  TO service_role;

DO $readback$
BEGIN
  IF has_function_privilege('anon','public.app_factory_merge_production_pr(text,text,boolean)','EXECUTE') THEN
    RAISE EXCEPTION 'APP_FACTORY_MERGE_RPC_ANON_EXECUTE_STILL_PRESENT';
  END IF;
  IF has_function_privilege('authenticated','public.app_factory_merge_production_pr(text,text,boolean)','EXECUTE') THEN
    RAISE EXCEPTION 'APP_FACTORY_MERGE_RPC_AUTHENTICATED_EXECUTE_STILL_PRESENT';
  END IF;
  IF NOT has_function_privilege('service_role','public.app_factory_merge_production_pr(text,text,boolean)','EXECUTE') THEN
    RAISE EXCEPTION 'APP_FACTORY_MERGE_RPC_SERVICE_ROLE_EXECUTE_MISSING';
  END IF;
END
$readback$;

COMMENT ON FUNCTION public.app_factory_merge_production_pr(text,text,boolean) IS
'Privileged App Factory GitHub merge executor. Service-role only; anon/authenticated execution prohibited. Provider writes remain bounded by the function allowlist and governed release gates.';
