-- CIE interoperability v2 controlled-test registry reconciliation
-- Classification: RESTRICTED_INSTITUTIONAL operation; this file contains no secret values.
-- Exact parent main observed: c7f14b73cff09f00a8f94f15a8587289de18ff7b
-- Exact child candidate head: 6b4db00c49e3b988e664a7e1944cb77e0f064054
-- Live dispatch, activation, voting, pricing, checkout and entitlement remain disabled.

begin;

-- Fail before mutation if the protected capability identity or safety invariants drift.
do $$
begin
  if not exists (
    select 1 from institutional_federation.framework_package_registry
    where package_id = 'ct.framework-package.cie'
  ) then raise exception 'HOLD:missing_cie_framework_package'; end if;
  if not exists (
    select 1 from institutional_federation.framework_package_registry
    where package_id = 'ct.framework-package.convergent-ecosystem'
  ) then raise exception 'HOLD:missing_convergent_framework_package'; end if;
  if (select count(*) from chlom_runtime.capability_contracts where capability_id='ct.cap.vault.cie.advisory') <> 1
     or (select count(*) from chlom_runtime.vaulted_capability_registry where capability_id='ct.cap.vault.cie.advisory') <> 1
  then raise exception 'HOLD:capability_registry_cardinality'; end if;
  if exists (
    select 1 from (
      select immutable_digest, invocation_state, requires_independent_verifier, body_exposure_allowed
      from chlom_runtime.capability_contracts where capability_id='ct.cap.vault.cie.advisory'
      union all
      select immutable_digest, invocation_state, requires_independent_verifier, body_exposure_allowed
      from chlom_runtime.vaulted_capability_registry where capability_id='ct.cap.vault.cie.advisory'
    ) x where immutable_digest <> 'd6955a7bb0ebecdc5cd45e458af4ccb0ad911ef52e0a0634426d5199b1a89b42'
       or invocation_state <> 'controlled_test'
       or requires_independent_verifier is not true
       or body_exposure_allowed is not false
  ) then raise exception 'HOLD:capability_digest_or_safety_invariant_drift'; end if;
end $$;

update institutional_federation.framework_package_registry
set operationally_enabled = false,
    public_activation_allowed = false,
    exact_price_authorized = false,
    checkout_enabled = false,
    customer_entitlement_active = false,
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'cie_interoperability_packet','v2',
      'interoperability_packet_state','PREPARED_NOT_ACTIVATED',
      'parent_main_reconciled_sha','c7f14b73cff09f00a8f94f15a8587289de18ff7b',
      'child_repository','crownthrive1/CrownThrive-CIE',
      'child_candidate_pr',1,
      'child_candidate_head','6b4db00c49e3b988e664a7e1944cb77e0f064054',
      'child_base_sha','073da74bb6eb1fde31b9a6d0321bb85baf5ac8fd',
      'child_public_contract_bundle_digest','12f45147dd6298ce68f28bf8e1f73e029f2711b23822c632976e316fcf08525f',
      'chlom_capability_id','ct.cap.vault.cie.advisory',
      'chlom_capability_digest','d6955a7bb0ebecdc5cd45e458af4ccb0ad911ef52e0a0634426d5199b1a89b42',
      'oidc_current_head_state','STALE_OR_MISSING_REPROOF_REQUIRED',
      'agent_d_parent_certification_state','pending',
      'live_private_dispatch_enabled',false,
      'repository_federation_state','PROVISIONED_UNLINKED'
    )
where package_id = 'ct.framework-package.cie';

update institutional_federation.framework_package_registry
set operationally_enabled = false,
    public_activation_allowed = false,
    exact_price_authorized = false,
    checkout_enabled = false,
    customer_entitlement_active = false,
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'cie_handoff_state','RESEARCH_CANDIDATE_ONLY',
      'cie_source_child_head','6b4db00c49e3b988e664a7e1944cb77e0f064054',
      'implementation_allowed',false,
      'operational_activation_allowed',false,
      'registry_growth_is_certification',false
    )
where package_id = 'ct.framework-package.convergent-ecosystem';

update chlom_runtime.capability_contracts
set allowed_agent_ids = array(
      select distinct agent_id
      from unnest(coalesce(allowed_agent_ids, array[]::text[]) || array[
        'ct.framework-agent.cie','ct.subagent.cie-interoperability'
      ]::text[]) agent_id
      order by agent_id
    ),
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'cie_interoperability_binding','v2',
      'binding_state','PREPARED_NOT_ACTIVATED',
      'child_candidate_head','6b4db00c49e3b988e664a7e1944cb77e0f064054',
      'public_contract_bundle_digest','12f45147dd6298ce68f28bf8e1f73e029f2711b23822c632976e316fcf08525f',
      'live_dispatch_enabled',false,
      'transport_identities_non_voting',true,
      'parent_certification_state','pending',
      'oidc_current_head_state','STALE_OR_MISSING_REPROOF_REQUIRED'
    )
where capability_id = 'ct.cap.vault.cie.advisory';

update chlom_runtime.vaulted_capability_registry
set allowed_agent_ids = array(
      select distinct agent_id
      from unnest(coalesce(allowed_agent_ids, array[]::text[]) || array[
        'ct.framework-agent.cie','ct.subagent.cie-interoperability'
      ]::text[]) agent_id
      order by agent_id
    ),
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'cie_interoperability_binding','v2',
      'binding_state','PREPARED_NOT_ACTIVATED',
      'child_candidate_head','6b4db00c49e3b988e664a7e1944cb77e0f064054',
      'public_contract_bundle_digest','12f45147dd6298ce68f28bf8e1f73e029f2711b23822c632976e316fcf08525f',
      'live_dispatch_enabled',false,
      'transport_identities_non_voting',true,
      'parent_certification_state','pending',
      'oidc_current_head_state','STALE_OR_MISSING_REPROOF_REQUIRED'
    )
where capability_id = 'ct.cap.vault.cie.advisory';

commit;

-- Required readback: both capability tables must agree, all safety booleans remain fail-closed,
-- CIE remains non-operational, and Convergent remains research-only.
select package_id, package_state, operationally_enabled, public_activation_allowed,
       exact_price_authorized, checkout_enabled, customer_entitlement_active, metadata
from institutional_federation.framework_package_registry
where package_id in ('ct.framework-package.cie','ct.framework-package.convergent-ecosystem')
order by package_id;

select 'capability_contracts' as source, capability_id, allowed_agent_ids, invocation_state,
       requires_independent_verifier, body_exposure_allowed, immutable_digest, metadata
from chlom_runtime.capability_contracts where capability_id='ct.cap.vault.cie.advisory'
union all
select 'vaulted_capability_registry' as source, capability_id, allowed_agent_ids, invocation_state,
       requires_independent_verifier, body_exposure_allowed, immutable_digest, metadata
from chlom_runtime.vaulted_capability_registry where capability_id='ct.cap.vault.cie.advisory'
order by source;

-- MANUAL ROLLBACK (execute only against the exact post-change snapshot):
-- begin;
-- update chlom_runtime.capability_contracts
-- set allowed_agent_ids = array(select x from unnest(allowed_agent_ids) x
--   where x not in ('ct.framework-agent.cie','ct.subagent.cie-interoperability') order by x),
--   metadata = metadata - array['cie_interoperability_binding','binding_state','child_candidate_head',
--     'public_contract_bundle_digest','live_dispatch_enabled','transport_identities_non_voting',
--     'parent_certification_state','oidc_current_head_state']::text[]
-- where capability_id='ct.cap.vault.cie.advisory';
-- update chlom_runtime.vaulted_capability_registry
-- set allowed_agent_ids = array(select x from unnest(allowed_agent_ids) x
--   where x not in ('ct.framework-agent.cie','ct.subagent.cie-interoperability') order by x),
--   metadata = metadata - array['cie_interoperability_binding','binding_state','child_candidate_head',
--     'public_contract_bundle_digest','live_dispatch_enabled','transport_identities_non_voting',
--     'parent_certification_state','oidc_current_head_state']::text[]
-- where capability_id='ct.cap.vault.cie.advisory';
-- update institutional_federation.framework_package_registry
-- set metadata = metadata - array['cie_interoperability_packet','interoperability_packet_state',
--   'parent_main_reconciled_sha','child_repository','child_candidate_pr','child_candidate_head',
--   'child_base_sha','child_public_contract_bundle_digest','chlom_capability_id',
--   'chlom_capability_digest','oidc_current_head_state','agent_d_parent_certification_state',
--   'live_private_dispatch_enabled','repository_federation_state']::text[]
-- where package_id='ct.framework-package.cie';
-- update institutional_federation.framework_package_registry
-- set metadata = metadata - array['cie_handoff_state','cie_source_child_head','implementation_allowed',
--   'operational_activation_allowed','registry_growth_is_certification']::text[]
-- where package_id='ct.framework-package.convergent-ecosystem';
-- commit;
