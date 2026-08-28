#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'data' / 'penta' / 'locticians-publishing-control.v1.json'


def main() -> None:
    c = json.loads(CONTRACT.read_text())
    assert c['schema'] == 'ct.integration.locticians-publishing-control.v1'
    assert c['environment'] == 'production'
    assert c['expected_persona_count'] == 39
    assert c['surface_id'] == 'ct.surface.locticians.production'
    assert c['adapter_id'] == 'ct.adapter.brilliant-directories.locticians.v1'
    assert c['publisher_agent_id'] == 'ct.pentamarketer.agent.publisher'
    assert c['publisher_persona_id'] == 'ct.persona.locticians.publisher.kiara.v1'

    provider = c['provider_contract']
    assert provider['create_path'] == '/api/v2/data_posts/create'
    assert provider['read_path_template'] == '/api/v2/data_posts/get/{post_id}'
    assert provider['required_identifiers'] == ['user_id', 'data_id', 'data_type']
    assert provider['identifiers']['data_type'] == 20
    assert provider['identifiers']['data_id'] is None
    assert provider['open_state'] is False
    assert provider['write_canary_required'] is True
    assert provider['read_after_write_required'] is True
    assert provider['rollback_canary_required'] is True

    rights = c['image_rights_gate']
    assert rights['required_when_image_present'] is True
    assert rights['rights_state_required'] == 'verified'
    assert rights['provenance_ref_required'] is True
    assert rights['source_ref_required'] is True
    assert rights['alt_text_required'] is True
    assert rights['missing_or_unverified_action'] == 'quarantine'
    assert {'owned', 'licensed', 'public_domain', 'provider_permitted'}.issubset(set(rights['accepted_rights_bases']))

    authority = c['authority']
    assert authority['publisher_may_request_provider_publish'] is True
    assert authority['publisher_may_bypass_release_gate'] is False
    assert authority['non_publishers_direct_provider_write'] is False
    assert authority['all_other_personas_handoff_only'] is True
    assert authority['requires_chlom_invocation'] is True
    assert authority['requires_readback'] is True

    offer = c['offer_claim_gate']
    assert offer['verified_public_scope'] == ['Community+ Member', 'Basic']
    assert offer['claimable_listings_only'] is True
    assert 'all plans' in offer['prohibited_until_checkout_verified']
    print('LOCTICIANS_PUBLISHING_CONTROL_PASS')


if __name__ == '__main__':
    main()
