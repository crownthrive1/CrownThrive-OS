# CrownThrive OS Command Center UX release

Production-shell remediation for 2026-09-02.

## Scope
- Replaces implementation-first navigation with an operator-first Command Center.
- Adds ecosystem and commerce portfolio corridors grounded in current CrownThrive public positioning.
- Preserves existing `/api/health`, `/api/fabric`, `/api/operations`, `/api/penta`, `/api/chlom`, `/api/mcp` contracts and the live `activity.js` runtime.
- Keeps provider and release truth fail-closed: portfolio placement is not presented as runtime status.
- Improves responsive layout, focus visibility, reduced-motion handling, content hierarchy, actionability, and mobile navigation.

## Production boundary
No provider credentials, money movement, rights grant, D3 action, database migration, or backend authority expansion is introduced by this UI release. Existing CSP/security headers and Vercel/provider readback remain unchanged.

## Validation
The changed `app.js` passes Node syntax validation and a DOM-selector contract check against the changed `index.html`. Full CI and Vercel preview/provider readback remain release gates.
