import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonicalize, compilePolicyPackage, runScenarioMatrix, sha256Hex } from './policy-engine.mjs';
import { validateLicenseCandidate } from './metering-engine.mjs';
import { generatePolicyAdvisorProposal } from './policy-advisor.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const policy = JSON.parse(readFileSync(join(HERE, 'fixtures/walletkit-controlled-policy.v1.json'), 'utf8'));
const license = JSON.parse(readFileSync(join(HERE, 'fixtures/walletkit-synthetic-license.v1.json'), 'utf8'));
const artifact = compilePolicyPackage(policy);
const licenseCandidate = validateLicenseCandidate(license);

function baseAction(overrides = {}) {
  return {
    category: 'policy_simulation',
    provider_write: false,
    money_movement: false,
    production_rights_grant: false,
    chain_broadcast: false,
    effective_offer_change: false,
    ...overrides,
  };
}

function scenario(selector) {
  const context = {
    environment: 'CONTROLLED_TEST',
    action: baseAction(),
    evidence: {
      provider_signature_verified: false,
      independent_rights_active: false,
    },
  };
  if (selector === 0) {
    context.action.category = 'provider_translation';
    context.evidence.provider_signature_verified = true;
  } else if (selector === 1) {
    context.action.category = 'provider_translation';
  } else if (selector === 2) {
    context.action.category = 'rights_decision';
    context.evidence.independent_rights_active = true;
  } else if (selector === 3) {
    context.action.category = 'rights_decision';
  } else if (selector === 4) context.action.provider_write = true;
  else if (selector === 5) context.action.money_movement = true;
  else if (selector === 6) context.action.production_rights_grant = true;
  else if (selector === 7) context.action.chain_broadcast = true;
  else if (selector === 8) context.action.effective_offer_change = true;
  else context.action.category = 'usage_preview';
  return context;
}

const scenarios = Array.from({ length: 10_000 }, (_, index) => scenario(index % 10));
const simulation = runScenarioMatrix(artifact, scenarios);
const advisor = generatePolicyAdvisorProposal({
  policy_id: artifact.policy_id,
  compiled_digest_sha256: artifact.compiled_digest_sha256,
  simulation_summary: simulation,
  meter_snapshots: [
    { meter_id: 'ct.meter.wallet.api.requests.monthly', limit: 100, used: 85 },
    { meter_id: 'ct.meter.wallet.chain.broadcast.monthly', limit: 0, used: 0 },
    { meter_id: 'ct.meter.wallet.proof.anchor.monthly', limit: null, used: 0 },
    { meter_id: 'ct.meter.wallet.internal.simulation.monthly', limit: -1, used: 10_000 },
  ],
  risk_signals: [
    { signal_type: 'UNCOVERED_RULE_PATH', rule_id: 'ct.rule.wallet.future-account-deployment.v1' },
  ],
});

const algorithms = [
  ['CWPX', 'ct.algorithm.chlom-wallet.cwpx.v1', 'Policy Compiler & eXecutor'],
  ['MARC', 'ct.algorithm.chlom-wallet.marc.v1', 'Metered Activity Reconciliation Compiler'],
  ['QERA', 'ct.algorithm.chlom-wallet.qera.v1', 'Quota Enforcement & Reconciliation Algorithm'],
  ['SAGE', 'ct.algorithm.chlom-wallet.sage.v1', 'Scenario Assurance & Governance Evaluator'],
  ['AURA', 'ct.algorithm.chlom-wallet.aura.v1', 'Algorithmic Usage & Risk Advisor'],
].map(([short_name, algorithm_id, role]) => ({
  algorithm_id,
  short_name,
  role,
  deterministic: true,
  external_model_call: false,
  auto_apply: false,
  authority_effect: 'none',
}));

const manifestBody = {
  manifest_id: 'ct.manifest.chlom-wallet-policy-metering-engine.v1',
  semantic_version: '1.0.0',
  state: 'CONTROLLED_TEST',
  phase: '2.99',
  canonical_agent_id: 'ct.agent.chlom-wallet-settlement',
  subsystem_id: 'ct.subsystem.chlom-wallet.policy-metering-assurance.v1',
  algorithm_suite: {
    suite_id: 'ct.algorithm-suite.chlom-wallet-policy-metering.v1',
    semantic_version: '1.0.0',
    algorithms,
  },
  policy: {
    policy_id: artifact.policy_id,
    semantic_version: artifact.semantic_version,
    compiler_version: artifact.compiler_version,
    rule_count: artifact.rules.length,
    source_digest_sha256: artifact.source_digest_sha256,
    compiled_digest_sha256: artifact.compiled_digest_sha256,
    decision_precedence: artifact.decision_precedence,
    unknown_input_disposition: artifact.defaults.unknown,
    effective_policy: false,
  },
  simulation: {
    result: 'PASS_DETERMINISTIC_POLICY_SCENARIO_MATRIX',
    scenario_count: simulation.scenario_count,
    decisions: simulation.decisions,
    reason_counts: simulation.reason_counts,
    unreachable_rule_ids: simulation.unreachable_rule_ids,
    simulation_digest_sha256: simulation.simulation_digest_sha256,
    deterministic_replay_required: true,
  },
  exact_limit_semantics: {
    semantics_version: 'ct.limit-semantics.founder-override.v1',
    unlimited: -1,
    zero: 0,
    positive_integer: 'EXACT_LIMIT',
    unresolved: null,
    unresolved_disposition: 'HOLD_FAIL_CLOSED',
    invalid_below_negative_one: 'DENY',
    provider_limits_still_authoritative: true,
  },
  meters: [
    'ct.meter.wallet.api.requests.monthly',
    'ct.meter.wallet.chain.broadcast.monthly',
    'ct.meter.wallet.proof.anchor.monthly',
    'ct.meter.wallet.internal.simulation.monthly',
  ],
  license_candidate: {
    license_id: licenseCandidate.license_id,
    semantic_version: licenseCandidate.semantic_version,
    license_digest_sha256: licenseCandidate.license_digest_sha256,
    support_class: licenseCandidate.support_class,
    limits: licenseCandidate.limits,
    effective_offer: false,
    public_price_authorized: false,
    stripe_objects_created: false,
    checkout_enabled: false,
  },
  algorithmic_advisor: {
    algorithm_id: advisor.algorithm_id,
    proposal_state: advisor.proposal_state,
    proposal_count: advisor.proposals.length,
    proposal_digest_sha256: advisor.proposal_digest_sha256,
    external_model_call_performed: false,
    auto_apply: false,
    policy_activation: false,
    effective_offer_change: false,
  },
  private_runtime: {
    tables: [
      'chlom_wallet.policy_algorithm_suites_v1',
      'chlom_wallet.policy_algorithm_definitions_v1',
      'chlom_wallet.policy_packages_v1',
      'chlom_wallet.policy_compiled_artifacts_v1',
      'chlom_wallet.policy_simulation_runs_v1',
      'chlom_wallet.meter_definitions_v1',
      'chlom_wallet.license_package_candidates_v1',
      'chlom_wallet.usage_event_receipts_v1',
      'chlom_wallet.usage_rollup_snapshots_v1',
      'chlom_wallet.policy_advisor_proposals_v1',
      'chlom_wallet.policy_metering_canary_runs_v1'
    ],
    functions: [
      'chlom_wallet.evaluate_usage_budget_v1',
      'chlom_wallet.record_usage_event_v1',
      'chlom_wallet.run_policy_metering_canary_v1',
      'public.chlom_wallet_policy_metering_status_v1'
    ],
    rls_deny_all: true,
    append_or_version_only: true,
    private_writes_service_role_only: true,
    public_status_read_only: true,
  },
  monetization: {
    commercial_family: 'CHLOM WalletKit',
    metering_controlled_test: true,
    price_calculation_enabled: false,
    billing_enabled: false,
    effective_offer: false,
    public_price: false,
    stripe_product_created: false,
    stripe_price_created: false,
    checkout_enabled: false,
    independent_price_review_request: 'ct.price-review.chlom-wallet.phase-b.v1',
  },
  source_files: [
    'developers/reference/chlom-wallet/policy/policy-engine.mjs',
    'developers/reference/chlom-wallet/policy/metering-engine.mjs',
    'developers/reference/chlom-wallet/policy/policy-advisor.mjs',
    'developers/reference/chlom-wallet/policy/fixtures/walletkit-controlled-policy.v1.json',
    'developers/reference/chlom-wallet/policy/fixtures/walletkit-synthetic-license.v1.json',
    'developers/reference/chlom-wallet/policy/wallet-policy-package.v1.schema.json',
    'developers/reference/chlom-wallet/policy/wallet-policy-decision-receipt.v1.schema.json',
    'developers/reference/chlom-wallet/policy/wallet-usage-event.v1.schema.json',
    'developers/reference/chlom-wallet/policy/wallet-license-candidate.v1.schema.json',
    'developers/reference/chlom-wallet/policy/test-policy-metering-engine.mjs',
    'developers/reference/chlom-wallet/policy/test-policy-schemas.mjs',
    'developers/reference/chlom-wallet/policy/supabase-policy-metering-v1.sql',
    'developers/chlom-wallet-policy-metering-engine.mdx',
    '.github/workflows/chlom-wallet-policy-metering-engine.yml'
  ],
  hard_boundaries: {
    external_model_authority: false,
    auto_policy_activation: false,
    effective_policy: false,
    provider_write: false,
    production_rights_grant: false,
    credential_activation: false,
    chain_broadcast: false,
    custody: false,
    token_issuance: false,
    money_movement: false,
    effective_price_publication: false,
    checkout_activation: false,
    phase_advancement: false,
    merge_authorized: false,
  },
  source_ref: 'github:crownthrive1/CrownThrive-Support:pull/230',
  observed_on: '2026-08-23',
};

const manifest = {
  ...manifestBody,
  manifest_digest_sha256: sha256Hex(canonicalize(manifestBody)),
};
const output = `${JSON.stringify(manifest, null, 2)}\n`;
const outputArg = process.argv[2];
if (outputArg) writeFileSync(resolve(outputArg), output, 'utf8');
else process.stdout.write(output);
