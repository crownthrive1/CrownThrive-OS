-- App Factory provider-dispatch synchronization RPC least-privilege source convergence v1.
--
-- Current production readback on 2026-09-02 proves
-- public.app_factory_provider_dispatch_sync(text,text) is SECURITY DEFINER, resolves
-- privileged provider-dispatch capability, and is already contained to service_role/owner.
-- This migration converges canonical source to that safe runtime boundary. It contracts ACLs
-- only and performs no provider call, credential mutation, money/right action, D3 action,
-- vote/quorum action, or authority expansion.

DO $preflight$
DECLARE
  v_oid oid := to_regprocedure('public.app_factory_provider_dispatch_sync(text,text)');
  v_definition_sha256 text;
BEGIN
  IF v_oid IS NULL THEN
    RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_SYNC_RPC_NOT_FOUND';
  END IF;
  IF NOT (SELECT p.prosecdef FROM pg_proc p WHERE p.oid = v_oid) THEN
    RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_SYNC_RPC_SECURITY_DEFINER_EXPECTED';
  END IF;
  SELECT encode(extensions.digest(convert_to(pg_get_functiondef(v_oid),'UTF8'),'sha256'),'hex')
    INTO v_definition_sha256;
  IF v_definition_sha256 <> '1e4a7c1696180fc89fe5aff3f11f581cda1b4cc071124bc4c760b06e7beabb5f' THEN
    RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_SYNC_RPC_DEFINITION_DRIFT:%', v_definition_sha256;
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
    RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_SYNC_RPC_ANON_EXECUTE_STILL_PRESENT';
  END IF;
  IF has_function_privilege('authenticated','public.app_factory_provider_dispatch_sync(text,text)','EXECUTE') THEN
    RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_SYNC_RPC_AUTHENTICATED_EXECUTE_STILL_PRESENT';
  END IF;
  IF NOT has_function_privilege('service_role','public.app_factory_provider_dispatch_sync(text,text)','EXECUTE') THEN
    RAISE EXCEPTION 'APP_FACTORY_PROVIDER_DISPATCH_SYNC_RPC_SERVICE_ROLE_EXECUTE_MISSING';
  END IF;
END
$readback$;

COMMENT ON FUNCTION public.app_factory_provider_dispatch_sync(text,text) IS
'Privileged App Factory provider-dispatch synchronization executor. Service-role only; end-user execution prohibited. Provider effects remain bounded by existing runtime controls.';
