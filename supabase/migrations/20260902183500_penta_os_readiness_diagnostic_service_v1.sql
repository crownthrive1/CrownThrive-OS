-- CrownThrive OS Governance & Activation Readiness Diagnostic v1
-- Forward-only catalog registration. No Stripe/provider mutation is performed here.

begin;

do $migration$
declare
  v_band developer_commerce.penta_service_price_bands_v1%rowtype;
  v_existing developer_commerce.penta_service_catalog_v1%rowtype;
begin
  select * into v_band
  from developer_commerce.penta_service_price_bands_v1
  where band_key = 'penta.deep.v1';

  if not found then
    raise exception 'required commercial band penta.deep.v1 is missing';
  end if;

  if not v_band.active or v_band.usd_cents <> 14900 then
    raise exception 'required commercial band penta.deep.v1 is not active at 14900 cents';
  end if;

  if v_band.stripe_product_id is null
     or v_band.stripe_price_id is null
     or v_band.stripe_payment_link_id is null
     or v_band.checkout_url is null then
    raise exception 'required commercial band penta.deep.v1 lacks complete existing Stripe checkout bindings';
  end if;

  select * into v_existing
  from developer_commerce.penta_service_catalog_v1
  where service_key = 'penta.os.readiness.diagnostic.v1';

  if not found then
    insert into developer_commerce.penta_service_catalog_v1 (
      service_key,
      display_name,
      description,
      service_family,
      commercial_class,
      default_band_key,
      authority_ceiling,
      requires_payment_before_execution,
      charge_on_success_only,
      provider_failure_chargeable,
      included_revision_count,
      active,
      metadata
    ) values (
      'penta.os.readiness.diagnostic.v1',
      'CrownThrive OS Governance & Activation Readiness Diagnostic',
      'A governed read-only diagnostic that compares source, deployment, PR lifecycle, Identity Fabric, PentaDND, and independent gate evidence and returns a redacted JSON plus Markdown remediation packet. It is diagnostic evidence, not independent certification.',
      'os_assurance',
      'paid_service',
      'penta.deep.v1',
      'D1',
      true,
      true,
      false,
      2,
      true,
      jsonb_build_object(
        'asset_key', 'ct.asset.penta-os-readiness-diagnostic.v1',
        'product_key', 'ct.product.penta-os-readiness-diagnostic.v1',
        'manifest_path', 'data/penta/os-readiness-diagnostic.v1.json',
        'cli_path', 'scripts/penta_os_readiness_diagnostic.py',
        'delivery_formats', jsonb_build_array('application/json', 'text/markdown'),
        'execution_mode', 'governed_read_only_snapshot',
        'checkout_inherited_from_band', true,
        'new_stripe_object_required', false,
        'independent_certification_required', true,
        'independent_certification_performed_by_service', false,
        'provider_writes', false,
        'authority_created', false,
        'rollback', 'deactivate_and_supersede_do_not_delete'
      )
    );
  else
    if v_existing.default_band_key <> 'penta.deep.v1'
       or v_existing.authority_ceiling <> 'D1'
       or v_existing.commercial_class <> 'paid_service'
       or not v_existing.requires_payment_before_execution
       or not v_existing.charge_on_success_only
       or v_existing.provider_failure_chargeable then
      raise exception 'existing penta.os.readiness.diagnostic.v1 conflicts with the governed commercial contract';
    end if;

    update developer_commerce.penta_service_catalog_v1
    set metadata = metadata || jsonb_build_object(
          'asset_key', 'ct.asset.penta-os-readiness-diagnostic.v1',
          'product_key', 'ct.product.penta-os-readiness-diagnostic.v1',
          'manifest_path', 'data/penta/os-readiness-diagnostic.v1.json',
          'cli_path', 'scripts/penta_os_readiness_diagnostic.py',
          'checkout_inherited_from_band', true,
          'new_stripe_object_required', false,
          'independent_certification_required', true,
          'provider_writes', false,
          'authority_created', false,
          'rollback', 'deactivate_and_supersede_do_not_delete'
        ),
        updated_at = now()
    where service_key = 'penta.os.readiness.diagnostic.v1';
  end if;
end
$migration$;

commit;

-- Governed rollback/recovery posture: never delete the service row. If a material
-- regression is proven, set active=false and append a superseding metadata receipt
-- through the canonical release owner after exact pre/post readback.
