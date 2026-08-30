<?php

declare(strict_types=1);

namespace App\CrownThriveCos;

use InvalidArgumentException;

final class CapabilityFabric
{
    /** @return array<string, array<string, mixed>> */
    public static function manifest(): array
    {
        return InternalAdapterManifest::all() + ProviderAdapterManifest::all();
    }

    public static function adapter(string $key): CapabilityAdapter
    {
        $spec = self::manifest()[$key] ?? null;
        if (! is_array($spec)) {
            throw new InvalidArgumentException(sprintf('Unknown Crown Affiliates COS adapter: %s', $key));
        }

        return new CapabilityAdapter($spec);
    }

    public static function resolve(string $adapter, string $capability): CapabilityResolution
    {
        return self::adapter($adapter)->resolve($capability);
    }

    /** @return list<string> */
    public static function keys(): array
    {
        return array_keys(self::manifest());
    }
}
