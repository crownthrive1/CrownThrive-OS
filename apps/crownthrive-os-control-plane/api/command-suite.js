import { randomUUID } from 'node:crypto';

export const SCHEMA = 'ct.command.operating-suite.v1';
const ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const COOKIE = '__Host-ct_command_operator';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SOURCE = /^[a-z][a-z0-9-]{0,63}$/;
const SECRET_FIELDS = /^(password|secret|token|access_token|refresh_token|credential_ref|auth_ref|payload|body|config|metadata|signature_template|source_definition)$/i;
class Fault extends Error { constructor(code, status = 503) { super(code); this.status = status; } }
function header(req, key) { return String(req.headers?.[key] || req.headers?.get?.(key) || ''); }
function bearer(req) {
  const auth = header(req, 'authorization');
  if (auth) { const m = /^Bearer ([A-Za-z0-9_.-]{20,8192})$/.exec(auth); return m ? m[1] : null; }
  const raw = header(req, 'cookie').split(';').map(x => x.trim()).find(x => x.startsWith(`${COOKIE}=`));
  if (!raw) return null;
  const token = raw.slice(COOKIE.length + 1);
  return /^[A-Za-z0-9_.-]{20,8192}$/.test(token) ? token : null;
}
function body(req) {
  if (Number(header(req, 'content-length')) > 16384) throw new Fault('request_too_large', 413);
  let value = req.body;
  if (Buffer.isBuffer(value)) value = value.toString('utf8');
  if (typeof value === 'string') { if (Buffer.byteLength(value) > 16384) throw new Fault('request_too_large', 413); try { value = JSON.parse(value); } catch { throw new Fault('invalid_json', 400); } }
  if (!value || Array.isArray(value) || typeof value !== 'object' || Buffer.byteLength(JSON.stringify(value)) > 16384) throw new Fault('invalid_body', 400);
  return value;
}
function only(value, keys) { if (Object.keys(value).some(k => !keys.includes(k))) throw new Fault('unexpected_field', 400); }
function number(value, fallback = 50) { if (value == null || value === '') return fallback; if (!/^\d{1,3}$/.test(String(value)) || +value < 1 || +value > 100) throw new Fault('invalid_limit', 400); return +value; }
function safeRecords(value) {
  if (!value || value.schema !== 'ct.command.operating-suite.records.v1' || !Array.isArray(value.rows)) throw new Fault('source_contract_invalid');
  const allowed = new Set([...(value.source?.keys || []), ...(value.source?.fields || [])].filter(k => typeof k === 'string' && !SECRET_FIELDS.test(k)));
  return { ...value, rows: value.rows.map(row => Object.fromEntries(Object.entries(row).filter(([k]) => allowed.has(k)))) };
}
export function createHandler({ env = process.env, fetcher = globalThis.fetch } = {}) {
  return async function handler(req, res) {
    for (const [k,v] of Object.entries({ 'Cache-Control':'private, no-store, max-age=0', 'Content-Type':'application/json; charset=utf-8', 'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer', 'Vary':'Cookie, Authorization', 'X-CrownThrive-Suite-Contract':SCHEMA })) res.setHeader(k,v);
    const send = (status, value) => req.method === 'HEAD' ? res.status(status).end() : res.status(status).json(value);
    const clearCookie = () => res.setHeader('Set-Cookie', `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict`);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 7800);
    try {
      if (!['GET','HEAD','POST'].includes(req.method)) { res.setHeader('Allow','GET, HEAD, POST'); throw new Fault('method_not_allowed',405); }
      const origin = env.SUPABASE_URL || env.NEXT_PUBLIC_SUPABASE_URL;
      const key = env.SUPABASE_SERVICE_ROLE_KEY;
      if (![ORIGIN,`${ORIGIN}/`].includes(origin) || !key) throw new Fault('source_binding_unavailable');
      async function call(path, data, token = key, method = 'POST') {
        const response = await fetcher(`${ORIGIN}${path}`, { method, cache:'no-store', redirect:'error', signal:controller.signal,
          headers:{apikey:key, Authorization:`Bearer ${token}`, 'Content-Type':'application/json', Accept:'application/json'},
          ...(method === 'GET' ? {} : {body:JSON.stringify(data)}) });
        const size = Number(response.headers?.get?.('content-length'));
        if (size > 2*1024*1024) throw new Fault('source_response_too_large');
        const text = await response.text();
        if (Buffer.byteLength(text) > 2*1024*1024) throw new Fault('source_response_too_large');
        let result; try { result = JSON.parse(text); } catch { throw new Fault('source_response_invalid'); }
        if (!response.ok) {
          if (path.startsWith('/auth/v1/token') && response.status === 400) throw new Fault('sign_in_not_accepted',401);
          if (response.status === 429 || result?.message === 'RATE_LIMITED') throw new Fault('rate_limited',429);
          if (response.status === 401) throw new Fault('authentication_required',401);
          if (response.status === 403 || result?.code === '42501') throw new Fault('operator_access_denied',403);
          if (result?.code === '22023') throw new Fault('invalid_query',400);
          throw new Fault('source_read_failed');
        }
        return result;
      }
      const rpc = (name,data={}) => call(`/rest/v1/rpc/${name}`,data);
      async function identity(token) {
        if (!token) throw new Fault('authentication_required',401);
        const user = await call('/auth/v1/user',null,token,'GET');
        if (!UUID.test(user?.id || '')) throw new Fault('authentication_required',401);
        const allowed = await rpc('ct_pentabrain_operator_authorized_v1',{p_user_id:user.id,p_capability:'pentabrain.state.read'});
        if (allowed !== true) throw new Fault('operator_access_denied',403);
        return user;
      }
      function postOrigin() {
        const origins = new Set(['https://crown-thrive-os.vercel.app']);
        if (/^[a-z0-9-]+\.vercel\.app$/.test(env.VERCEL_URL || '')) origins.add(`https://${env.VERCEL_URL}`);
        if (!origins.has(header(req,'origin')) || header(req,'x-command-suite') !== '1') throw new Fault('same_origin_required',403);
      }
      if (req.method === 'POST') {
        postOrigin(); const data = body(req);
        if (data.op === 'logout') { only(data,['op']); clearCookie(); return send(200,{schema:SCHEMA,state:'SIGNED_OUT'}); }
        if (data.op === 'login') {
          only(data,['op','email','password']);
          if (typeof data.email !== 'string' || data.email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email) || typeof data.password !== 'string' || data.password.length < 1 || data.password.length > 4096) throw new Fault('invalid_sign_in',400);
          // Existing account only. No signup, grant creation, token logging, or persistent browser storage.
          const session = await call('/auth/v1/token?grant_type=password',{email:data.email.trim(),password:data.password});
          const user = await identity(session.access_token);
          const age = Math.min(3600,Number(session.expires_in));
          if (!Number.isFinite(age) || age < 1 || !/^[A-Za-z0-9_.-]{20,8192}$/.test(session.access_token || '')) throw new Fault('invalid_session');
          await rpc('ct_pentabrain_operator_audit_write',{p_trace_id:randomUUID(),p_user_id:user.id,p_user_email:user.email || '',p_action:'command.session.login',p_passed:true,p_status_code:200,p_input_sha256:null,p_evidence:{cookie_http_only:true,grant_created:false,credentials_logged:false}});
          res.setHeader('Set-Cookie',`${COOKIE}=${session.access_token}; Path=/; Max-Age=${Math.floor(age)}; HttpOnly; Secure; SameSite=Strict`);
          return send(200,{schema:SCHEMA,state:'SIGNED_IN',expires_in:Math.floor(age),new_grants_created:false});
        }
        if (data.op !== 'request') throw new Fault('operation_not_allowed',400);
        only(data,['op','source','action','request_id']);
        if (!SOURCE.test(data.source || '') || !['inspect','reconcile'].includes(data.action) || !UUID.test(data.request_id || '')) throw new Fault('invalid_request',400);
        const user = await identity(bearer(req));
        const value = await rpc('ct_command_suite_request_v1',{p_user_id:user.id,p_source:data.source,p_action:data.action,p_request_id:data.request_id});
        return send(202,{schema:SCHEMA,...value,execution_boundary:'Existing CHLOM worker; metadata inspection only, never a provider repair or publication claim.'});
      }
      const query = new URL(req.url,'https://crown-thrive-os.vercel.app').searchParams;
      const op = query.get('op') || 'overview';
      if (op === 'overview') {
        const value = await rpc('ct_command_suite_overview_v1');
        if (value?.schema !== SCHEMA || !Array.isArray(value.sources)) throw new Fault('source_contract_invalid');
        return send(200,value);
      }
      const user = await identity(bearer(req));
      if (op === 'session') {
        const manage = await rpc('ct_pentabrain_operator_authorized_v1',{p_user_id:user.id,p_capability:'pentabrain.operator.manage'});
        return send(200,{schema:SCHEMA,state:'SIGNED_IN',can_read:true,can_manage:manage === true,grant_source:'EXISTING_PENTABRAIN_OPERATOR_GRANT'});
      }
      if (op === 'records') {
        const source = query.get('source'), q = query.get('q') || '', raw = query.get('cursor');
        if (!SOURCE.test(source || '') || q.length > 120 || (raw && raw.length > 4096)) throw new Fault('invalid_query',400);
        let cursor = null; if (raw) { try {cursor=JSON.parse(raw);} catch {throw new Fault('invalid_cursor',400);} if (!cursor || typeof cursor !== 'object' || Array.isArray(cursor)) throw new Fault('invalid_cursor',400); }
        const value = await rpc('ct_command_suite_records_v1',{p_user_id:user.id,p_source:source,p_query:q,p_cursor:cursor,p_limit:number(query.get('limit'))});
        return send(200,safeRecords(value));
      }
      if (op === 'request') {
        const id = query.get('id'); if (!UUID.test(id || '')) throw new Fault('invalid_request',400);
        return send(200,{schema:SCHEMA,...await rpc('ct_command_suite_request_read_v1',{p_user_id:user.id,p_request_id:id})});
      }
      throw new Fault('operation_not_allowed',400);
    } catch(error) {
      if (error?.status === 401) clearCookie();
      return send(error instanceof Fault ? error.status : 503,{schema:SCHEMA,status:'UNAVAILABLE',error:error instanceof Fault ? error.message : 'source_unavailable',observed_at:new Date().toISOString(),pass_manufactured:false});
    } finally {clearTimeout(timeout);}
  };
}
export default createHandler();
