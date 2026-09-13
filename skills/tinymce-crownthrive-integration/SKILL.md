# CrownThrive TinyMCE Integration Skill

## Purpose

Use TinyMCE 8 and TinyMCE AI inside CrownThrive applications without exposing signing keys, trusting browser-supplied identities, or confusing documentation MCP access with production provider authority.

## Upstream skill source

CrownThrive maintains `crownthrive1/tinymce-ai-skills` as the GitHub source for TinyMCE setup guidance. Treat it as an upstream implementation/reference skill, not as CrownThrive institutional truth. Reconcile its guidance with current Tiny documentation and CrownThrive OS controls before consequential changes.

## Required sequence

1. Detect the application/framework and existing editor surface before changing code.
2. Use TinyMCE major channel `8` unless the application has a separately governed version pin.
3. Confirm the Tiny plan/plugin entitlement before enabling premium plugins.
4. Use the official Tiny documentation MCP (`https://tinymcedocs.mcp.kapa.ai`) or current Tiny docs for API details.
5. For TinyMCE AI, obtain the authenticated CrownThrive user from the application's existing identity/session provider.
6. Request the Tiny AI JWT from the CrownThrive server route `/api/tinymce-ai-token`; never use Tiny's demo identity service in production.
7. Keep the RSA private key server-only. The browser may receive only the short-lived signed JWT.
8. Require `aud` to match the Tiny API key, `sub` to come from verified identity, short `iat`/`exp`, and only the required AI permissions.
9. Fail closed when identity, key binding, provider entitlement, origin policy, or signing configuration is missing.
10. Verify provider behavior after deployment and preserve public-safe evidence without raw secrets.

## CrownThrive implementation

- MCP configuration: `.mcp.json` → `tinymce-docs`.
- Token service: `api/tinymce-ai-token.js`.
- Integration contract/runbook: `integrations/tinymce/README.md`.
- Identity provider: CrownThrive Supabase Auth unless the consuming application has a separately governed identity binding.

## Security boundary

Any private key copied into chat, tickets, public Git, documentation, browser code, logs, or screenshots is treated as exposed and must be rotated before production use. Do not reuse disclosed key material merely because the corresponding public key still exists in the Tiny account.

## Publication boundary

TinyMCE and TinyMCE AI assist authoring. They do not create CIE approval, CHLOM rights, economic authority, editorial approval, or permission to publish. Preserve each consuming application's existing review and release gates.
