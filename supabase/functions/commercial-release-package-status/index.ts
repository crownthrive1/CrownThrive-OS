import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const jsonHeaders = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
};

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: jsonHeaders });
}

Deno.serve(async (req: Request) => {
  if (req.method !== "GET") {
    return json(405, { error: "method_not_allowed", allowed: ["GET"] });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return json(503, { error: "server_configuration_unavailable" });
  }

  const client = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: { "x-crownthrive-service": "commercial-release-package-status" } },
  });

  const [{ data: rows, error: rowsError }, { data: runs, error: runsError }] = await Promise.all([
    client
      .schema("integration_control")
      .from("commercial_release_package_status_v1")
      .select("sku,platform_id,surface_id,package_state,credit_only,checkout_mode,package_sha256,certification_state,vote_state,release_state,gate_count,pass_gate_count,hold_gate_count,fail_gate_count,updated_at")
      .order("sku", { ascending: true }),
    client
      .schema("integration_control")
      .from("product_release_package_runs")
      .select("run_id,run_state,product_count,package_count,pass_gate_count,hold_gate_count,release_count,accepted_count,published_count,input_sha256,output_sha256,started_at,completed_at")
      .eq("source_system", "commercial-gap-sites-2026-08-21-v1")
      .order("started_at", { ascending: false })
      .limit(1),
  ]);

  if (rowsError || runsError) {
    console.error("commercial_release_status_query_failed", {
      rows: rowsError?.code ?? null,
      runs: runsError?.code ?? null,
    });
    return json(502, { error: "status_query_failed" });
  }

  const byPlatform: Record<string, {
    packages: number;
    pass_gates: number;
    hold_gates: number;
    fail_gates: number;
    accepted: number;
    published: number;
  }> = {};
  const stateCounts: Record<string, number> = {};

  for (const row of rows ?? []) {
    const platform = String(row.platform_id);
    const bucket = byPlatform[platform] ?? {
      packages: 0,
      pass_gates: 0,
      hold_gates: 0,
      fail_gates: 0,
      accepted: 0,
      published: 0,
    };
    bucket.packages += 1;
    bucket.pass_gates += Number(row.pass_gate_count ?? 0);
    bucket.hold_gates += Number(row.hold_gate_count ?? 0);
    bucket.fail_gates += Number(row.fail_gate_count ?? 0);
    bucket.accepted += row.release_state === "accepted" ? 1 : 0;
    bucket.published += row.package_state === "published" ? 1 : 0;
    byPlatform[platform] = bucket;

    const stateKey = `${row.certification_state}:${row.vote_state}:${row.release_state}`;
    stateCounts[stateKey] = (stateCounts[stateKey] ?? 0) + 1;
  }

  const latestRun = (runs ?? [])[0] ?? null;
  return json(200, {
    schema_version: "1.0.0",
    service_id: "ct.service.commercial-release-package-status",
    source_system: "commercial-gap-sites-2026-08-21-v1",
    credit_only: true,
    checkout_enabled: false,
    direct_provider_write: false,
    totals: {
      packages: (rows ?? []).length,
      pass_gates: (rows ?? []).reduce((sum, row) => sum + Number(row.pass_gate_count ?? 0), 0),
      hold_gates: (rows ?? []).reduce((sum, row) => sum + Number(row.hold_gate_count ?? 0), 0),
      fail_gates: (rows ?? []).reduce((sum, row) => sum + Number(row.fail_gate_count ?? 0), 0),
      accepted: (rows ?? []).filter((row) => row.release_state === "accepted").length,
      published: (rows ?? []).filter((row) => row.package_state === "published").length,
    },
    by_platform: byPlatform,
    release_states: stateCounts,
    latest_run: latestRun,
    generated_at: new Date().toISOString(),
  });
});
