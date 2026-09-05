-- App Factory institutionalization provider-dispatch RPC least-privilege containment v1.
--
-- Production security readback on 2026-09-01 proved these public-schema SECURITY DEFINER
-- functions were directly executable by anon/authenticated while resolving the internal
-- APP_FACTORY_PROVIDER_DISPATCH_TOKEN and issuing bounded provider/network dispatches.
-- Caller inventory found no database-function callers, no cron callers, and only postgres
-- executions in available pg_stat_statements evidence. This migration contracts execution
-- authority only; it does not modify provider executor bodies, credentials, release predicates,
-- rights, money, votes/quorum, D3, or provider state.

DO $preflight$
DECLARE
  v_sig text;
  v_oid oid;
  v_expected_sha text;
  v_actual_sha text;
BEGIN
  FOR v_sig, v_expected_sha IN
    SELECT * FROM (VALUES
      ('public.app_factory_institutionalize_recertification_dispatch()', '1ff2f6fbed6c40848d9989fe9cb64b3aab38607b23d3fc814da3775110a91182'),
      ('public.app_factory_institutionalize_release_dispatch()', '08ecbc29fa387b24ab8196aaeb1a6a9fab52b4dced8d3e128f897de2107c105a'),
      ('public.app_factory_merge_institutionalization_dispatch()', '1e7b4da06177c944eee21c22268e01ace12e2adb216a22a30d9c31e156b6b979'),
      ('public.app_factory_merge_recertification_dispatch()', '218a5cf728f3e083fb6d32e72201a99f01ceed1721f201a9f11cede1af95b81c')
    ) AS t(sig, expected_sha)
  LOOP
    v_oid := to_regprocedure(v_sig);
    IF v_oid IS NULL THEN
      RAISE EXCEPTION 'APP_FACTORY_INSTITUTIONALIZATION_RPC_NOT_FOUND:%', v_sig;
    END IF;
    IF NOT (SELECT p.prosecdef FROM pg_proc p WHERE p.oid=v_oid) THEN
      RAISE EXCEPTION 'APP_FACTORY_INSTITUTIONALIZATION_RPC_SECURITY_DEFINER_EXPECTED:%', v_sig;
    END IF;
    SELECT encode(extensions.digest(convert_to(pg_get_functiondef(v_oid),'UTF8'),'sha256'),'hex')
      INTO v_actual_sha;
    IF v_actual_sha <> v_expected_sha THEN
      RAISE EXCEPTION 'APP_FACTORY_INSTITUTIONALIZATION_RPC_DEFINITION_DRIFT:%:%', v_sig, v_actual_sha;
    END IF;
  END LOOP;
END
$preflight$;

REVOKE ALL ON FUNCTION public.app_factory_institutionalize_recertification_dispatch()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_institutionalize_recertification_dispatch()
  TO service_role;

REVOKE ALL ON FUNCTION public.app_factory_institutionalize_release_dispatch()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_institutionalize_release_dispatch()
  TO service_role;

REVOKE ALL ON FUNCTION public.app_factory_merge_institutionalization_dispatch()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_merge_institutionalization_dispatch()
  TO service_role;

REVOKE ALL ON FUNCTION public.app_factory_merge_recertification_dispatch()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_factory_merge_recertification_dispatch()
  TO service_role;

DO $readback$
DECLARE
  v_sig text;
BEGIN
  FOREACH v_sig IN ARRAY ARRAY[
    'public.app_factory_institutionalize_recertification_dispatch()',
    'public.app_factory_institutionalize_release_dispatch()',
    'public.app_factory_merge_institutionalization_dispatch()',
    'public.app_factory_merge_recertification_dispatch()'
  ]
  LOOP
    IF has_function_privilege('anon',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'APP_FACTORY_INSTITUTIONALIZATION_RPC_ANON_EXECUTE_STILL_PRESENT:%',v_sig;
    END IF;
    IF has_function_privilege('authenticated',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'APP_FACTORY_INSTITUTIONALIZATION_RPC_AUTHENTICATED_EXECUTE_STILL_PRESENT:%',v_sig;
    END IF;
    IF NOT has_function_privilege('service_role',v_sig,'EXECUTE') THEN
      RAISE EXCEPTION 'APP_FACTORY_INSTITUTIONALIZATION_RPC_SERVICE_ROLE_EXECUTE_MISSING:%',v_sig;
    END IF;
  END LOOP;
END
$readback$;

COMMENT ON FUNCTION public.app_factory_institutionalize_recertification_dispatch() IS
'Privileged App Factory recertification institutionalization provider dispatcher. Service-role only; end-user execution prohibited.';
COMMENT ON FUNCTION public.app_factory_institutionalize_release_dispatch() IS
'Privileged App Factory release institutionalization provider dispatcher. Service-role only; end-user execution prohibited.';
COMMENT ON FUNCTION public.app_factory_merge_institutionalization_dispatch() IS
'Privileged App Factory institutionalization merge provider dispatcher. Service-role only; end-user execution prohibited.';
COMMENT ON FUNCTION public.app_factory_merge_recertification_dispatch() IS
'Privileged App Factory recertification merge provider dispatcher. Service-role only; end-user execution prohibited.';
