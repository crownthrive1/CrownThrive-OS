#!/usr/bin/env node
import { readFile, writeFile, mkdir, access } from 'node:fs/promises';
import { resolve, dirname, join } from 'node:path';
import { createHash } from 'node:crypto';

const argv = process.argv.slice(2);
const arg = (name) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : null; };
const root = process.cwd();
const outputRoot = resolve(root, arg('--output') || 'generated');
const readJson = async (path) => JSON.parse(await readFile(path, 'utf8'));
const atomicJson = async (path, value) => { await mkdir(dirname(path), { recursive: true }); const tmp=`${path}.tmp`; await writeFile(tmp, `${JSON.stringify(value,null,2)}\n`); const {rename}=await import('node:fs/promises'); await rename(tmp,path); };
const sha = (value) => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const nonempty = (value) => value !== null && value !== undefined && value !== '';
const exists = async (path) => { try { await access(path); return true; } catch { return false; } };
const get = (obj, path) => path.split('.').reduce((acc,key)=>acc?.[key],obj);
const set = (obj, path, value) => { const keys=path.split('.'); let cur=obj; for(const key of keys.slice(0,-1)){cur[key] ??= {}; cur=cur[key];} cur[keys.at(-1)]=value; };

const config = await readJson(resolve(root,'config/factory.config.json'));
const batchPath = join(outputRoot,'pentagreen/current-batch.json');
const statusPath = join(outputRoot,'current-status.json');
const batch = await readJson(batchPath);
let bindings = {};
const bindingsPath = arg('--bindings') || process.env.PENTAGREEN_BINDINGS_PATH;
if (bindingsPath) bindings = await readJson(resolve(root,bindingsPath));
else if (process.env.PENTAGREEN_BINDINGS_JSON?.trim()) bindings = JSON.parse(process.env.PENTAGREEN_BINDINGS_JSON);
const byHandoff = bindings.by_handoff_id || {};
const bySkill = bindings.by_skill_id || {};
const bindingHash = sha(bindings);
const processingKey = sha({ tick_id: batch.tick_id, binding_hash: bindingHash });
const processedBatchPath = join(outputRoot,'pentagreen/processed-batch.json');
const processingReceiptPath = join(outputRoot,'pentagreen/processing-receipt.json');
if (await exists(processingReceiptPath) && await exists(processedBatchPath)) {
  const previous = await readJson(processingReceiptPath);
  if (previous.processing_key === processingKey) {
    console.log(JSON.stringify({ ...previous, idempotent: true }));
    process.exit(0);
  }
}
const allowedPaths = [
  'rights.status','rights.authority_ref','price.provider_product_id','price.provider_price_id',
  'tax.status','tax.provider_tax_code','fulfillment.provider_destination_id','fulfillment.receipt_id',
  'entitlement.contract_id','destination.provider_id','destination.url',
  'provider_readback.receipt_id','provider_readback.observed_at','provider_readback.observed_state'
];
const stateNames = {
  'rights.authority_ref':'MISSING_RIGHTS_AUTHORITY_REF',
  'price.provider_price_id':'MISSING_PROVIDER_PRICE_ID',
  'tax.provider_tax_code':'MISSING_PROVIDER_TAX_CODE',
  'fulfillment.provider_destination_id':'MISSING_FULFILLMENT_DESTINATION',
  'entitlement.contract_id':'MISSING_ENTITLEMENT_CONTRACT',
  'destination.provider_id':'MISSING_PROVIDER_DESTINATION',
  'provider_readback.receipt_id':'MISSING_PROVIDER_READBACK'
};
const acceptedObservedStates = new Set(['ACTIVE','PUBLISHED','READY','VERIFIED']);
const processedAt = new Date().toISOString();
const processed = batch.handoffs.map((original) => {
  const handoff = structuredClone(original);
  const binding = { ...(bySkill[handoff.skill_id] || {}), ...(byHandoff[handoff.handoff_id] || {}) };
  for (const path of allowedPaths) { const value=get(binding,path); if(nonempty(value)) set(handoff,path,value); }
  const missing = config.pentagreen.required_activation_fields.filter(path => !nonempty(get(handoff,path))).map(path => stateNames[path] || `MISSING_${path.toUpperCase().replaceAll('.','_')}`);
  if (nonempty(handoff.provider_readback.receipt_id) && !acceptedObservedStates.has(String(handoff.provider_readback.observed_state || '').toUpperCase())) missing.push('INVALID_PROVIDER_OBSERVED_STATE');
  handoff.hold_reasons = [...new Set(missing)];
  handoff.state = handoff.hold_reasons.length === 0 ? 'ECAC' : 'HOLD';
  handoff.processed_at = processedAt;
  return handoff;
});
const ecac = processed.filter(h=>h.state==='ECAC').length;
const hold = processed.length - ecac;
const receipt = {
  schema_version:'1.0.0', processor_id:'ct.pentagreen.skills.processor.v1',
  tick_id:batch.tick_id, processed_at:processedAt, total:processed.length,
  processing_key:processingKey, binding_hash:bindingHash,
  ecac, hold, binding_source:bindingsPath ? 'FILE' : process.env.PENTAGREEN_BINDINGS_JSON?.trim() ? 'ENV_JSON' : 'NONE',
  result_hash:sha(processed.map(({processed_at,...handoff})=>handoff)), idempotent:false, truth_boundary:'ECAC is emitted only after every required exact field and an accepted provider-observed state are present.'
};
await atomicJson(processedBatchPath,{...batch,handoffs:processed,processing:receipt});
await atomicJson(processingReceiptPath,receipt);
const status = await readJson(statusPath);
status.current_batch = {...status.current_batch, commercial_ecac:ecac, commercial_hold:hold};
status.provider_state = {...status.provider_state, live_commerce:ecac===processed.length && processed.length>0 ? 'ECAC_PROVIDER_READBACK_VERIFIED' : ecac>0 ? 'PARTIAL_ECAC_PROVIDER_READBACK_VERIFIED' : 'HOLD_PROVIDER_BINDING'};
status.pentagreen_processing = receipt;
await atomicJson(statusPath,status);
console.log(JSON.stringify(receipt));
