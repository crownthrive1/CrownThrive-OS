import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const url = Deno.env.get("SUPABASE_URL")!;
const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db = createClient(url, key, { auth: { persistSession: false } });
const PROTOCOL = "2026-07-28";
const SERVER = { name: "PentaFlex", version: "1.0.0", contract: "ct.penta.flex.v1" };
const headers = { "content-type": "application/json", "cache-control": "no-store" };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers });
const rpc = (id: unknown, result: unknown) => json({ jsonrpc: "2.0", id: id ?? null, result });
const err = (id: unknown, code: number, message: string) => json({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });

async function status() {
  const [{ data: registry, error: re }, { data: vergence, error: ve }] = await Promise.all([
    db.schema("penta_runtime").rpc("penta_registry_status_v1"),
    db.schema("penta_runtime").rpc("penta_vergence_status_v1"),
  ]);
  if (re) throw new Error(re.message);
  if (ve) throw new Error(ve.message);
  return { contract: "ct.penta.flex.status.v1", server: SERVER, registry, vergence };
}
async function components() {
  const { data, error } = await db.schema("penta_runtime").from("component_registry_v1").select("component_key,canonical_name,role,primary_axis,stable_contract_id,implementation_state,aliases,enabled").eq("enabled", true).order("component_key");
  if (error) throw new Error(error.message);
  return { contract: "ct.penta.flex.components.v1", components: data ?? [] };
}
async function topology() {
  const { data, error } = await db.schema("penta_runtime").rpc("penta_topology_v1");
  if (error) throw new Error(error.message);
  return data;
}
async function agents() {
  const { data, error } = await db.schema("penta_runtime").from("agent_registry_v1").select("agent_id,canonical_name,owner_component_key,role,autonomy_ceiling,decision_ceiling,vote_eligible,self_approval,status,capabilities").eq("status", "active").order("agent_id");
  if (error) throw new Error(error.message);
  return { contract: "ct.penta.agents.catalog.v1", agents: data ?? [] };
}
const tools = [
  { name: "penta_status", description: "Read PentaOS registry and PentaVergence status.", inputSchema: { type: "object", properties: {}, additionalProperties: false } },
  { name: "penta_components", description: "List canonical Penta components and compatibility aliases.", inputSchema: { type: "object", properties: {}, additionalProperties: false } },
  { name: "penta_topology", description: "Return the PentaPology component graph.", inputSchema: { type: "object", properties: {}, additionalProperties: false } },
  { name: "penta_agents", description: "List executable PentaAgents identities and bounded capabilities.", inputSchema: { type: "object", properties: {}, additionalProperties: false } },
];
Deno.serve(async (req: Request) => {
  try {
    if (req.method === "GET") return json({ ok: true, server: SERVER, protocolVersion: PROTOCOL, writeTools: false });
    if (req.method !== "POST") return json({ error: "POST required" }, 405);
    const body = await req.json().catch(() => ({}));
    const id = body.id ?? null;
    const method = String(body.method ?? "");
    if (method === "initialize") return rpc(id, { protocolVersion: PROTOCOL, capabilities: { tools: { listChanged: false } }, serverInfo: SERVER });
    if (method === "tools/list") return rpc(id, { tools });
    if (method === "tools/call") {
      const name = String(body.params?.name ?? "");
      let value: unknown;
      if (name === "penta_status") value = await status();
      else if (name === "penta_components") value = await components();
      else if (name === "penta_topology") value = await topology();
      else if (name === "penta_agents") value = await agents();
      else return err(id, -32602, "unknown tool");
      return rpc(id, { content: [{ type: "text", text: JSON.stringify(value) }], structuredContent: value, isError: false });
    }
    return err(id, -32601, "method not found");
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return json({ jsonrpc: "2.0", id: null, error: { code: -32603, message } }, 500);
  }
});
