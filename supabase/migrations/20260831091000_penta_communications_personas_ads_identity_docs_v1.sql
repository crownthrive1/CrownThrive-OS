-- ct.migration.penta-communications-personas-ads.identity-docs.v1
-- Additive identity/docs/alias convergence only. No provider write, money, rights, credentials, D3 or certification.
-- Source candidate: github:crownthrive1/CrownThrive-OS@sol/penta-communications-personas-ads-institutionalization-v1-20260831
-- Source parent: 89eb1e65131d6d5b3655c23da63646429451829d
-- Current PentaAds source pin after no-loss convergence: 47f31106c815ff303e02b28900ae4d7de4c59b84

begin;

update integration_control.penta_identity_registry_v1
set docs_path = '/pentas/canonical/penta-persona-execution',
    docs_namespace = 'canonical',
    source_refs = coalesce(source_refs, '{}'::jsonb) || jsonb_build_object(
      'institutionalization_source','github:crownthrive1/CrownThrive-OS@sol/penta-communications-personas-ads-institutionalization-v1-20260831',
      'contract','contracts/personas/penta-persona-execution.v1.json'
    ),
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'persona_contract_standard','ct.penta.persona.contract.standard.v1',
      'penta_mail_transport_only',true,
      'd3_human_reserved',true
    ),
    updated_at = now()
where identity_key='penta.persona-execution';

update integration_control.penta_identity_registry_v1
set docs_path = '/pentas/canonical/penta-persona-factory',
    docs_namespace = 'canonical',
    source_refs = coalesce(source_refs, '{}'::jsonb) || jsonb_build_object(
      'institutionalization_source','github:crownthrive1/CrownThrive-OS@sol/penta-communications-personas-ads-institutionalization-v1-20260831',
      'contract','contracts/personas/penta-persona-factory.v1.json'
    ),
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'reuse_existing_first',true,
      'new_persona_last_resort',true,
      'independent_certification_required',true,
      'd3_human_reserved',true
    ),
    updated_at = now()
where identity_key='penta.persona-factory';

update integration_control.penta_identity_registry_v1
set source_refs = coalesce(source_refs, '{}'::jsonb) || jsonb_build_object(
      'institutionalization_source','github:crownthrive1/CrownThrive-OS@sol/penta-communications-personas-ads-institutionalization-v1-20260831',
      'contract','contracts/communications/penta-mail.v2.json',
      'mailer_contract','contracts/communications/penta-mailer-transport.v1.json'
    ),
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'transport_subcomponent','penta.mailer',
      'direct_mailbox_send_fallback',false,
      'd3_human_reserved',true
    ),
    updated_at = now()
where identity_key='penta.mail';

insert into integration_control.penta_identity_registry_v1
(identity_key,canonical_name,identity_class,docs_path,docs_namespace,family_key,family_name,role,axis,kind,maturity,registration_state,activation_state,runtime_state,labels,source_refs,source_sha256,current,active,metadata)
values
('penta.ads','PentaAds','CANONICAL','/pentas/canonical/penta-ads','canonical',
 'COMMERCE_ECONOMY','Penta Commerce & Economy Family',
 'Governed advertising inventory, placement, delivery, evidence and recovery layer powered by AdLuxe Network / Adserver.Online.',
 'execution','system','production','registered','ACTIVE','RUNTIME_PRESENT',
 array['advertising','adluxe','placement','inventory','commerce','provider-bounded','d3-human-reserved'],
 jsonb_build_object(
   'source_authority','github:crownthrive1/PentaAds-Placement-OS',
   'source_sha','47f31106c815ff303e02b28900ae4d7de4c59b84',
   'institutionalization_source','github:crownthrive1/CrownThrive-OS@sol/penta-communications-personas-ads-institutionalization-v1-20260831',
   'contract','contracts/ads/penta-ads.v2.json'
 ),
 null,true,true,
 jsonb_build_object(
   'authority_ceiling','D2',
   'd3_autonomous',false,
   'state_authority','ThriveBase',
   'docs_authority','PentaDocs/Mintlify',
   'institutional_mirror','Google Drive/Sheets',
   'provider','AdLuxe Network / Adserver.Online',
   'release_state','SOURCE_CERTIFIED_LIVE_COMPATIBLE_INSTALLATION_HELD',
   'locticians_installation_hold','HOLD_BD_TEMPLATE_WRITE_AUTHORITY'
 ))
on conflict(identity_key) do update
set canonical_name=excluded.canonical_name,
    identity_class=excluded.identity_class,
    docs_path=excluded.docs_path,
    docs_namespace=excluded.docs_namespace,
    family_key=excluded.family_key,
    family_name=excluded.family_name,
    role=excluded.role,
    axis=excluded.axis,
    kind=excluded.kind,
    maturity=excluded.maturity,
    registration_state=excluded.registration_state,
    activation_state=excluded.activation_state,
    runtime_state=excluded.runtime_state,
    labels=excluded.labels,
    source_refs=coalesce(integration_control.penta_identity_registry_v1.source_refs,'{}'::jsonb)||excluded.source_refs,
    current=true,
    active=true,
    metadata=coalesce(integration_control.penta_identity_registry_v1.metadata,'{}'::jsonb)||excluded.metadata,
    updated_at=now();

insert into integration_control.penta_identity_aliases_v1(alias_key,identity_key,alias_type,source_ref,metadata)
values
('pentaads','penta.ads','compatibility_alias','github:crownthrive1/PentaAds-Placement-OS@47f31106c815ff303e02b28900ae4d7de4c59b84','{"non_competing_identity":true}'::jsonb),
('ct.penta.ads.v1','penta.ads','contract_alias','github:crownthrive1/CrownThrive-OS@sol/penta-communications-personas-ads-institutionalization-v1-20260831','{"non_competing_identity":true}'::jsonb),
('penta.mailer','penta.mail','subcomponent_alias','github:crownthrive1/CrownThrive-OS@sol/penta-communications-personas-ads-institutionalization-v1-20260831','{"independent_peer_identity":false}'::jsonb),
('pentamailer','penta.mail','compatibility_alias','github:crownthrive1/CrownThrive-OS@sol/penta-communications-personas-ads-institutionalization-v1-20260831','{"independent_peer_identity":false}'::jsonb),
('ct.penta.mailer.v1','penta.mail','contract_alias','github:crownthrive1/CrownThrive-OS@sol/penta-communications-personas-ads-institutionalization-v1-20260831','{"independent_peer_identity":false}'::jsonb)
on conflict(alias_key) do update
set identity_key=excluded.identity_key,
    alias_type=excluded.alias_type,
    source_ref=excluded.source_ref,
    metadata=coalesce(integration_control.penta_identity_aliases_v1.metadata,'{}'::jsonb)||excluded.metadata,
    last_seen_at=now();

commit;
