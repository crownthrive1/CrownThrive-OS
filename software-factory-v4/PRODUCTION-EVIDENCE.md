# Production Evidence — CrownThrive Autonomous Software Factory v4

Certification date: 2026-08-26 UTC

## Build

- Build request: `factory-v4-breadth-production-001`
- Build run: `42982e51-08cb-482e-a629-7e019e9845cb`
- Terminal state: `implemented`
- Started: `2026-08-26T02:46:39.788804Z`
- Completed: `2026-08-26T02:53:52.026252Z`
- Release: `2.1.1`
- Release state: `implemented`
- Package SHA-256: `897ae1fa9f66a6fa52b1001f973d643061302fad4a3c868829111b55ff750655`
- Generated-manifest SHA-256: `466537c421ffffbc8a345631a7d0ef1242c2518191f38abf9f95b7de01f0563c`
- Compiler report SHA-256: `a2e26bdec1762d6737c3594d02548cb1f3dced4f1db27dca5ba6d4fee2950bfc`
- Test report SHA-256: `7bc453a119c91decdba563cff4d7873a31adfbd110fa96aabcaf73a721ce5f75`

All required lanes passed: Discover, Architect, Generate, Security, Test, Package, Deploy, Assurance.

## Compiler breadth

Seventeen component families are registered. The certification blueprint emitted sixteen source artifacts across fourteen kinds:

- TypeScript module
- OpenAPI 3.1 contract
- Edge API
- bounded SQL table migration
- static sites
- MCP tool manifest
- MDX documentation
- allowlisted GitHub workflow
- event JSON Schema
- environment contract without secret values
- route manifest
- asset manifest
- policy manifest
- service worker

The production test gate passed source-family validation, artifact-size limits, SHA-256 coverage, embedded-secret-pattern checks, provider-adapter coverage, and surface-binding checks.

## Property/provider mesh

Twenty production website surfaces were bound from `integration_control.website_surfaces`:

- 5 `auto` / release-required
- 5 `manual`
- 5 `observe`
- 5 `hold_unbound`

The five release-required Sites surfaces completed governed write plus read-after-write evidence:

- CrownThrive Developer Marketplace
- CrownThrive Launch
- CrownThrive Procure
- CrownThrive Ready
- Virality Music

Infrastructure deployment evidence also passed for:

- ThriveBase native service registry
- cPanel UAPI write/readback
- GitHub Actions/OIDC provider publisher

GitHub provider job: `a0803677-b333-4667-a162-a89da495d3a5`

GitHub workflow run: `32924377409`

Generated-source commit: `931d80ee13a445780e28889bc7f78c6d8eef0fe3`

Readback recorded sixteen generated files and rollback reference `git:931d80ee13a445780e28889bc7f78c6d8eef0fe3^1`.

## Fail-closed provider dispositions

Known production surfaces are not omitted merely because their writer is not certified. They remain bound with explicit non-mutating dispositions. Current unbound/held examples include Brilliant Directories, Squarespace, the unverified Store.Locticians provider, and ThriveTools module-family writers. Observe-only surfaces remain visible without being silently mutated.

Vercel remains disabled/fail-closed because the connected Vercel team exposes zero projects. This certification does not claim Vercel deployment.

CrownThrive Sites evidence in this run is governed publication into the per-surface Sites projection/feed with readback. It is not represented as a native ChatGPT Sites provider mutation.
