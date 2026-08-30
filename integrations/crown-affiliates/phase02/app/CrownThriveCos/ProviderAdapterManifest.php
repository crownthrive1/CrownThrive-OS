<?php

declare(strict_types=1);

namespace App\CrownThriveCos;

final class ProviderAdapterManifest
{
    /** @return array<string, array<string, mixed>> */
    public static function all(): array
    {
        return [
            'thrivepush' => self::entry('thrivepush', 'thrivepush', 'D2', 'e221c5b98c54cd936520211c85ed024b18d02c171b521b67caa6e72be555e0b6', [
                'capability://crown-affiliates/thrivepush.status.read' => self::active('Credential and read path are verified.'),
                'capability://crown-affiliates/thrivepush.subscriber.write' => self::unavailable('Provider writes are closed in current PentaWire evidence.'),
            ]),
            'crownpulse' => self::entry('crownpulse', 'crownpulse_admin', 'D2', '643648c6efdf2bb89e611bde1bfb64cdf40c5b6960ddcb68dfe4eaffd7df9db9', [
                'capability://crown-affiliates/crownpulse.status.read' => self::unavailable('Service is configured but has zero enabled direct tools.'),
                'capability://crown-affiliates/crownpulse.event.write' => self::unavailable('No certified provider-write route exists.'),
            ]),
            'crownlytics' => self::entry('crownlytics', 'crownlytics', 'D2', 'dbf9c6a69c5614514476d7f6cafcf80cb1f19d5dd92957e30a4d4dac10e61623', [
                'capability://crown-affiliates/crownlytics.analytics.read' => self::active('Credential and read path are verified.'),
                'capability://crown-affiliates/crownlytics.event.write' => self::unavailable('Phase 02 does not authorize analytics provider writes.'),
            ]),
            'crownthrive-io' => self::entry('crownthrive-io', 'crownthrive_io', 'D2', 'f035d9637733aca2efbbbda21fb4a01ef5fe90e024eb5627857c6b541a39c5d6', [
                'capability://crown-affiliates/crownthrive-io.asset.read' => self::unavailable('Current service integration state is blocked.'),
                'capability://crown-affiliates/crownthrive-io.asset.write' => self::unavailable('Broad/non-project mutations remain contained.'),
            ]),
            'stripe-connect' => self::entry('stripe-connect', 'stripe', 'D2', '03990b373b4ea375f271974b3ef27b698fe1783db566612737f0a698206ecf95', [
                'capability://crown-affiliates/stripe-connect.status.read' => self::active('Stripe service is read-verified and connected-account readback is established.'),
                'capability://crown-affiliates/stripe-connect.oauth.write' => self::gated('Connect OAuth registry/runtime state is held for security review.'),
                'capability://crown-affiliates/stripe-connect.transfer.write' => self::unavailable('Money movement is outside Phase 02 authority.'),
            ]),
            'partnero-fallback' => self::entry('partnero-fallback', 'partnero', 'D2', 'b08b7e36e2143cb902e66c189a1414960920a55ba6d5e990d6e607a347b7699d', [
                'capability://crown-affiliates/partnero.status.read' => self::active('Authenticated provider readback is verified.'),
                'capability://crown-affiliates/partnero.fallback.write' => self::gated('Fallback writes require point-of-use reopening; Phase 02 does not dispatch them.'),
            ]),
            'adluxe' => self::entry('adluxe', 'adluxe_network', 'D2', '862226757a1f167e66f54134b6026e04261f649d4ed4c88a94f246f543506b5a', [
                'capability://crown-affiliates/adluxe.distribution' => self::gated('Frozen checklist requires AdLuxe to remain staged/gated in Phase 02.'),
            ]),
            'crownrewards' => self::entry('crownrewards', 'crownrewards', 'D2', '14c24d890d87fcb5c3700de10d6860754cde43103033bfb4659a8a329680b068', [
                'capability://crown-affiliates/crownrewards.retention' => self::gated('Frozen checklist requires CrownRewards to remain staged/gated in Phase 02.'),
            ]),
        ];
    }

    /** @param array<string, array{state:string,reason:string}> $capabilities */
    private static function entry(string $key, string $serviceId, string $ceiling, string $evidence, array $capabilities): array
    {
        return ['key' => $key, 'kind' => 'provider', 'service_id' => $serviceId, 'authority_ceiling' => $ceiling, 'provider_write' => false, 'evidence_sha256' => $evidence, 'capabilities' => $capabilities];
    }

    private static function active(string $reason): array { return ['state' => CapabilityState::ACTIVE, 'reason' => $reason]; }
    private static function gated(string $reason): array { return ['state' => CapabilityState::GATED, 'reason' => $reason]; }
    private static function unavailable(string $reason): array { return ['state' => CapabilityState::UNAVAILABLE, 'reason' => $reason]; }
}
