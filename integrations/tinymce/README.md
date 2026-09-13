# TinyMCE 8 / TinyMCE AI integration

**Stable integration ID:** `ct.integration.tinymce.v1`  
**Provider:** Tiny Technologies, Inc. / TinyMCE Cloud  
**Editor line:** TinyMCE 8  
**Owner:** CrownThrive, LLC  
**Institutional state:** `BUILT_UNDEPLOYED` with production JWT issuance on `HOLD` until credential rotation and provider readback complete.

## Purpose

This integration gives CrownThrive applications a governed TinyMCE 8 rich-text editor path, TinyMCE AI capability, Tiny Cloud document conversion support, and direct access to Tiny's current documentation MCP without exposing server signing material to browsers or source control.

The CrownThrive-owned GitHub repository `crownthrive1/tinymce-ai-skills` is retained as an upstream agent-skill source for setup and troubleshooting. It is not the production editor runtime and it does not grant provider authority by itself.

## MCP binding

CrownThrive OS registers Tiny's official documentation MCP as:

```json
{
  "tinymce-docs": {
    "type": "http",
    "url": "https://tinymcedocs.mcp.kapa.ai"
  }
}
```

The MCP is a documentation/research surface. It is OAuth-protected by the provider and does not expose CrownThrive application data or create TinyMCE production authority.

## Production JWT flow

```text
authenticated CrownThrive user
        |
        | Supabase access token
        v
POST /api/tinymce-ai-token?service=<service>
        |
        | server verifies session with Supabase Auth
        | selects service-specific JWT claims
        | signs short-lived JWT with server-only RSA key
        v
Tiny Cloud service
```

Supported `service` values are `ai`, `importword`, `exportword`, and `exportpdf`. The default is `ai`.

- `ai` receives `aud`, `iat`, `exp`, verified-user `sub`, and bounded `auth.ai.permissions`.
- `importword`, `exportword`, and `exportpdf` receive the converter claim set `aud`, `iat`, and `exp` only.

The route intentionally does **not** use Tiny's demo identity endpoints and does **not** accept a caller-supplied user ID as identity proof.

### Required server environment bindings

- `TINYMCE_API_KEY` — Tiny Cloud API key; must match the JWT `aud` claim and the client CDN/API configuration.
- `TINYMCE_JWT_PRIVATE_KEY` — fresh PKCS#8 RSA private key corresponding to the public key registered in the Tiny account. Server secret only.
- `CROWNTHRIVE_SUPABASE_ANON_KEY` (or `SUPABASE_ANON_KEY`) — used server-side to validate the caller's Supabase access token through `/auth/v1/user`.
- `CROWNTHRIVE_SUPABASE_URL` — optional; defaults to the current CrownThrive Supabase Auth project.
- `TINYMCE_ALLOWED_ORIGINS` — optional comma-separated additions to the built-in CrownThrive origin allowlist.
- `TINYMCE_JWT_TTL_SECONDS` — optional; clamped to 300–900 seconds, default 600.

## Security incident / rotation requirement

A Tiny RSA private key was supplied through an interactive conversation during this integration request. Because that private key has crossed a disclosure boundary, it is **not accepted for production use** and must never be committed to Git, documentation, logs, tickets, screenshots, or client code.

Before production activation:

1. Revoke/delete the exposed Tiny key entry.
2. Generate a new RSA key pair in Tiny.
3. Register only the new public key with Tiny.
4. Store only the new PKCS#8 private key in the deployment secret store as `TINYMCE_JWT_PRIVATE_KEY`.
5. Add the exact production application domains to Tiny's Approved Domains configuration.
6. Bind the required server environment values and deploy the token endpoint.
7. Confirm authenticated token issuance and RS256 verification separately for AI, Import from Word, Export to Word, and Export to PDF features that are entitled on the active Tiny plan.
8. Confirm expiry behavior, origin enforcement, and fail-closed behavior.
9. Preserve provider/readback evidence without storing private key material.

Until those steps complete, the token route must fail closed with `TINYMCE_JWT_UNBOUND` or the applicable authentication/configuration error.

## Browser integration

Replace Tiny's demo token provider with the CrownThrive server route. The calling application should pass its existing authenticated Supabase access token:

```js
const tinyTokenProvider = (service) => async () => {
  const accessToken = await getCurrentSupabaseAccessToken();
  const response = await fetch(`/api/tinymce-ai-token?service=${encodeURIComponent(service)}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) throw new Error(`TinyMCE ${service} authentication failed`);
  const { token } = await response.json();
  return { token };
};

const tinyAuth = {
  tinymceai_token_provider: tinyTokenProvider('ai'),
  importword_token_provider: tinyTokenProvider('importword'),
  exportword_token_provider: tinyTokenProvider('exportword'),
  exportpdf_token_provider: tinyTokenProvider('exportpdf')
};
```

Spread `tinyAuth` into `tinymce.init(...)` only for the plugins actually enabled on that application surface.

`getCurrentSupabaseAccessToken()` is application-specific and must use the application's existing trusted auth/session client. Do not substitute a user ID, email address, or unsigned browser assertion.

## Network and plugin profile

The requested editor profile may use the TinyMCE 8 core and plan-entitled premium plugins, including `tinymceai`, comments, accessibility, PowerPaste, advanced table/code/template tooling, spellchecking, Uploadcare, Import from Word, Export to Word, Export to PDF, and related authoring tools. Individual CrownThrive applications should enable only the plugins required by that surface and confirmed available under the active Tiny plan.

If an application uses Tiny Cloud services behind a CSP, firewall, or forward proxy, allow the current Tiny Cloud service domains required by the enabled features and preserve Tiny's required API-key headers. Prefer the provider's current `*.tiny.cloud` guidance rather than maintaining a stale hard-coded list.

## Truth boundary

- A successful CDN load proves editor delivery, not JWT authority.
- A valid Tiny JWT proves bounded authentication for its claims and lifetime, not CrownThrive content/rights approval.
- TinyMCE AI output remains subject to CIE, CHLOM, application permissions, editorial review, and publication controls.
- MCP documentation access is research capability only.
- Provider success never authorizes private-key disclosure, rights changes, publishing, commerce, or D3 actions.
