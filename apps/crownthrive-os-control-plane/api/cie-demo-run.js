const ALLOWED = new Set(['salon','media','platform','institution','agency']);
const UPSTREAM = 'https://crown-thrive-os.vercel.app/api/cie-demo';

export default async function handler(request, response) {
  response.setHeader('Cache-Control','no-store, max-age=0');
  response.setHeader('Content-Type','application/json; charset=utf-8');
  response.setHeader('X-Content-Type-Options','nosniff');
  response.setHeader('Access-Control-Allow-Origin','*');
  if (!['GET','HEAD'].includes(request.method)) {
    response.setHeader('Allow','GET, HEAD');
    return response.status(405).json({error:'method_not_allowed'});
  }
  const preset = String(request.query?.preset || 'media').trim().toLowerCase();
  if (!ALLOWED.has(preset)) return response.status(400).json({error:'unknown_preset',allowed:[...ALLOWED]});
  try {
    const runResponse = await fetch(UPSTREAM, {
      method:'POST',
      headers:{'content-type':'application/json','user-agent':'CrownThrive-CIE-Proof-Bridge/1.0'},
      body:JSON.stringify({preset}),
    });
    const data = await runResponse.json();
    response.setHeader('X-CrownThrive-CIE-Proof-Bridge','1.0');
    if (request.method === 'HEAD') return response.status(runResponse.status).end();
    return response.status(runResponse.status).json({
      schema:'ct.cie.shareable-demo-run.v1',
      preset,
      upstream_status:runResponse.status,
      executed_via:'GET_TO_LIVE_POST_BRIDGE',
      upstream:UPSTREAM,
      run:data,
    });
  } catch (error) {
    return response.status(502).json({error:'demo_bridge_failed',message:String(error?.message || error)});
  }
}
