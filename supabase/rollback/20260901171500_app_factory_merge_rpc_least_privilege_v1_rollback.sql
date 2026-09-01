-- Guarded rollback for App Factory production-merge RPC least-privilege hardening v1.
-- Restores the exact pre-containment role ACL only if the provider-writing function bytes are
-- still the incident-observed definition. This rollback intentionally re-opens the prior
-- anon/authenticated execution state and therefore must be used only for controlled recovery.

DO $preflight$
DECLARE
  v_oid oid := to_regprocedure('public.app_factory_merge_production_pr(text,text,boolean)');
  v_definition_sha256 text;
BEGIN
  IF v_oid IS NULL THEN
    RAISE EXCEPTION 'APP_FACTORY_MERGE_RPC_NOT_FOUND';
  END IF;
  SELECT encode(extensions.digest(convert_to(pg_get_functiondef(v_oid),'UTF8'),'sha256'),'hex')
    INTO v_definition_sha256;
  IF v_definition_sha256 <> '29af46e774a7fd6fadec29f063928bc96950a6a4021d185f07dbf69ceb02f394' THEN
    RAISE EXCEPTION 'ROLLBACK_REFUSES_CHANGED_APP_FACTORY_MERGE_RPC:%',v_definition_sha256;
  END IF;
END
$preflight$;

REVOKE ALL ON FUNCTION public.app_factory_merge_production_pr(text,text,boolean)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.app_factory_merge_production_pr(text,text,boolean)
  TO anon, authenticated, service_role;

DO $readback$
BEGIN
  IF NOT has_function_privilege('anon','public.app_factory_merge_production_pr(text,text,boolean)','EXECUTE') THEN
    RAISE EXCEPTION 'ROLLBACK_ANON_EXECUTE_NOT_RESTORED';
  END IF;
  IF NOT has_function_privilege('authenticated','public.app_factory_merge_production_pr(text,text,boolean)','EXECUTE') THEN
    RAISE EXCEPTION 'ROLLBACK_AUTHENTICATED_EXECUTE_NOT_RESTORED';
  END IF;
  IF NOT has_function_privilege('service_role','public.app_factory_merge_production_pr(text,text,boolean)','EXECUTE') THEN
    RAISE EXCEPTION 'ROLLBACK_SERVICE_ROLE_EXECUTE_NOT_RESTORED';
  END IF;
END
$readback$;
