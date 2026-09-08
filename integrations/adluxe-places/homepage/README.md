# AdLuxe Places responsive homepage

Founder request, 2026-09-08: redo the AdLuxe Places homepage to make it responsive. Related OS intake: #4238 / #4239. This is a bounded additive frontend refinement, not an AdSpot upgrade or full source synchronization.

## Implemented

- Full-width stacked phone CTAs; wrap-safe labels and 48px targets.
- Desktop navigation starts at 1280px, with measured-content compact fallback for longer translations.
- Header-height-aware content offset and section anchors.
- Fluid typography, constrained grids, reflowing preview labels and visible sample-data disclaimer.
- Responsive footer, keyboard-operable preview tabs, Escape closes the mobile menu.
- Reduced-motion support, explicit pause control, offscreen video pausing.
- Existing branding, media, translated copy, role-aware links, account dashboards, billing and screen-management logic are preserved.

## Provider inspection

The cPanel document root is a Passenger wrapper, not the deployed frontend. Routing readback identified `/home/adluxeplaces/adspot` as the application root, `build/backend/server.js` as the Passenger entrypoint and `build/frontend` as the Vite build output. Package metadata reads version 2.3.0. This does not certify the entire vendor source tree.

The public frontend retained these original bundle references at inspection: `/assets/index-CGLrHdox.js` and `/assets/index-DSnp2kZG.css`.

## Validation boundary

Chromium local DOM-fixture regression checks passed at 320, 360, 375, 390, 640, 768, 1024, 1279, 1280, 1440 and 1920 CSS pixels. Checked horizontal overflow, CTA height, header overlap, menu/Escape and keyboard tabs. Additional RTL and reduced-motion checks passed. JavaScript syntax check passed. The fixture reproduces the inspected DOM contracts; it is NOT an end-to-end live-browser audit, authentication test, payment test or full accessibility certification. Live browser navigation is unavailable in this execution environment.

## Release requirements

Read original source and built index bytes without HTML-encoding mutation; preserve verified backups outside the served root. Add versioned assets in both `public` and `build/frontend`. Inject their links additively while preserving the original application bundles. Expected-state hashes, exact asset hashes, post-write file readback and public HTTP readback are required. Abort on concurrent-source conflict. Never write payment, backend, environment, credential or screen-player files for this change. Do not infer production publication or institutional completion from this commit alone.

The authenticated existing `pentaads-places-partner-mcp` was extended with a scoped frontend read operation to resolve provider truth; the seven prior operations remain intact. No new Supabase plan or function capacity was purchased. Provider read operations were sent through the OS audited HTTP route. CHLOM institutional completion is not asserted.
