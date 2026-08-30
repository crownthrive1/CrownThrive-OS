<?php

declare(strict_types=1);

namespace App\CrownThriveCos;

final class Phase02Certification
{
    /** @return array<string, int|bool> */
    public static function run(): array
    {
        $manifest = CapabilityFabric::manifest();
        $expected = [
            'penta-wire', 'penta-context', 'penta-health', 'penta-events', 'penta-pay', 'penta-costs', 'penta-media', 'penta-flow',
            'thrivepush', 'crownpulse', 'crownlytics', 'crownthrive-io', 'stripe-connect', 'partnero-fallback', 'adluxe', 'crownrewards',
        ];
        $classes = [
            CapabilityState::class, CapabilityResolution::class, CapabilityAdapter::class, InternalAdapterManifest::class,
            ProviderAdapterManifest::class, CapabilityFabric::class, Phase02Sbom::class, self::class,
        ];

        $classCount = count(array_filter($classes, static fn (string $class): bool => class_exists($class)));
        $duplicateKeys = count(array_keys($manifest)) - count(array_unique(array_keys($manifest)));
        $missing = array_diff($expected, array_keys($manifest));
        $extra = array_diff(array_keys($manifest), $expected);
        $active = $gated = $unavailable = $providerWrite = $secretMaterial = $invalidCapabilities = 0;

        foreach ($manifest as $key => $spec) {
            $providerWrite += (($spec['provider_write'] ?? true) === true) ? 1 : 0;
            foreach ((array) ($spec['capabilities'] ?? []) as $capability => $definition) {
                if (! str_starts_with((string) $capability, 'capability://crown-affiliates/')) {
                    $invalidCapabilities++;
                }
                $state = (string) ($definition['state'] ?? '');
                if ($state === CapabilityState::ACTIVE) { $active++; }
                elseif ($state === CapabilityState::GATED) { $gated++; }
                elseif ($state === CapabilityState::UNAVAILABLE) { $unavailable++; }
                else { $invalidCapabilities++; }
                CapabilityFabric::adapter((string) $key)->resolve((string) $capability);
            }
        }

        $encoded = json_encode([$manifest, Phase02Sbom::evidence()], JSON_UNESCAPED_SLASHES) ?: '';
        foreach (['sk_' . 'live_', 'rk_' . 'live_', 'BEGIN ' . 'PRIVATE KEY', 'client_' . 'secret=', 'api_' . 'key='] as $needle) {
            if (stripos($encoded, $needle) !== false) { $secretMaterial++; }
        }

        return [
            'ok' => count($missing) === 0 && count($extra) === 0 && $duplicateKeys === 0 && $providerWrite === 0 && $secretMaterial === 0 && $invalidCapabilities === 0 && $classCount === count($classes),
            'class_count' => $classCount,
            'adapter_count' => count($manifest),
            'active_count' => $active,
            'gated_count' => $gated,
            'unavailable_count' => $unavailable,
            'provider_write_count' => $providerWrite,
            'secret_material_count' => $secretMaterial,
            'invalid_capability_count' => $invalidCapabilities,
        ];
    }
}
