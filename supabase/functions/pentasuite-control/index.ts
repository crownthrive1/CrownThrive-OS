import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json; charset=utf-8" },
});

function decodeJwtPayload(auth: string | null): Record<string, unknown> {
  if (!auth?.startsWith("Bearer ")) return {};
  try {
    const token = auth.slice(7);
    const payload = token.split(".")[1];
    const padded = payload.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(payload.length / 4) * 4, "=");
    return JSON.parse(atob(padded));
  } catch {
    return {};
  }
}

function authorized(payload: Record<string, unknown>): boolean {
  if (payload.role === "service_role") return true;
  const app = (payload.app_metadata ?? {}) as Record<string, unknown>;
  return ["operator", "adjudicator", "governance"].includes(String(app.pentasuite_role ?? ""));
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ ok: false, error: "POST required" }, 405);

  const claims = decodeJwtPayload(req.headers.get("authorization"));
  if (!authorized(claims)) return json({ ok: false, error: "PentaSuite operator authority required" }, 403);

  const url = Deno.env.get("SUPABASE_URL");
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !key) return json({ ok: false, error: "runtime control-plane configuration missing" }, 500);

  const sb = createClient(url, key, { auth: { persistSession: false } });

  let body: Record<string, unknown> = {};
  try {
    body = await req.json();
  } catch {
    return json({ ok: false, error: "invalid JSON" }, 400);
  }

  const action = String(body.action ?? "status");

  try {
    if (action === "status") {
      const [{ count: rfa }, { count: leases }, { count: appeals }, { data: active }, { data: lockouts }] = await Promise.all([
        sb.from("pentarfa_agent_requests").select("id", { count: "exact", head: true }),
        sb.from("pentasuite_agent_leases").select("id", { count: "exact", head: true }),
        sb.from("pentasuite_appeals").select("id", { count: "exact", head: true }),
        sb.from("pentasuite_agent_leases")
          .select("id,agent_key,state,expires_at,remediation_due_at,reapply_after,strike_count")
          .in("state", ["active", "conditional", "remediation", "restricted", "suspended", "rollback_pending", "barred"])
          .order("updated_at", { ascending: false })
          .limit(100),
        sb.from("pentasuite_lockouts")
          .select("id,requester_ref,agent_key,reason,ends_at,strike_count")
          .eq("state", "active")
          .gt("ends_at", new Date().toISOString())
          .order("ends_at", { ascending: true })
          .limit(100),
      ]);

      return json({
        ok: true,
        contract: "ct.pentasuite.control.v1.0.1",
        rfa_count: rfa ?? 0,
        lease_count: leases ?? 0,
        appeal_count: appeals ?? 0,
        active_leases: active ?? [],
        active_lockouts: lockouts ?? [],
        governance: {
          appeals_layer: "ThriveAlumni - The Governmental Layer",
          primary_body: "Membership and Ethics Committee",
          final_body: "Board of Directors",
        },
      });
    }

    const rpcMap: Record<string, string> = {
      submit_rfa: "pentarfa_submit_agent_request",
      adjudicate: "pentarfa_adjudicate_agent_request",
      materialize: "pentasuite_materialize_agent",
      heartbeat: "pentasuite_heartbeat",
      submit_remediation: "pentasuite_submit_remediation",
      verify_remediation: "pentasuite_verify_remediation",
      enforce: "pentasuite_enforce_lease",
      record_violation: "pentasuite_record_violation",
      file_appeal: "pentasuite_file_appeal",
      review_appeal: "pentasuite_review_appeal",
      decide_appeal: "pentasuite_decide_appeal",
      tick: "pentasuite_tick",
    };

    const rpc = rpcMap[action];
    if (!rpc) return json({ ok: false, error: "unknown action" }, 400);

    const args = (body.args ?? {}) as Record<string, unknown>;
    const { data, error } = await sb.rpc(rpc, args);
    if (error) return json({ ok: false, action, error: "request_rejected", code: error.code ?? "RPC_ERROR" }, 409);

    return json({ ok: true, action, result: data });
  } catch {
    return json({
      ok: false,
      action,
      error: "internal_control_plane_error",
    }, 500);
  }
});
