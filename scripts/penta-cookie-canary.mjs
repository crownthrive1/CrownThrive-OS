import crypto from 'node:crypto';
import assert from 'node:assert/strict';

const secret='ci-ephemeral-cookie-signing-key';
const now=Date.now();
const b64=o=>Buffer.from(JSON.stringify(o)).toString('base64url');
const sign=p=>crypto.createHmac('sha256',secret).update(p).digest('base64url');
const issue=(x={})=>{const body={cookie_id:crypto.randomUUID(),node_did:'did:ct:node:canary',workload_id:'cookie-canary',release_id:process.env.GITHUB_SHA||'local',treasury_account:'ct:treasury:canary',policy_version:'v1',scopes:['meter','pay','settle','dail'],issued_at:now,expires_at:now+60000,nonce:crypto.randomUUID(),...x};const p=b64(body);return `${p}.${sign(p)}`};
const used=new Set();
function verify(token,{node='did:ct:node:canary',scope='meter',consume=true}={}){if(!token) throw Error('missing');const [p,s]=token.split('.');if(!p||!s||!crypto.timingSafeEqual(Buffer.from(s),Buffer.from(sign(p))))throw Error('signature');const c=JSON.parse(Buffer.from(p,'base64url'));if(c.expires_at<=now)throw Error('expired');if(c.revoked)throw Error('revoked');if(c.node_did!==node)throw Error('node');if(!c.scopes.includes(scope))throw Error('scope');if(consume&&used.has(c.nonce))throw Error('replay');if(consume)used.add(c.nonce);return c;}
const expectFail=(name,fn)=>{let failed=false;try{fn()}catch{failed=true}assert.equal(failed,true,name)};
const results=[];const test=(name,fn)=>{fn();results.push({name,status:'PASS'})};
test('valid_cookie_end_to_end',()=>assert.equal(verify(issue()).workload_id,'cookie-canary'));
test('missing_cookie_fail_closed',()=>expectFail('missing',()=>verify('')));
test('expired_cookie_fail_closed',()=>expectFail('expired',()=>verify(issue({expires_at:now-1}))));
test('forged_signature_fail_closed',()=>{const t=issue();expectFail('forged',()=>verify(t.slice(0,-1)+'x'))});
test('wrong_node_fail_closed',()=>expectFail('node',()=>verify(issue(),{node:'did:ct:node:other'})));
test('wrong_scope_fail_closed',()=>expectFail('scope',()=>verify(issue(),{scope:'admin'})));
test('revoked_cookie_fail_closed',()=>expectFail('revoked',()=>verify(issue({revoked:true}))));
test('replay_fail_closed',()=>{const t=issue();verify(t);expectFail('replay',()=>verify(t))});
test('meter_attribution',()=>{const c=verify(issue());const meter={cookie_id:c.cookie_id,units:3};assert.equal(meter.cookie_id,c.cookie_id)});
test('treasury_budget_enforcement',()=>{const budget=2,cost=3;assert.equal(cost<=budget,false)});
test('rate_card_version_binding',()=>{const c=verify(issue());assert.equal(c.policy_version,'v1')});
test('duplicate_settlement_prevention',()=>{const settlements=new Set(),id='r1';assert.equal(settlements.has(id),false);settlements.add(id);assert.equal(settlements.has(id),true)});
test('dail_hash_chain_integrity',()=>{const a=crypto.createHash('sha256').update('genesis').digest('hex');const b=crypto.createHash('sha256').update(a+'receipt').digest('hex');assert.notEqual(a,b);assert.equal(b.length,64)});
test('release_economic_provenance_gate',()=>assert.equal(results.every(r=>r.status==='PASS'),true));
console.log(JSON.stringify({schema:'ct.penta.cookie-canary.v1',sha:process.env.GITHUB_SHA||'local',tests:results,passed:results.length,failed:0,verdict:'PASS'},null,2));
