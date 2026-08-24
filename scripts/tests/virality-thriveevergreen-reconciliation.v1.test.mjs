import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const read = (path) => readFileSync(new URL(path, `file://${root}`), "utf8");
const parse = (path) => JSON.parse(read(path));
const countBy = (rows, field) =>
  rows.reduce((counts, row) => {
    counts[row[field]] = (counts[row[field]] ?? 0) + 1;
    return counts;
  }, {});

const products = parse(
  "developers/manifests/virality-thriveevergreen-product-reconciliation.2026-08-24.v1.json",
);
assert.equal(products.products.length, 389);
assert.equal(
  products.validation_contract.id,
  "ct.contract.virality-thriveevergreen-product-reconciliation.v1",
);
assert.equal(products.currency_semantics.canonical_observed_currency, "USD");
assert.deepEqual(countBy(products.products, "decision"), {
  AVAILABLE: 2,
  HOLD: 385,
  DENY: 2,
});
assert.deepEqual(products.summary.decisions, {
  AVAILABLE: 2,
  HOLD: 385,
  DENY: 2,
});
assert.equal(products.summary.paid_products_economically_available, 0);
assert.equal(new Set(products.products.map((row) => row.product_id)).size, 389);
assert.equal(new Set(products.products.map((row) => row.sku)).size, 389);

for (const row of products.products) {
  assert.ok(["AVAILABLE", "HOLD", "DENY"].includes(row.decision));
  assert.ok(row.decision_reasons.length > 0);
  assert.equal(row.provider_aliases.provider_success_is_authority, false);
  assert.equal(row.settlement_revenue.provider_receipt_is_evidence_only, true);
  assert.equal(row.offer_price.historical_balance_rewrite, false);
  if (row.offer_price.virality_credits_presentation !== null) {
    assert.equal(
      row.offer_price.crown_credits,
      row.offer_price.virality_credits_presentation * 25,
    );
  }
  const activeContent = row.canonical_candidate.exact_active_version?.content_sha256;
  if (activeContent !== undefined && activeContent !== null) {
    const digests = activeContent.split(":");
    assert.ok(digests.length > 0);
    assert.ok(
      digests.every((value) => /^[0-9a-f]{64}$/.test(value)),
      `invalid exact content digest for ${row.product_id}`,
    );
  }
  if (row.decision === "AVAILABLE") {
    assert.equal(row.offer_price.cash_amount_minor, 0);
    assert.equal(row.canonical_candidate.exact_public_assets.length, 2);
    for (const asset of row.canonical_candidate.exact_public_assets) {
      assert.match(asset.sha256, /^[0-9a-f]{64}$/);
      assert.ok(asset.bytes > 0);
    }
    assert.equal(row.entitlement.issuance_state, "NOT_REQUIRED_PUBLIC_STATIC_DOWNLOAD");
  } else {
    assert.notEqual(row.offer_price.effective_offer_state, "AVAILABLE_ZERO_PRICE");
  }
}

const attachments = parse(
  "developers/manifests/virality-attached-masters-reconciliation.2026-08-24.v1.json",
);
assert.equal(attachments.assets.length, 16);
assert.deepEqual(attachments.decision_summary, {
  AVAILABLE: 0,
  HOLD: 16,
  DENY: 0,
});
assert.equal(
  attachments.assets.reduce((total, asset) => total + asset.bytes, 0),
  294_208_601,
);
assert.equal(new Set(attachments.assets.map((asset) => asset.sha256)).size, 16);
assert.ok(attachments.assets.every((asset) => asset.decision === "HOLD"));

const edgeSource = read(
  "developers/supabase/functions/virality-commerce-control/index.ts",
);
const candidateRoot =
  "developers/candidates/supabase/virality-commerce-control-v1.1.2";
const candidateEdgeSource = read(`${candidateRoot}/index.ts`);
const candidateControlSource = read(`${candidateRoot}/control.ts`);
const candidateState = parse(`${candidateRoot}/candidate-state.json`);
assert.match(edgeSource, /version: "1\.1\.1"/);
assert.match(edgeSource, /const ALLOWED_ORIGIN = "https:\/\/vm\.crownthrive\.com"/);
assert.match(edgeSource, /origin_not_allowed/);
assert.match(edgeSource, /const MAX_BODY_BYTES = 4_096/);
assert.match(edgeSource, /overall_state: "HOLD"/);
assert.match(
  edgeSource,
  /authority_rule: "Provider success is evidence, not economic truth\."/,
);
assert.match(edgeSource, /historical_balance_rewrite: false/);
assert.match(edgeSource, /checkout_authorized: false/);
assert.match(edgeSource, /crown_credit_topups_authorized: false/);
assert.match(edgeSource, /provider_execution_authorized: false/);
assert.match(edgeSource, /native_mutation_authorized: false/);
assert.match(edgeSource, /execution_authorized: false/);
assert.match(edgeSource, /EXACT_ECAC_PURCHASE_CHAIN_NOT_CERTIFIED/);
for (const service of ["chlom_wallet", "virality_music", "website_surface_control"]) {
  assert.match(edgeSource, new RegExp(`"${service}"|'${service}'`));
}
for (const gate of [
  "provider_writes",
  "credit_funding_policy_v2_alignment",
  "additional_enabled_webhook_surface_reconciliation",
]) {
  assert.match(edgeSource, new RegExp(`"${gate}"`));
}
assert.doesNotMatch(edgeSource, /public_catalog_count\s*:\s*316/);
assert.doesNotMatch(edgeSource, /checkout_authorized\s*:\s*true/);
assert.doesNotMatch(edgeSource, /checkout_authorized\s*:\s*!/);
assert.doesNotMatch(edgeSource, /crown_credit_topups_authorized\s*:\s*!/);

assert.match(candidateEdgeSource, /version: "1\.1\.2-staged-candidate"/);
assert.match(
  candidateEdgeSource,
  /deployment_state: "STAGED_REPOSITORY_ONLY_NOT_DEPLOYED"/,
);
assert.match(candidateEdgeSource, /createHandler,/);
assert.match(candidateEdgeSource, /from "\.\/control\.ts";/);
assert.match(candidateEdgeSource, /Deno\.serve\(createHandler\(manifest\)\);/);
assert.match(
  candidateControlSource,
  /ALLOWED_ORIGIN = "https:\/\/vm\.crownthrive\.com"/,
);
assert.match(candidateControlSource, /request\.body\.getReader\(\)/);
assert.doesNotMatch(candidateControlSource, /request\.text\(\)/);
assert.match(
  candidateControlSource,
  /HOLD_REGISTRY_FLAG_TRUE_UNAUTHORIZED/,
);
assert.match(
  candidateControlSource,
  /HOLD_REGISTRY_STATE_MISSING_OR_UNREADABLE/,
);
assert.match(candidateControlSource, /effective_enabled: false/);
assert.match(candidateControlSource, /execution_authorized: false/);
assert.doesNotMatch(candidateEdgeSource, /select project_key,/);
assert.match(
  candidateEdgeSource,
  /project_key is not null as project_key_configured/,
);
assert.equal(candidateState.state, "STAGED_REPOSITORY_ONLY_NOT_DEPLOYED");
assert.equal(candidateState.live_edge_function_version, 4);
assert.equal(candidateState.live_state, "HOLD_UNCHANGED");
assert.equal(candidateState.deployment_authorized, false);
assert.equal(candidateState.provider_mutation_authorized, false);

const digest = (path) =>
  createHash("sha256").update(read(path)).digest("hex");
const candidateBundleDigest = createHash("sha256")
  .update(candidateEdgeSource)
  .update("\0")
  .update(candidateControlSource)
  .digest("hex");
assert.equal(
  candidateState.artifact_sha256.index_ts,
  digest(`${candidateRoot}/index.ts`),
);
assert.equal(
  candidateState.artifact_sha256.control_ts,
  digest(`${candidateRoot}/control.ts`),
);
assert.equal(
  candidateState.artifact_sha256.deno_json,
  digest(`${candidateRoot}/deno.json`),
);
assert.equal(
  candidateState.artifact_sha256.control_test_ts,
  digest(`${candidateRoot}/control.test.ts`),
);
assert.equal(
  candidateState.artifact_sha256.source_contract_test_py,
  digest(`${candidateRoot}/source_contract_test.py`),
);
assert.equal(
  candidateState.artifact_sha256.index_control_bundle,
  candidateBundleDigest,
);

const acceptance = parse(
  "developers/certification/virality-thriveevergreen-production-integration-2026-08-24.v1.json",
);
assert.equal(acceptance.decision, "HOLD");
assert.deepEqual(acceptance.exact_decision_set, ["ECAC", "HOLD", "DENY"]);
assert.deepEqual(acceptance.product_reconciliation, {
  total: 389,
  AVAILABLE: 2,
  HOLD: 385,
  DENY: 2,
  deployed_source_registry_records: 355,
  source_registry_matches: 355,
  d1_only_records: 34,
  exact_active_d1_versions: 329,
  paid_products_economically_available: 0,
  free_public_resources_available: 2,
  attached_source_files: {
    total: 16,
    AVAILABLE: 0,
    HOLD: 16,
    DENY: 0,
    total_bytes: 294_208_601,
    pdf_pages: 2_908,
  },
});
assert.equal(
  acceptance.api_mcp.active.count +
    acceptance.api_mcp.staged.count +
    acceptance.api_mcp.disabled.count,
  58,
);
assert.equal(acceptance.generalized_dispatch.enabled, false);
assert.equal(acceptance.wallets.walletconnect.unattended_value_ceiling_minor, 0);
assert.equal(
  acceptance.wallets.dedicated_agent_wallet.unattended_value_ceiling_minor,
  0,
);
assert.equal(acceptance.credits.virality_credits.crown_credits_per_unit, 25);
assert.equal(
  acceptance.credits.virality_credits.automatic_historical_balance_rewrite,
  false,
);
assert.equal(
  acceptance.artifact_sha256.runtime_v1_1,
  digest("developers/scripts/thriveevergreen/production-fabric-runtime.v1.1.ts"),
);
assert.equal(
  acceptance.artifact_sha256.runtime_contract_v1_1,
  digest(
    "developers/contracts/thriveevergreen/production-fabric.contracts.v1.1.schema.json",
  ),
);
assert.equal(
  acceptance.artifact_sha256.virality_edge_source,
  digest("developers/supabase/functions/virality-commerce-control/index.ts"),
);
assert.equal(
  acceptance.artifact_sha256.product_reconciliation,
  digest(
    "developers/manifests/virality-thriveevergreen-product-reconciliation.2026-08-24.v1.json",
  ),
);
assert.equal(
  acceptance.artifact_sha256.attached_masters,
  digest(
    "developers/manifests/virality-attached-masters-reconciliation.2026-08-24.v1.json",
  ),
);

console.log(
  JSON.stringify(
    {
      status: "PASS",
      products: products.summary,
      attachments: attachments.decision_summary,
      edge_source_sha256: digest(
        "developers/supabase/functions/virality-commerce-control/index.ts",
      ),
      edge_candidate: {
        state: candidateState.state,
        deployed: false,
        index_sha256: digest(`${candidateRoot}/index.ts`),
        control_sha256: digest(`${candidateRoot}/control.ts`),
        source_bundle_sha256: candidateBundleDigest,
      },
    },
    null,
    2,
  ),
);
