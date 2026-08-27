import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-engine-mode",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Cache-Control": "no-store",
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);

  const url = Deno.env.get("SUPABASE_URL");
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const auth = req.headers.get("Authorization");
  if (!url || !key) return json({ ok: false, error: "runtime_configuration_missing" }, 500);
  if (!auth?.startsWith("Bearer ")) return json({ ok: false, error: "missing_authorization" }, 401);

  const service = createClient(url, key);
  const { data: userData, error: userError } = await service.auth.getUser(auth.slice(7));
  if (userError || !userData.user) return json({ ok: false, error: "unauthorized" }, 401);

  let body: any;
  try {
    body = await req.json();
  } catch {
    return json({ ok: false, error: "invalid_json" }, 400);
  }

  const action = String(body.action ?? "simulate_allocation");
  const mode = req.headers.get("x-engine-mode") ?? String(body.mode ?? "simulation");
  const gross = Number(body.gross_minor);
  if (!Number.isSafeInteger(gross) || gross <= 0) return json({ ok: false, error: "gross_minor_must_be_positive_integer" }, 400);

  const idempotencyKey = String(body.idempotency_key ?? "");
  if (idempotencyKey.length < 12) return json({ ok: false, error: "idempotency_key_required" }, 400);

  const internal = action === "settle_internal";
  if (internal && mode !== "hot") return json({ ok: false, state: "HOLD", reason: "settle_internal_requires_x-engine-mode_hot" }, 423);
  if (!internal && action !== "simulate_allocation") return json({ ok: false, error: "unsupported_action" }, 400);

  const contractKey = internal ? "CT-SFE-INTERNAL-SETTLEMENT-1.0" : String(body.contract_key ?? "CT-SFE-PROVIDER-80-1.0");
  const payload = {
    idempotency_key: idempotencyKey,
    provider_ref: internal ? "provider:stripe-connect" : String(body.provider_ref ?? "simulation:provider"),
    contract_key: contractKey,
    policy_key: "CT-SFE-80-10-5-3-2",
    currency: String(body.currency ?? "USD").toUpperCase(),
    gross_minor: gross,
    refundable_minor: gross,
    state: "received",
    compliance_state: "pass",
    rights_state: "pass",
    allocation_state: "pending",
    metadata: { mode: internal ? "hot_internal" : "simulation", actor: userData.user.id },
  };

  const { error: insertError } = await service
    .from("ct_self_funding_transactions")
    .upsert(payload, { onConflict: "idempotency_key", ignoreDuplicates: true });
  if (insertError) return json({ ok: false, error: insertError.message }, 500);

  const { data: transaction, error: transactionError } = await service
    .from("ct_self_funding_transactions")
    .select("transaction_id,idempotency_key,gross_minor,currency,policy_key,contract_key,state,allocation_state")
    .eq("idempotency_key", idempotencyKey)
    .single();
  if (transactionError || !transaction) return json({ ok: false, error: transactionError?.message ?? "transaction_not_found" }, 500);

  const { data: allocations, error: allocationError } = await service.rpc("ct_calculate_self_funding_allocations", {
    p_transaction_id: transaction.transaction_id,
  });
  if (allocationError) return json({ ok: false, error: allocationError.message }, 422);

  const total = (allocations ?? []).reduce((sum: number, row: any) => sum + Number(row.amount_minor), 0);
  if (total !== gross) return json({ ok: false, error: "allocation_total_mismatch", expected: gross, actual: total }, 500);

  if (!internal) {
    return json({
      ok: true,
      mode: "simulation",
      production_settlement: "available_for_internal_hot_route",
      transaction,
      allocations,
      allocation_total_minor: total,
    });
  }

  const providerAllocation = (allocations ?? []).find((row: any) => String(row.allocation_code) === "PROVIDER");
  if (!providerAllocation) return json({ ok: false, error: "provider_allocation_missing" }, 500);

  const dispatchIdempotencyKey = `sfe-transfer-${idempotencyKey}`;
  const { data: dispatch, error: dispatchError } = await service
    .schema("integration_control")
    .rpc("dispatch_stripe_internal_transfer_v1", {
      p_amount: Number(providerAllocation.amount_minor),
      p_currency: String(transaction.currency),
      p_idempotency_key: dispatchIdempotencyKey,
      p_transfer_group: `CT-SFE-${transaction.transaction_id}`,
    });

  if (dispatchError) return json({ ok: false, state: "HOLD", error: dispatchError.message, transaction_id: transaction.transaction_id }, 502);

  const dispatchBody = (dispatch as any)?.body ?? {};
  const httpStatus = Number((dispatch as any)?.http_status ?? 0);
  if (httpStatus < 200 || httpStatus >= 300 || dispatchBody.readback_pass !== true) {
    await service
      .from("ct_self_funding_transactions")
      .update({ state: "held", allocation_state: "hold", metadata: { ...payload.metadata, dispatch } })
      .eq("transaction_id", transaction.transaction_id);

    return json({ ok: false, state: "HOLD", reason: "provider_dispatch_or_readback_failed", dispatch }, 502);
  }

  await service
    .from("ct_self_funding_transactions")
    .update({
      state: "settled",
      allocation_state: "executed",
      settled_at: new Date().toISOString(),
      metadata: {
        ...payload.metadata,
        route_key: "sfe.stripe.crownthrive.hot.v1",
        provider_transfer_id: dispatchBody?.result?.id ?? null,
        provider_readback_pass: true,
      },
    })
    .eq("transaction_id", transaction.transaction_id);

  return json({
    ok: true,
    mode: "hot",
    production_settlement: "executed",
    transaction_id: transaction.transaction_id,
    route_key: "sfe.stripe.crownthrive.hot.v1",
    provider_transfer: dispatchBody.result,
    allocations,
    allocation_total_minor: total,
    policy: "CT-SFE-80-10-5-3-2@1.0.0",
    redundancy: [
      "sfe.paypal.crownthrive.cold.v1",
      "sfe.paypal.penta.cold.v1",
      "sfe.ledger.queue.v1",
    ],
  });
});
