-- COS V1 sprint repair: keep CIE production-source reauthorization aligned with the canonical renamed child repository.
-- Exact pre/post function digests make this fail closed; no activation, provider write, money, rights, vote, quorum, or D3 authority is created.
DO $migration$
DECLARE
  v_oid oid;
  v_def text;
  v_after text;
  v_pre_sha text;
  v_post_sha text;
  v_legacy_count integer;
  v_new_count integer;
  v_legacy_only text;
BEGIN
  SELECT p.oid, pg_get_functiondef(p.oid)
    INTO v_oid, v_def
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='chlom_runtime'
    AND p.proname='reauthorize_cie_production_source_v1'
    AND pg_get_function_identity_arguments(p.oid)='p_parent_head text, p_child_head text, p_exact_version_ref text, p_content_sha256 text, p_founder_request_id uuid, p_parent_compare jsonb, p_child_compare jsonb';

  IF v_oid IS NULL THEN RAISE EXCEPTION 'cie_reauthorize_function_missing'; END IF;

  v_pre_sha := encode(extensions.digest(convert_to(v_def,'UTF8'),'sha256'),'hex');
  v_new_count := (length(v_def)-length(replace(v_def,'crownthrive1/CrownThrive-CIE-OS','')))/length('crownthrive1/CrownThrive-CIE-OS');
  v_legacy_only := replace(v_def,'crownthrive1/CrownThrive-CIE-OS','');
  v_legacy_count := (length(v_legacy_only)-length(replace(v_legacy_only,'crownthrive1/CrownThrive-CIE','')))/length('crownthrive1/CrownThrive-CIE');

  IF v_pre_sha <> '0ba29d608fb27267d842e70d74ecd8d66391ffaadc595ee91dd9825e6bd10384'
     OR v_legacy_count <> 2 OR v_new_count <> 0 THEN
    RAISE EXCEPTION 'unexpected_cie_reauthorize_prestate sha=% legacy=% new=%', v_pre_sha, v_legacy_count, v_new_count;
  END IF;

  EXECUTE replace(v_def,'crownthrive1/CrownThrive-CIE','crownthrive1/CrownThrive-CIE-OS');

  SELECT pg_get_functiondef(v_oid) INTO v_after;
  v_post_sha := encode(extensions.digest(convert_to(v_after,'UTF8'),'sha256'),'hex');
  v_new_count := (length(v_after)-length(replace(v_after,'crownthrive1/CrownThrive-CIE-OS','')))/length('crownthrive1/CrownThrive-CIE-OS');
  v_legacy_only := replace(v_after,'crownthrive1/CrownThrive-CIE-OS','');
  v_legacy_count := (length(v_legacy_only)-length(replace(v_legacy_only,'crownthrive1/CrownThrive-CIE','')))/length('crownthrive1/CrownThrive-CIE');

  IF v_post_sha <> '5e41edbc4d5115e3fb05c18bd0e8a8f2643cd21ec9728fe388f39c0196627c47'
     OR v_legacy_count <> 0 OR v_new_count <> 2 THEN
    RAISE EXCEPTION 'cie_reauthorize_poststate_failed sha=% legacy=% new=%', v_post_sha, v_legacy_count, v_new_count;
  END IF;
END
$migration$;
