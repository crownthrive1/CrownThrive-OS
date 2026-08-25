# CHLOM Integration Mesh Federation Binding

Canonical source of truth: `crownthrive1/chlom-protocol` → `registry/integrations.json`.

This repository is a governed consumer of `ct.mesh.integrations.v1`; it does not fork or redefine the canonical integration registry.

Required assertions:
- registry id is `ct.mesh.integrations.v1`;
- CrownThrive IO / MCP remains registered with a founder-declared hardcoded `UNLIMITED` provider limit;
- AdLuxe Network / Adserve Online remains registered with a founder-declared hardcoded provider limit of `3000000`;
- credentials remain vault references only;
- provider controls are not bypassed;
- destructive permissions remain separately certified.

The scheduled federation verifier is `.github/workflows/chlom-integration-mesh-federation.yml`. A failed verifier means this repository must treat the mesh relationship as degraded until the canonical registry is reachable and passes contract assertions.
