#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'data' / 'penta' / 'outreach-control-plane.v1.json'


def main() -> None:
    c = json.loads(CONTRACT.read_text())
    assert c['schema'] == 'ct.crm.outreach-control-plane.v1'
    assert c['environment'] == 'production'
    assert c['scheduler_topology'] == 'ct.scheduler-topology.production.v1'
    assert c['binding'] == 'ct.ops.agent.email-attention'
    cold = c['cold_outreach']
    assert cold['enabled'] is True
    assert cold['monthly_cap'] == 20
    assert cold['research_required'] is True
    assert cold['minimum_legitimacy_score'] >= 70
    assert cold['minimum_fit_score'] >= 60
    assert cold['claimable_profile_required'] is True
    assert cold['physical_postal_address_required'] is True
    assert cold['single_cold_attempt_per_contact'] is True
    assert cold['offer_ref'] == 'locticians.claimmonth50.v1'
    assert cold['safe_offer_copy'] == [
        '50% off Community+ Member or Basic for claimable listings only',
        'use code CLAIMMONTH50 and verify exact eligibility and terms at checkout',
    ]
    prohibited = set(cold['prohibited_unverified_claims'])
    assert {'all plans', 'higher-tier plans', 'lifetime discount'}.issubset(prohibited)
    assert all('recurring membership payments' not in line.lower() for line in cold['safe_offer_copy'])
    nurture = c['nurture']
    assert nurture['unlimited'] is True
    assert nurture['global_monthly_cap'] is None
    assert nurture['relationship_gated'] is True
    assert nurture['minimum_interval_hours'] >= 72
    required_stops = {'opt_out','wrong_person','hard_bounce','complaint','risk_hold','conversion'}
    assert required_stops.issubset(set(c['automatic_stop_conditions']))
    assert c['maintenance_policy'] == 'read_only_no_commercial_send'
    assert c['external_clock_created'] is False
    assert c['d3_human_reserved'] is True
    assert c['no_self_approval'] is True
    assert c['no_authority_from_clock'] is True
    print('OUTREACH_CONTROL_PLANE_CONTRACT_PASS')


if __name__ == '__main__':
    main()
