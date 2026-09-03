-- Fail-closed recovery contract for App Factory provider-dispatch-sync ACL containment v1.
-- The incident-observed end-user EXECUTE grants are a known security defect and are never restored.
-- Recovery is exact-definition-bound and reasserts the safe service-role-only execution boundary.

DO $preflight$
DECLARE
  v_oid oid := to_regprocedure('public.app_factory_provider_dispatch_sync(text,text)');
  v_definition_sha256 text;
BEGIN
  IF v_oid IS NULL THEN
    RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_PROVIDER_DISPATCH_SYNC_NOT_FOUND';
  END IF;
  IF NOT (SELECT p.prosecdef FROM pg_proc p WHERE p.oid = v_oid) THEN
    RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_PROVIDER_DISPATCH_SYNC_SECURITY_DEFINER_EXPECTED';
  END IF;
  SELECT encode(extensions.digest(convert_to(pg_get_functiondef(v_oid),'UTF8'),'sha256'),'hex')
    INTO v_definition_sha256;
  IF v_definition_sha256 <> '1e4a7c1696180fc89fe5aff3f11f581cda1b4cc071124bc4c760b06e7beabb5f' THEN
    RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_PROVIDER_DISPATCH_SYNC_DEFINITION_DRIFT:%', v_definition_sha256;
  END IF;
END
$preflight$;

REVOKE ALL ON FUNCTION public.app_factory_provider_dispatch_sync(text,text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_provider_dispatch_sync(text,text)
  TO service_role;

DO $readback$
BEGIN
  IF has_function_privilege('anon','public.app_factory_provider_dispatch_sync(text,text)','EXECUTE') THEN
    RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_PROVIDER_DISPATCH_SYNC_ANON_EXECUTE_PRESENT';
  END IF;
  IF has_function_privilege('authenticated','public.app_factory_provider_dispatch_sync(text,text)','EXECUTE') THEN
    RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_PROVIDER_DISPATCH_SYNC_AUTHENTICATED_EXECUTE_PRESENT';
  END IF;
  IF NOT has_function_privilege('service_role','public.app_factory_provider_dispatch_sync(text,text)','EXECUTE') THEN
    RAISE EXCEPTION 'ROLLBACK_APP_FACTORY_PROVIDER_DISPATCH_SYNC_SERVICE_ROLE_EXECUTE_MISSING';
  END IF;
END
$readback$;
