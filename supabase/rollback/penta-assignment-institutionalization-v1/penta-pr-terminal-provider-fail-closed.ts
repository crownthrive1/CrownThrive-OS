import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const VERSION = "4.0.0-rollback-hold";
const SERVICE = "ct.penta.pr-terminalization.v4.rollback";

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return Response.json({ error: "method_not_allowed" }, { status: 405 });
  }
  const input = await req.json().catch(() => ({}));
  const op = String(input.op ?? "probe");
  if (op === "probe") {
    return Response.json({
      ok: true,
      service: SERVICE,
      version: VERSION,
      state: "HOLD_FAIL_CLOSED",
      provider_mutation_enabled: false,
      evidence_history_preserved: true,
      authority_expansion: false,
    });
  }
  return Response.json({
    ok: false,
    service: SERVICE,
    version: VERSION,
    state: "HOLD_FAIL_CLOSED",
    operation: op,
    mutation_performed: false,
    reason: "assignment institutionalization runtime rollback hold; repair and independent recertification required",
    evidence_history_preserved: true,
    authority_expansion: false,
  }, { status: 503 });
});
