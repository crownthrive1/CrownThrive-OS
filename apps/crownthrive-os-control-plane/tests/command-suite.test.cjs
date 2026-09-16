const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const modulePromise = import('../api/command-suite.js');
const U='d6b82fa4-c3da-47f6-a169-72705004d0cd', R='8f7ca31f-c430-49d7-8d71-52c8bfe55494';
const token='eyJtest.authorized_operator_token.signature_for_tests';
const env={SUPABASE_URL:'https://tzajnzshmtzjenqulehq.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'synthetic-server-key',VERCEL_URL:'command-test.vercel.app'};
const overview={schema:'ct.command.operating-suite.v1',sources:[],observed_at:new Date().toISOString()};
function fixture(overrides={}){
 const calls=[];
 const fetcher=async(url,options)=>{
  const p=new URL(url).pathname, input=options.body?JSON.parse(options.body):null;calls.push({url,options,input});
  let result=p==='/auth/v1/user'?{id:U,email:'operator@example.test'}:p==='/auth/v1/token'?{access_token:token,expires_in:3600}:p.endsWith('ct_pentabrain_operator_authorized_v1')?true:p.endsWith('ct_command_suite_overview_v1')?overview:p.endsWith('ct_command_suite_records_v1')?{schema:'ct.command.operating-suite.records.v1',status:'OBSERVED',source:{keys:['id'],fields:['name','state','secret']},rows:[{id:1,name:'Record',state:'held',secret:'must-not-leak',payload:{bad:true},_cursor:{id:1},unexpected:'must-not-leak'}],next_cursor:{id:1}}:p.endsWith('ct_command_suite_request_v1')?{request_id:R,state:'queued',execution_effect:'REQUEST_ONLY'}:p.endsWith('ct_command_suite_request_read_v1')?{request_id:R,state:'completed',execution_effect:'COMMAND_SOURCE_METADATA_READBACK'}:'receipt-test';
  let status=200;if(overrides[p]){const v=overrides[p](input,options);if(v instanceof Error)throw v;result=v?.result??v;status=v?.http??200;}
  return new Response(JSON.stringify(result),{status,headers:{'Content-Type':'application/json'}});
 };
 const call=async(req={},customEnv=env)=>{const {createHandler}=await modulePromise;const res={headers:{},statusCode:0,setHeader(k,v){this.headers[k]=v},status(v){this.statusCode=v;return this},json(v){this.value=v;return this},end(){this.ended=true;return this}};await createHandler({env:customEnv,fetcher})({method:'GET',url:'/api/command-suite',headers:{},...req},res);return res;};
 return {calls,call};
}
const auth={authorization:`Bearer ${token}`};
const csrf={origin:'https://crown-thrive-os.vercel.app','x-command-suite':'1',...auth};
test('overview works without a private session; strictly no cache',async()=>{const f=fixture(),r=await f.call();assert.equal(r.statusCode,200);assert.equal(r.headers['Cache-Control'],'private, no-store, max-age=0');assert.equal(f.calls.length,1);});
test('private records reject absent authentication without calling provider',async()=>{const f=fixture(),r=await f.call({url:'/?op=records&source=websites'});assert.equal(r.statusCode,401);assert.equal(f.calls.length,0);});
test('invalid method denied',async()=>{assert.equal((await fixture().call({method:'DELETE'})).statusCode,405);});
test('wrong backend origin cannot use server credential',async()=>{const f=fixture();assert.equal((await f.call({}, {...env,SUPABASE_URL:'https://evil.example'})).statusCode,503);assert.equal(f.calls.length,0);});
test('provider identity and existing operator grant required',async()=>{const f=fixture({'/rest/v1/rpc/ct_pentabrain_operator_authorized_v1':()=>false});const r=await f.call({url:'/?op=records&source=websites',headers:auth});assert.equal(r.statusCode,403);assert.equal(f.calls.length,2);});
test('private rows retain only allowlisted fields, never secrets or payloads',async()=>{const f=fixture(),r=await f.call({url:'/?op=records&source=websites',headers:auth});assert.equal(r.statusCode,200);assert.deepEqual(r.value.rows,[{id:1,name:'Record',state:'held'}]);assert.equal(f.calls[2].input.p_user_id,U);});
test('unknown source syntax rejected before record RPC',async()=>{const f=fixture(),r=await f.call({url:'/?op=records&source=websites%3BDROP',headers:auth});assert.equal(r.statusCode,400);assert.equal(f.calls.length,2);});
test('query and pagination preserve values as parameters',async()=>{const f=fixture(),q="%_' OR 1=1 --",cursor={id:7};await f.call({url:'/?op=records&source=websites&q='+encodeURIComponent(q)+'&cursor='+encodeURIComponent(JSON.stringify(cursor)),headers:auth});assert.deepEqual(f.calls[2].input,{p_user_id:U,p_source:'websites',p_query:q,p_cursor:cursor,p_limit:50});});
for(const [name,query] of [['limit','limit=999'],['cursor','cursor=%5B%5D'],['long query','q='+('a'.repeat(121))]])test('invalid '+name+' rejected',async()=>{assert.equal((await fixture().call({url:'/?op=records&source=websites&'+query,headers:auth})).statusCode,400);});
test('management rejects cross origin',async()=>{const f=fixture(),r=await f.call({method:'POST',headers:{...csrf,origin:'https://evil.example'},body:{op:'request',source:'websites',action:'reconcile',request_id:R}});assert.equal(r.statusCode,403);assert.equal(f.calls.length,0);});
test('management rejects missing CSRF header',async()=>{const r=await fixture().call({method:'POST',headers:{origin:csrf.origin,...auth},body:{op:'logout'}});assert.equal(r.statusCode,403);});
test('management accepts exact request but does not claim completion',async()=>{const f=fixture(),r=await f.call({method:'POST',headers:csrf,body:{op:'request',source:'websites',action:'reconcile',request_id:R}});assert.equal(r.statusCode,202);assert.equal(r.value.state,'queued');assert.equal(f.calls[2].input.p_user_id,U);});
test('caller cannot inject operator identity or generic SQL',async()=>{const f=fixture(),r=await f.call({method:'POST',headers:csrf,body:{op:'request',source:'websites',action:'reconcile',request_id:R,p_user_id:U,sql:'select 1'}});assert.equal(r.statusCode,400);assert.equal(f.calls.length,0);});
test('cannot publish through metadata controls',async()=>{assert.equal((await fixture().call({method:'POST',headers:csrf,body:{op:'request',source:'websites',action:'publish',request_id:R}})).statusCode,400);});
test('login uses existing grant, secure cookie and audit; no browser token response',async()=>{const f=fixture(),r=await f.call({method:'POST',headers:csrf,body:{op:'login',email:'operator@example.test',password:'synthetic-only'}});assert.equal(r.statusCode,200);assert.match(r.headers['Set-Cookie'],/HttpOnly; Secure; SameSite=Strict/);assert.match(r.headers['Set-Cookie'],/__Host-ct_command_operator=/);assert.ok(!JSON.stringify(r.value).includes(token));assert.equal(f.calls.length,4);assert.ok(!JSON.stringify(f.calls[3].input).includes('synthetic-only'));});
test('failed provider password sign-in does not disclose upstream details',async()=>{const f=fixture({'/auth/v1/token':()=>({http:400,result:{message:'private upstream debug'}})}),r=await f.call({method:'POST',headers:csrf,body:{op:'login',email:'operator@example.test',password:'synthetic-only'}});assert.equal(r.statusCode,401);assert.ok(!JSON.stringify(r.value).includes('private upstream'));});
test('httpOnly cookie authenticates private session',async()=>{const r=await fixture().call({url:'/?op=session',headers:{cookie:'__Host-ct_command_operator='+token}});assert.equal(r.statusCode,200);assert.equal(r.value.can_manage,true);});
test('logout clears cookie without changing grants',async()=>{const f=fixture(),r=await f.call({method:'POST',headers:csrf,body:{op:'logout'}});assert.equal(r.statusCode,200);assert.match(r.headers['Set-Cookie'],/Max-Age=0/);assert.equal(f.calls.length,0);});
test('request readback remains separate from request acceptance',async()=>{const r=await fixture().call({url:'/?op=request&id='+R,headers:auth});assert.equal(r.value.state,'completed');assert.equal(r.value.execution_effect,'COMMAND_SOURCE_METADATA_READBACK');});
test('large body rejected',async()=>{assert.equal((await fixture().call({method:'POST',headers:csrf,body:'a'.repeat(17000)})).statusCode,413);});
test('HEAD contains no body',async()=>{const r=await fixture().call({method:'HEAD'});assert.equal(r.statusCode,200);assert.equal(r.value,undefined);assert.equal(r.ended,true);});
test('frontend reuses existing refresh, no interval; waits for estate DOM',()=>{const js=fs.readFileSync(path.join(__dirname,'../command-suite.js'),'utf8');assert.ok(!js.includes('setInterval'));assert.match(js,/MutationObserver/);assert.match(js,/DOMContentLoaded/);assert.ok(!js.includes('innerHTML'));assert.ok(!js.includes('localStorage.setItem(\'token'));});
