<?php

declare(strict_types=1);

namespace App\CrownThriveCos;

final class ClientInstrumentationManifest
{
    public const CONTRACT = 'ct.crown-affiliates.client-instrumentation.v1';
    public const APPLICATION_UUID = 'dd92c4db-22f8-4494-bda1-fab320645cf0';
    public const PRODUCTION_HOST = 'crownaffiliates.com';
    public const THRIVEPUSH_EXPECTED_SHA256 = '19970f0e27cb3eb4d17fb093a25fb0efd7208b36e1336578616d96d8d6ef4788';

    public static function providers(): array
    {
        return [
            'thrivepush' => [
                'service_id' => 'thrivepush',
                'state' => 'gated_exact_property_required',
                'legacy_property' => [
                    'host' => 'affiliates.crownthrive.com',
                    'website_id' => 10,
                ],
                'production_property' => null,
                'provider_writes' => false,
                'money_movement' => false,
                'service_worker' => [
                    'target' => '/thrivepusher.js',
                    'expected_sha256' => self::THRIVEPUSH_EXPECTED_SHA256,
                    'deploy_only_on_exact_hash_match' => true,
                ],
                'consent' => [
                    'browser_permission' => 'explicit_user_action_only',
                    'operational' => 'separate_preference',
                    'promotional' => 'separate_preference',
                ],
            ],
            'crownlytics' => [
                'service_id' => 'crownlytics',
                'state' => 'gated_exact_property_required',
                'legacy_property' => [
                    'host' => 'affiliates.crownthrive.com',
                    'website_id' => 14,
                ],
                'production_property' => null,
                'provider_writes' => false,
                'money_movement' => false,
                'client_events' => [
                    'program.view',
                    'program.search',
                    'program.filter',
                    'program.apply.click',
                    'affiliate.profile.view',
                    'guide.view',
                    'guide.cta.click',
                    'biolink.click',
                    'qr.visit',
                    'push.opt_in',
                ],
                'economic_truth_from_browser' => false,
            ],
            'crownpulse' => [
                'service_id' => 'crownpulse_admin',
                'state' => 'gated_compatibility_preflight_required',
                'installed_version' => 'v57.0.0',
                'highest_known_version' => 'v61.0.0',
                'provider_writes' => false,
                'money_movement' => false,
                'synthetic_social_proof' => false,
                'evidence_reference_required' => true,
                'identifying_financial_claims_default' => 'deny',
            ],
        ];
    }

    public static function security(): array
    {
        return [
            'production_grade_only' => true,
            'secure_by_default' => true,
            'duplicate_load_prevention' => true,
            'csp_preservation_required' => true,
            'secret_material_client_side' => false,
            'provider_writes' => false,
            'money_movement' => false,
            'd3_effect' => false,
            'fail_closed_on_missing_binding' => true,
        ];
    }
}
