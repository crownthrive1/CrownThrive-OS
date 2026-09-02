import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const resource = JSON.parse(await readFile(new URL('../../.crownthrive/resources/go-flipbooks-platform.v1.json', import.meta.url), 'utf8'));
const federation = JSON.parse(await readFile(new URL('../../.crownthrive/federation/go-flipbooks.json', import.meta.url), 'utf8'));

test('Go Flipbooks resolves as one brand with three non-colliding lanes', () => {
  assert.equal(resource.canonical_subject, 'ct.platform.go-flipbooks');
  assert.deepEqual(resource.children.map((child) => child.id), [
    'ct.product.go-flipbooks.static',
    'ct.product.go-flipbooks.pro',
    'ct.service.go-flipbooks.production'
  ]);
});

test('OS federation binds PentaGreen, PentaAds, CHLOM, and exact source refs', () => {
  assert.equal(federation.resource, resource.canonical_subject);
  assert.equal(federation.integration_refs.pentaads_contract, resource.contracts.pentaads);
  assert.equal(federation.integration_refs.pentagreen_contract, resource.contracts.pentagreen);
  assert.equal(federation.verified_source_ref, resource.source.ref);
  assert.equal(resource.provider_boundaries.fliplink, 'server_side_api_only');
  assert.equal(resource.destructive_authority, 'founder_reserved');
});
