-- CANDIDATE ONLY — NOT APPLIED BY AGENT C
-- Packet: ct.packet.cie-interoperability-continuity.2026-08-22.v1
-- Classification: RESTRICTED_INSTITUTIONAL migration design; no credentials or private evidence.
-- Purpose: repair two live projection defects only after governed acceptance:
--   1. require the already-provisioned physical CIE child repository;
--   2. bind the public-safe interoperability contract digest.
-- This candidate must never activate runtime, voting, checkout, pricing, certification or entitlement.

begin;

do $cie_projection$
begin
  if not exists (
    select 1
    from institutional_federation.framework_package_registry
    where package_id = 'ct.framework-package.cie'
      and framework_id = 'ct.framework.cultural-imprint-engine'
      and can_vote is false
      and operationally_enabled is false
      and public_activation_allowed is false
      and exact_price_authorized is false
      and checkout_enabled is false
      and customer_entitlement_active is false
      and parent_certification_state = 'pending'
  ) then
    raise exception 'CIE fail-closed precondition mismatch; HOLD';
  end if;

  update institutional_federation.framework_package_registry
  set physical_repository_required = true,
      public_contract_digest = '7ea12daf4b4ed96824aab51e7391309951e40e9abd94ccaa6b3685e79153316e',
      metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
        'candidate_packet_id', 'ct.packet.cie-interoperability-continuity.2026-08-22.v1',
        'parent_anchor_sha', '39713b4da545da6e293045ce2a0df19bd3b63585',
        'child_proposal_head_sha', '71c82cba953e091386f4687e3875cdb8066b679f',
        'parent_draft_pr', 245,
        'child_draft_pr', 8,
        'child_repository_id', 1341314455,
        'child_federation_state', 'PROVISIONED_UNLINKED',
        'runtime_integration_allowed', false,
        'applied_only_after_governed_acceptance', true
      ),
      updated_at = now()
  where package_id = 'ct.framework-package.cie'
    and framework_id = 'ct.framework.cultural-imprint-engine'
    and can_vote is false
    and operationally_enabled is false
    and public_activation_allowed is false
    and parent_certification_state = 'pending';

  if exists (
    select 1
    from institutional_federation.framework_package_registry
    where package_id = 'ct.framework-package.cie'
      and (
        can_vote is true
        or operationally_enabled is true
        or public_activation_allowed is true
        or exact_price_authorized is true
        or checkout_enabled is true
        or customer_entitlement_active is true
      )
  ) then
    raise exception 'CIE projection escaped fail-closed state; rollback transaction';
  end if;
end
$cie_projection$;

commit;

-- Reopen/rollback trigger: contract digest, parent anchor, child repository ID,
-- lifecycle state, Agent-D requirement, IP classification, or current-main topology changes.
-- Rollback method before any production use: restore the prior row from the exact
-- read-before-write snapshot captured by the independent operator; do not erase audit history.
