<?php

declare(strict_types=1);

namespace App\CrownThriveCos;

use InvalidArgumentException;

final class CapabilityState
{
    public const ACTIVE = 'active';
    public const GATED = 'gated';
    public const UNAVAILABLE = 'unavailable';

    public static function assert(string $state): void
    {
        if (! in_array($state, [self::ACTIVE, self::GATED, self::UNAVAILABLE], true)) {
            throw new InvalidArgumentException('Unsupported COS capability state.');
        }
    }
}
