<?php

declare(strict_types=1);

namespace App\CrownThriveCos;

use InvalidArgumentException;
use LogicException;

final readonly class CapabilityAdapter
{
    /** @param array<string, mixed> $spec */
    public function __construct(private array $spec)
    {
        if (($spec['provider_write'] ?? true) !== false) {
            throw new LogicException('Phase 02 adapters may not perform provider writes.');
        }
    }

    public function key(): string
    {
        return (string) $this->spec['key'];
    }

    public function kind(): string
    {
        return (string) $this->spec['kind'];
    }

    /** @return list<string> */
    public function capabilities(): array
    {
        return array_keys((array) $this->spec['capabilities']);
    }

    public function resolve(string $capability): CapabilityResolution
    {
        $definition = $this->spec['capabilities'][$capability] ?? null;
        if (! is_array($definition)) {
            throw new InvalidArgumentException(sprintf('Capability %s is not declared by adapter %s.', $capability, $this->key()));
        }

        return new CapabilityResolution(
            adapter: $this->key(),
            serviceId: (string) $this->spec['service_id'],
            capability: $capability,
            state: (string) $definition['state'],
            authorityCeiling: (string) $this->spec['authority_ceiling'],
            providerWrite: false,
            reason: (string) $definition['reason'],
            evidenceSha256: (string) $this->spec['evidence_sha256'],
        );
    }

    public function assertProviderMutationAllowed(): never
    {
        throw new LogicException('Provider mutation is outside Crown Affiliates Phase 02 authority.');
    }
}
