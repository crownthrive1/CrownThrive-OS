import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

const runFactory = (out) => execFileSync(process.execPath,['src/factory.mjs','--output',out,'--at','2026-09-02T21:17:00.000Z'],{cwd:process.cwd(),stdio:'pipe'});
const runPentaGreen = (out,bindings) => execFileSync(process.execPath,['src/pentagreen.mjs','--output',out,...(bindings?['--bindings',bindings]:[])],{cwd:process.cwd(),stdio:'pipe'});

test('PentaGreen processor preserves HOLD without exact bindings', async () => {
  const out=await mkdtemp(join(tmpdir(),'ct-pg-hold-'));
  runFactory(out); runPentaGreen(out);
  const processed=JSON.parse(await readFile(join(out,'pentagreen/processed-batch.json'),'utf8'));
  assert.equal(processed.processing.ecac,0);
  assert.equal(processed.processing.hold,10);
  assert.ok(processed.handoffs.every(h=>h.state==='HOLD'));
});

test('PentaGreen processor emits ECAC only for a fully evidenced exact subject', async () => {
  const out=await mkdtemp(join(tmpdir(),'ct-pg-ecac-'));
  runFactory(out);
  const batch=JSON.parse(await readFile(join(out,'pentagreen/current-batch.json'),'utf8'));
  const skill=batch.handoffs[0].skill_id;
  const binding={by_skill_id:{[skill]:{
    rights:{status:'VERIFIED_CROWNTHRIVE_AUTHORITY',authority_ref:'rights:synthetic-test'},
    price:{provider_product_id:'prod_test',provider_price_id:'price_test'},
    tax:{status:'VERIFIED_TEST',provider_tax_code:'txcd_test'},
    fulfillment:{provider_destination_id:'dest_fulfillment_test',receipt_id:'fulfill_receipt_test'},
    entitlement:{contract_id:'entitlement_test'},destination:{provider_id:'channel_test',url:'https://example.invalid/test'},
    provider_readback:{receipt_id:'provider_receipt_test',observed_at:'2026-09-02T21:18:00Z',observed_state:'ACTIVE'}
  }}};
  const path=join(out,'bindings.json'); await writeFile(path,JSON.stringify(binding));
  runPentaGreen(out,path);
  const processed=JSON.parse(await readFile(join(out,'pentagreen/processed-batch.json'),'utf8'));
  assert.equal(processed.processing.ecac,1);
  assert.equal(processed.processing.hold,9);
  assert.equal(processed.handoffs[0].state,'ECAC');
});


test('PentaGreen processor is idempotent for the same tick and binding set', async () => {
  const out=await mkdtemp(join(tmpdir(),'ct-pg-idem-'));
  runFactory(out);
  runPentaGreen(out);
  const first=JSON.parse(await readFile(join(out,'pentagreen/processing-receipt.json'),'utf8'));
  const stdout=runPentaGreen(out).toString();
  const second=JSON.parse(stdout);
  assert.equal(second.idempotent,true);
  assert.equal(second.processing_key,first.processing_key);
  assert.equal(second.result_hash,first.result_hash);
});
