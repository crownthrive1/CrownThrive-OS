# CrownThrive Autonomous Software Factory v3

Status: **production runtime active in ThriveBase.**

Factory v3 upgrades the Generate lane from manifest-only generation into a deterministic source compiler and upgrades Deploy into provider-specific adapters with read-after-write evidence and rollback references.

## Production pipeline

`discover -> architect -> generate/compiler -> security -> test -> package -> deploy -> assurance`

## Generate/compiler

`ct-factory-compiler` accepts a bounded machine-readable `compiler_spec` and emits actual source artifacts into `ct_factory_artifacts`. Supported component classes currently include:

- TypeScript modules
- Supabase/Deno Edge API source
- static HTML site source
- bounded SQL table migrations
- Deno test source

The compiler rejects arbitrary shell execution, unrestricted SQL, unsafe paths, and unsupported component types. Each emitted file receives SHA-256 evidence and is included in the production package.

`ct-factory-generator` invokes the compiler and seals the compiler report into the `ct.factory.v3` generated manifest.

## Provider deployment fabric

Provider adapters are registered in `ct_factory_provider_adapters`; provider work is recorded in `ct_factory_provider_jobs`.

Active paths:

- **ThriveBase** — provider-native service-registry write with database readback and rollback reference.
- **cPanel** — UAPI `Fileman::save_file_content` write into the bounded `public_html/.well-known` factory path followed by `get_file_content` readback.
- **CrownThrive Sites** — governed dynamic-feed publication through `governed_releases` and `site_catalog_projection`; this intentionally does not manufacture native Sites provider-write authority.
- **GitHub** — GitHub Actions OIDC worker claims queued provider jobs, writes compiler output into `generated/factory/<build-run>/`, commits to `main`, and reports provider readback to ThriveBase.
- **Vercel** — adapter is deployed and fail-closed. It remains disabled until a real Vercel project and runtime credentials are bound. The connected Vercel account currently exposes no projects, so the factory does not falsely claim Vercel deployment.

## Proof run

Factory v3 certification run: `0a93cdd4-d02a-49c1-8ad9-b9f4452f7ad0`.

The compiler emitted four real source files: a TypeScript module, Edge API source, static site source, and SQL migration. ThriveBase, cPanel, and Sites completed provider writes/readback. GitHub is handled asynchronously by the OIDC provider workflow; Assurance remains fail-closed until that provider job is implemented.

CrownThrive OS v2 continues to own scheduling and factory dispatch through ThriveBase. No ChatGPT conversation is required for the runtime loop.
