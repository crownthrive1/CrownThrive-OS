<?php

declare(strict_types=1);

namespace App\CrownThriveCos;

final class Phase02Sbom
{
    /** @return array<string, mixed> */
    public static function evidence(): array
    {
        return [
            'phase' => '02',
            'program_id' => 'ct.crown-affiliates.native-commerce-growth.v1',
            'r1_job_id' => '7dc99de4-0566-417d-a265-e94df075c59a',
            'r1_evidence_sha256' => '360a50a9d84bfd742da07feec736babdfd6046c156aee5ec809fb47f357926d5',
            'dependency_manifests' => [
                'composer.json' => '894c7ee48b49613b56a37d4de53cbaa483c241f006bae656f6b874e88a28496f',
                'composer.lock' => 'b0b4bf6c2d27cc8b10449e55d02d986182a938ff12c0b4cca0e7a56cfe4cbd19',
                'package.json' => '1271e1eba1cbad25f6f5e5e9728d0f832ec1f90f17a0b89a25b26fe7e43622ec',
                'package-lock.json' => '928f9a0d9dc21f69c8031eb1018b53f6d4da5eb2c711a8521c01c61a25766e84',
            ],
            'composer_packages' => ['production' => 124, 'development' => 39],
            'npm_direct_dependencies' => ['production' => 17, 'development' => 6, 'lockfile_version' => 3],
            'new_composer_dependencies' => 0,
            'new_javascript_dependencies' => 0,
            'client_scripts_loaded_by_phase02' => 0,
        ];
    }
}
