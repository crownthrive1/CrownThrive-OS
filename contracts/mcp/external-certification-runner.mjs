#!/usr/bin/env node
import fs from 'node:fs';

const plan = JSON.parse(fs.readFileSync(new URL('./external-certification-plan.v1.json', import.meta.url), 'utf8'));
if (process.env.MCP_CERTIFICATION_LIVE === 'true') {
  throw new Error('CT-MCP-EXTCERT-001 is on security hold; live execution is disabled');
}
if (plan.state !== 'security_hold_replacement_required') throw new Error('unexpected certification lifecycle state');
if (plan.authority.execution_enabled !== false) throw new Error('execution must remain disabled');
if (plan.authority.provider_reads_enabled !== false || plan.authority.provider_writes_enabled !== false) throw new Error('provider access must remain disabled');
if (plan.authority.oidc_minting_enabled !== false) throw new Error('OIDC minting must remain disabled');
if (plan.acceptance_predicates.length !== 15) throw new Error('acceptance predicate cardinality drift');

console.log(JSON.stringify({
  certification_id: plan.certification_id,
  state: plan.state,
  execution_enabled: false,
  provider_reads: 0,
  provider_writes: 0,
  acceptance_predicates: plan.acceptance_predicates.length
}, null, 2));

