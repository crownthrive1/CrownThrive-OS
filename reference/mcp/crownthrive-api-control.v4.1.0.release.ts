/**
 * Public-safe fail-closed projection for CT-MCP-EXTCERT-001.
 *
 * The deployable runtime, identity bindings, provider topology, operation catalog,
 * derived schemas and private evidence belong in governed private custody. This
 * file is intentionally non-deployable as a certification runtime.
 */
export const publicCertificationContract = Object.freeze({
  certificationId: "CT-MCP-EXTCERT-001",
  candidateVersion: "4.1.0",
  state: "SECURITY_HOLD",
  executionEnabled: false,
  providerReadsEnabled: false,
  providerWritesEnabled: false,
  sovereignVoteAuthority: false,
  phase3Advancement: false
});

export default function securityHoldResponse(): Response {
  return new Response(JSON.stringify({
    error: "certification_security_hold",
    certification_id: publicCertificationContract.certificationId
  }), {
    status: 503,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff"
    }
  });
}

