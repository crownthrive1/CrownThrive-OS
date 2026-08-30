@php
    $ctInstrumentation = [
        'contract' => 'ct.crown-affiliates.client-instrumentation.v1',
        'application_uuid' => 'dd92c4db-22f8-4494-bda1-fab320645cf0',
        'host' => request()->getHost(),
        'thrivepush' => [
            'service_id' => 'thrivepush',
            'state' => 'gated_exact_property_required',
            'script_url' => null,
            'script_hosts' => [],
            'integrity' => null,
            'provider_writes' => false,
            'money_movement' => false,
        ],
        'crownlytics' => [
            'service_id' => 'crownlytics',
            'state' => 'gated_exact_property_required',
            'script_url' => null,
            'script_hosts' => [],
            'integrity' => null,
            'provider_writes' => false,
            'money_movement' => false,
        ],
        'crownpulse' => [
            'service_id' => 'crownpulse_admin',
            'state' => 'gated_compatibility_preflight_required',
            'script_url' => null,
            'script_hosts' => [],
            'integrity' => null,
            'provider_writes' => false,
            'money_movement' => false,
            'synthetic_social_proof' => false,
        ],
    ];
@endphp

<div
    data-ct-instrumentation='@json($ctInstrumentation, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT)'
    hidden
    aria-hidden="true"
></div>
