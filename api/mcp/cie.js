const SERVER = { name:'CrownThrive CIE MCP', version:'1.0.0' };
const PROTOCOL = '2026-07-28';
const FRAMEWORK = 'ct.framework.cultural-imprint-engine';
const LENSES = ['identity_depth','cultural_contribution','ecosystem_gravity','economic_utility','scalability_longevity','imprint_power'];
const TIERS = [
  {sku:'CIE-OPERATOR-001',name:'CIE Operator',priceUsd:299,checkout:'https://buy.stripe.com/00w3cu0Z6ec29eagFxbAs1P'},
  {sku:'CIE-STUDIO-001',name:'CIE Studio',priceUsd:799,checkout:'https://buy.stripe.com/fZu5kC9vCgka4XUgFxbAs1Q'},
  {sku:'CIE-AGENCY-001',name:'CIE Agency',priceUsd:2499,checkout:'https://buy.stripe.com/00weVc23a4Bsduq9d5bAs1R'},
  {sku:'CIE-INSTITUTION-001',name:'CIE Institutional',priceUsd:4999,checkout:'https://buy.stripe.com/aFa7sK37ed7YgGC2OHbAs1S'},
  {sku:'CIE-ENTERPRISE-001',name:'CIE Enterprise / White-label',priceUsd:7500,checkout:'https://buy.stripe.com/bJe9AScHO0lc2PM1KDbAs1T'}
];

const TOOLS = [
  {name:'cie_describe',description:'Describe the Cultural Imprint Engine, six lenses, product surfaces, and integration topology.',inputSchema:{type:'object',properties:{},additionalProperties:false}},
  {name:'cie_catalog',description:'Return current CIE license tiers, SKUs, prices, and live Stripe checkout URLs.',inputSchema:{type:'object',properties:{},additionalProperties:false}},
  {name:'cie_validate_imprint',description:'Validate a CIE imprint package against public conformance fields.',inputSchema:{type:'object',properties:{name:{type:'string'},identity:{type:'string'},audience:{type:'string'},voice:{type:'string'}},required:['name','identity','audience','voice'],additionalProperties:true}},
  {name:'cie_route',description:'Generate a non-mutating CrownThrive ecosystem route plan.',inputSchema:{type:'object',properties:{imprint_id:{type:'string'},requested_lanes:{type:'array',items:{type:'string'}}},additionalProperties:true}},
  {name:'cie_pentaads_plan',description:'Generate a provider-neutral PentaAds placement plan. Never spends money or performs provider writes.',inputSchema:{type:'object',properties:{placement_intent:{type:'string'},creative:{type:'object'},audience:{type:'object'},rights_evidence:{},safety_constraints:{type:'array'},measurement:{type:'object'}},additionalProperties:true}},
  {name:'cie_score_public',description:'Compute a transparent public-profile CIE score from six caller-supplied 1–10 lens values. Does not use protected calibration.',inputSchema:{type:'object',properties:Object.fromEntries(LENSES.map((x)=>[x,{type:'number',minimum:1,maximum:10}])),required:LENSES,additionalProperties:false}}
].map((tool)=>({...tool,annotations:{readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:false}}));

const RESOURCES = [
  {uri:'crownthrive://frameworks/cie',name:'cie-framework',title:'Cultural Imprint Engine',mimeType:'application/json'},
  {uri:'crownthrive://frameworks/cie/catalog',name:'cie-catalog',title:'CIE commercial catalog',mimeType:'application/json'},
  {uri:'crownthrive://frameworks/cie/pentaads',name:'cie-pentaads',title:'CIE → PentaAds integration',mimeType:'application/json'}
];

function text(value){return [{type:'text',text:JSON.stringify(value,null,2)}];}
function result(id,value){return {jsonrpc:'2.0',id,result:value};}
function error(id,code,message,data){return {jsonrpc:'2.0',id:id??null,error:{code,message,...(data===undefined?{}:{data})}};}
function score(args){
  const values={};
  for(const lens of LENSES){const n=Number(args?.[lens]); if(!Number.isFinite(n)||n<1||n>10) throw new TypeError(`${lens} must be between 1 and 10`); values[lens]=n;}
  const mean=LENSES.reduce((s,l)=>s+values[l],0)/LENSES.length;
  return {profile:'ct.cie.profile.public.v1',score_100:Number((mean*10).toFixed(2)),lens_scores:values,protected_calibration_used:false};
}
function route(args){
  const requested=Array.isArray(args?.requested_lanes)?args.requested_lanes:[];
  return {framework:FRAMEWORK,mode:'non_mutating_plan',imprint_id:args?.imprint_id||null,lanes:[...new Set(requested.length?requested:['CrownThrive Developer Marketplace','PentaAds Placement OS','CrownLytics','ThriveBase'])].slice(0,20),side_effect_performed:false};
}
function pentaads(args){return {framework:FRAMEWORK,integration:'PentaAds Placement OS',source_binding_sha:'608072f19b075352db2a05e91c47b4c6855f31aa',mode:'provider_neutral_placement_plan',placement_intent:args?.placement_intent||'brand_awareness',creative:args?.creative||null,audience:args?.audience||null,rights_evidence:args?.rights_evidence||null,safety_constraints:args?.safety_constraints||[],measurement:args?.measurement||{provider:'CrownLytics',events:['impression','click','conversion']},ad_spend_authority:false,provider_write_authority:false,side_effect_performed:false};}
function validate(args){const missing=['name','identity','audience','voice'].filter((k)=>!String(args?.[k]||'').trim());return {valid:missing.length===0,missing,framework:FRAMEWORK,protected_calibration_used:false};}
function callTool(name,args){
  if(name==='cie_describe') return {framework:FRAMEWORK,name:'Cultural Imprint Engine',lenses:LENSES,api:'https://crown-thrive-os.vercel.app/api/cie/v1/describe',commerce:'https://crown-thrive-os.vercel.app/frameworks/cie',pentaads:'connected'};
  if(name==='cie_catalog') return {framework:FRAMEWORK,currency:'USD',tiers:TIERS,embedded_oem:{state:'sales_assisted',contact:'contact@crownthrive.com'}};
  if(name==='cie_validate_imprint') return validate(args);
  if(name==='cie_route') return route(args);
  if(name==='cie_pentaads_plan') return pentaads(args);
  if(name==='cie_score_public') return score(args);
  throw new Error('UNKNOWN_TOOL');
}
function readResource(uri){
  if(uri==='crownthrive://frameworks/cie') return {framework:FRAMEWORK,name:'Cultural Imprint Engine',lenses:LENSES,version:'4.0.0-commercial'};
  if(uri==='crownthrive://frameworks/cie/catalog') return {tiers:TIERS,contact:'contact@crownthrive.com'};
  if(uri==='crownthrive://frameworks/cie/pentaads') return {binding:'ct.binding.crownthrive-cie-os.pentaads-placement-os',source_sha:'608072f19b075352db2a05e91c47b4c6855f31aa',ad_spend_authority:false,provider_write_authority:false};
  throw new Error('UNKNOWN_RESOURCE');
}

export default async function handler(req,res){
  res.setHeader('Cache-Control','no-store, max-age=0');
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Access-Control-Allow-Origin','*');
  res.setHeader('Access-Control-Allow-Methods','GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers','Content-Type, Mcp-Protocol-Version, Mcp-Method, Mcp-Name');
  if(req.method==='OPTIONS') return res.status(204).end();
  if(req.method==='GET') return res.status(200).json({server:SERVER,protocol:PROTOCOL,framework:FRAMEWORK,tools:TOOLS.map(({name,description})=>({name,description})),resources:RESOURCES});
  if(req.method!=='POST'){res.setHeader('Allow','GET,POST,OPTIONS');return res.status(405).json({error:'METHOD_NOT_ALLOWED'});}
  let payload=req.body;
  if(typeof payload==='string'){try{payload=JSON.parse(payload);}catch{return res.status(400).json(error(null,-32700,'Parse error'));}}
  const id=payload?.id??null;
  try{
    if(payload?.method==='initialize') return res.status(200).json(result(id,{protocolVersion:PROTOCOL,capabilities:{tools:{listChanged:false},resources:{subscribe:false,listChanged:false}},serverInfo:SERVER}));
    if(payload?.method==='ping') return res.status(200).json(result(id,{}));
    if(payload?.method==='tools/list') return res.status(200).json(result(id,{tools:TOOLS}));
    if(payload?.method==='tools/call') {const value=callTool(payload?.params?.name,payload?.params?.arguments||{});return res.status(200).json(result(id,{content:text(value),structuredContent:value,isError:false}));}
    if(payload?.method==='resources/list') return res.status(200).json(result(id,{resources:RESOURCES}));
    if(payload?.method==='resources/read'){const value=readResource(payload?.params?.uri);return res.status(200).json(result(id,{contents:[{uri:payload.params.uri,mimeType:'application/json',text:JSON.stringify(value,null,2)}]}));}
    return res.status(200).json(error(id,-32601,'Method not found'));
  }catch(err){return res.status(200).json(error(id,-32602,String(err?.message||err)));}
}
