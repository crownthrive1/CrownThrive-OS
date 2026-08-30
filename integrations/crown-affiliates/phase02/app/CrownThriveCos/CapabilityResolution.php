<?php

declare(strict_types=1);

namespace App\CrownThriveCos;

use LogicException;

final readonly class CapabilityResolution
{
    public function __construct(
        public string $adapter,
        public string $serviceId,
        public string $capability,
        public string $state,
        public string $authorityCeiling,
        public bool $providerWrite,
        public string $reason,
        public string $evidenceSha256,
    ) {
        CapabilityState::assert($state);
    }

    public function available(): bool
    {
        return $this->state === CapabilityState::ACTIVE;
    }

    public function assertAvailable(): self
    {
        if (! $this->available()) {
            throw new LogicException(sprintf('Capability %s is %s: %s', $this->capability, $this->state, $this->reason));
        }

        return $this;
    }

    /** @return array<string, bool|string> */
    public function toArray(): array
    {
        return [
            'adapter' => $this->adapter,
            'service_id' => $this->serviceId,
            'capability' => $this->capability,
            'state' => $this->state,
            'authority_ceiling' => $this->authorityCeiling,
            'provider_write' => $this->providerWrite,
            'reason' => $this->reason,
            'evidence_sha256' => $this->evidenceSha256,
        ];
    }
}
