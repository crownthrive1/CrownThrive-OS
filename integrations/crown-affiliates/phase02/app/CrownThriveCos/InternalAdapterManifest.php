<?php

declare(strict_types=1);

namespace App\CrownThriveCos;

final class InternalAdapterManifest
{
    /** @return array<string, array<string, mixed>> */
    public static function all(): array
    {
        $phaseOneEvidence = 'a5962e610419e1e92dac73e38e83da3f0d78230240984130cb78962cea0b96c1';
        $dailEvidence = 'ct.dail.live.20260829';
        $mediaEvidence = 'ct.pentamedia.asset-bindings.72.20260829';

        return [
            'penta-wire' => self::entry('penta-wire', 'crown_affiliates_cos_bridge', 'D2', $phaseOneEvidence, [
                'capability://crown-affiliates/penta-wire.capability.read' => self::active('Phase 01 bridge is read-verified and PentaWire-bound.'),
                'capability://crown-affiliates/penta-wire.health.read' => self::active('Phase 01 bridge exposes bounded health/capability references.'),
            ]),
            'penta-context' => self::entry('penta-context', 'penta.context', 'D2', $phaseOneEvidence, [
                'capability://crown-affiliates/penta-context.ref' => self::active('PentaContext is production-registered; Phase 02 exposes references only.'),
            ]),
            'penta-health' => self::entry('penta-health', 'penta.health', 'D1', $phaseOneEvidence, [
                'capability://crown-affiliates/penta-health.read' => self::active('PentaHealth is production-registered at D1.'),
            ]),
            'penta-events' => self::entry('penta-events', 'chlom_runtime.append_dail_event', 'D2', $dailEvidence, [
                'capability://crown-affiliates/penta-events.envelope.prepare' => self::active('DAIL event append contract is live; this adapter only prepares/refers to event envelopes.'),
            ]),
            'penta-pay' => self::entry('penta-pay', 'penta.pay', 'D2', $phaseOneEvidence, [
                'capability://crown-affiliates/penta-pay.ledger.read' => self::active('PentaPay is production-registered; direct money movement is forbidden.'),
                'capability://crown-affiliates/penta-pay.obligation.prepare' => self::active('Preparation is non-settlement and remains below D3.'),
            ]),
            'penta-costs' => self::entry('penta-costs', 'penta.cost', 'D2', $phaseOneEvidence, [
                'capability://crown-affiliates/penta-costs.read' => self::active('PentaCost is production-registered and read-bounded.'),
            ]),
            'penta-media' => self::entry('penta-media', 'integration_control.pentamedia_asset_bindings_v1', 'D2', $mediaEvidence, [
                'capability://crown-affiliates/penta-media.asset.ref' => self::active('PentaMedia asset bindings are live; Phase 02 exposes references only.'),
            ]),
            'penta-flow' => self::entry('penta-flow', 'penta.flow', 'D2', $phaseOneEvidence, [
                'capability://crown-affiliates/penta-flow.route.prepare' => self::active('PentaFlow is production-registered; provider dispatch remains external to this adapter.'),
            ]),
        ];
    }

    /** @param array<string, array{state:string,reason:string}> $capabilities */
    private static function entry(string $key, string $serviceId, string $ceiling, string $evidence, array $capabilities): array
    {
        return ['key' => $key, 'kind' => 'internal', 'service_id' => $serviceId, 'authority_ceiling' => $ceiling, 'provider_write' => false, 'evidence_sha256' => $evidence, 'capabilities' => $capabilities];
    }

    private static function active(string $reason): array
    {
        return ['state' => CapabilityState::ACTIVE, 'reason' => $reason];
    }
}
