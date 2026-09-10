const VERSION = '1.0.0';
const FRAMEWORK = 'ct.framework.cultural-imprint-engine';
const LENSES = [
  'identity_depth',
  'cultural_contribution',
  'ecosystem_gravity',
  'economic_utility',
  'scalability_longevity',
  'imprint_power'
];

const TIERS = [
  { sku:'CIE-OPERATOR-001', name:'CIE Operator', priceUsd:299, checkout:'https://buy.stripe.com/00w3cu0Z6ec29eagFxbAs1P' },
  { sku:'CIE-STUDIO-001', name:'CIE Studio', priceUsd:799, checkout:'https://buy.stripe.com/fZu5kC9vCgka4XUgFxbAs1Q' },
  { sku:'CIE-AGENCY-001', name:'CIE Agency', priceUsd:2499, checkout:'https://buy.stripe.com/00weVc23a4Bsduq9d5bAs1R' },
  { sku:'CIE-INSTITUTION-001', name:'CIE Institutional', priceUsd:4999, checkout:'https://buy.stripe.com/aFa7sK37ed7YgGC2OHbAs1S' },
  { sku:'CIE-ENTERPRISE-001', name:'CIE Enterprise / White-label', priceUsd:7500, checkout:'https://buy.stripe.com/bJe9AScHO0lc2PM1KDbAs1T' }
];

function body(req) {
  if (!req.body) return {};
  if (typeof req.body === 'object') return req.body;
  try { return JSON.parse(req.body); } catch { return {}; }
}

function clampLens(value) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 1 && number <= 10 ? number : null;
}

function publicScore(input) {
  const values = Object.fromEntries(LENSES.map((lens) => [lens, clampLens(input?.[lens])]));
  const missing = LENSES.filter((lens) => values[lens] === null);
  if (missing.length) return { ok:false, missing_or_invalid:missing };
  const mean = LENSES.reduce((sum, lens) => sum + values[lens], 0) / LENSES.length;
  return {
    ok:true,
    profile:'ct.cie.profile.public.v1',
    score_100:Number((mean * 10).toFixed(2)),
    lens_scores:values,
    protected_calibration_used:false,
    note:'Public-profile arithmetic only. This is not the protected CrownThrive calibration runtime.'
  };
}

function validateImprint(input) {
  const imprint = input?.imprint || input;
  const required = ['name','identity','audience','voice'];
  const missing = required.filter((key) => !String(imprint?.[key] || '').trim());
  return {
    valid: missing.length === 0,
    missing,
    framework: FRAMEWORK,
    checked_rules: required,
    protected_calibration_used:false
  };
}

function routePlan(input) {
  const requested = Array.isArray(input?.requested_lanes) ? input.requested_lanes : [];
  const defaultLanes = ['CrownThrive Developer Marketplace','PentaAds Placement OS','CrownLytics','ThriveBase'];
  const lanes = [...new Set((requested.length ? requested : defaultLanes).map(String))].slice(0, 20);
  return {
    framework: FRAMEWORK,
    mode:'non_mutating_plan',
    imprint_id: input?.imprint_id || null,
    lanes,
    recommended_sequence:[
      'CIE imprint package',
      'rights/license evidence',
      'ecosystem routing',
      'distribution or commerce',
      'CrownLytics evidence',
      'Thrive Flywheel feedback'
    ],
    side_effect_performed:false
  };
}

function pentaAdsPlan(input) {
  return {
    framework:FRAMEWORK,
    integration:'PentaAds Placement OS',
    source_binding_sha:'608072f19b075352db2a05e91c47b4c6855f31aa',
    mode:'provider_neutral_placement_plan',
    placement_intent:input?.placement_intent || 'brand_awareness',
    creative:input?.creative || null,
    audience:input?.audience || null,
    rights_evidence:input?.rights_evidence || null,
    safety_constraints:input?.safety_constraints || [],
    measurement:input?.measurement || { provider:'CrownLytics', events:['impression','click','conversion'] },
    ad_spend_authority:false,
    provider_write_authority:false,
    side_effect_performed:false
  };
}

async function managedScore(req, res, input) {
  const upstream = process.env.CIE_MANAGED_RUNTIME_URL;
  const token = process.env.CIE_MANAGED_RUNTIME_TOKEN;
  if (!upstream || !token) {
    return res.status(503).json({
      error:'CIE_MANAGED_RUNTIME_NOT_BOUND',
      public_alternative:'/api/cie/v1/score-public',
      protected_calibration_exposed:false
    });
  }
  try {
    const response = await fetch(upstream, {
      method:'POST',
      headers:{'content-type':'application/json','authorization':`Bearer ${token}`},
      body:JSON.stringify(input),
      signal:AbortSignal.timeout(5000)
    });
    const text = await response.text();
    res.status(response.status);
    res.setHeader('content-type', response.headers.get('content-type') || 'application/json; charset=utf-8');
    return res.send(text);
  } catch (error) {
    return res.status(502).json({error:'CIE_MANAGED_RUNTIME_UPSTREAM_ERROR', detail:String(error?.message || error)});
  }
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control','no-store, max-age=0');
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Referrer-Policy','no-referrer');
  res.setHeader('Access-Control-Allow-Origin','*');
  res.setHeader('Access-Control-Allow-Methods','GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers','Content-Type, Authorization');
  if (req.method === 'OPTIONS') return res.status(204).end();

  const action = Array.isArray(req.query?.action) ? req.query.action[0] : String(req.query?.action || '');
  const input = body(req);

  if (req.method === 'GET' && action === 'health') {
    return res.status(200).json({ok:true, framework:FRAMEWORK, api_version:VERSION, release:'CIE 4.0.0-commercial', commit:process.env.VERCEL_GIT_COMMIT_SHA || null, observed_at:new Date().toISOString()});
  }
  if (req.method === 'GET' && action === 'describe') {
    return res.status(200).json({framework:FRAMEWORK, name:'Cultural Imprint Engine', api_version:VERSION, lenses:LENSES, capabilities:['describe','catalog','validate-imprint','route','pentaads-plan','score-public','score-managed'], commerce:'/frameworks/cie', mcp:'/api/mcp/cie'});
  }
  if (req.method === 'GET' && action === 'catalog') {
    return res.status(200).json({framework:FRAMEWORK, currency:'USD', tiers:TIERS, embedded_oem:{state:'sales_assisted',contact:'contact@crownthrive.com'}});
  }
  if (req.method === 'POST' && action === 'validate-imprint') return res.status(200).json(validateImprint(input));
  if (req.method === 'POST' && action === 'route') return res.status(200).json(routePlan(input));
  if (req.method === 'POST' && action === 'pentaads-plan') return res.status(200).json(pentaAdsPlan(input));
  if (req.method === 'POST' && action === 'score-public') {
    const result = publicScore(input?.lenses || input);
    return res.status(result.ok ? 200 : 400).json(result);
  }
  if (req.method === 'POST' && action === 'score-managed') return managedScore(req,res,input);

  return res.status(404).json({error:'CIE_ROUTE_NOT_FOUND', method:req.method, action, describe:'/api/cie/v1/describe'});
}
