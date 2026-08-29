import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import postgres from "npm:postgres@3.4.3";

const DB_URL = Deno.env.get("SUPABASE_DB_URL") ?? "";
const VERSION = "4.0.1";
const MAX_PAGES = 100;
let client: ReturnType<typeof postgres> | null = null;

function db() {
  if (!DB_URL) throw new Error("database_unavailable");
  client ??= postgres(DB_URL, { max: 2, idle_timeout: 10, prepare: false });
  return client;
}

function reply(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
    },
  });
}

async function vault(name: string): Promise<string> {
  const sql = db();
  const rows = await sql<Array<{ value: string }>>`
    select decrypted_secret as value
    from vault.decrypted_secrets
    where name=${name}
    limit 1
  `;
  return rows[0]?.value ?? "";
}

async function authorized(request: Request): Promise<boolean> {
  const expected = await vault("stripe_production_control_gateway_secret_v1");
  const supplied = request.headers.get("x-ct-stripe-control-secret") ?? "";
  return expected.length > 20 && supplied === expected;
}

function safeMetadata(input: unknown): Record<string, string> {
  const output: Record<string, string> = {};
  if (!input || typeof input !== "object" || Array.isArray(input)) return output;
  for (const [key, value] of Object.entries(input as Record<string, unknown>)) {
    if (/secret|token|password|credential|api[_-]?key|client[_-]?secret/i.test(key)) continue;
    const text = String(value ?? "");
    if (key.length <= 80 && text.length <= 500) output[key] = text;
  }
  return output;
}

async function sha256(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return [...digest].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function stripeGet(path: string, key: string): Promise<any> {
  const response = await fetch(`https://api.stripe.com${path}`, {
    headers: {
      authorization: `Bearer ${key}`,
      accept: "application/json",
      "user-agent": "CrownThrive-Stripe-Payment-Link-Sync/4.0.1",
    },
    signal: AbortSignal.timeout(30_000),
  });
  const text = await response.text();
  let data: any = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error("stripe_invalid_json");
  }
  if (response.status === 429) {
    throw new Error(`stripe_rate_limited:retry_after=${response.headers.get("retry-after") ?? "unknown"}`);
  }
  if (!response.ok) {
    const parameter = data?.error?.param == null ? "" : `:param=${String(data.error.param)}`;
    const code = data?.error?.code == null ? "" : `:code=${String(data.error.code)}`;
    throw new Error(`stripe_http_${response.status}:${String(data?.error?.type ?? "provider_error")}${parameter}${code}`);
  }
  return data;
}

Deno.serve(async (request: Request) => {
  let runId = "";
  try {
    if (request.method === "GET") {
      return reply(200, {
        service: "stripe-payment-link-sync-v4",
        version: VERSION,
        mode: "provider_read_only",
        payment_link_mutation: false,
        product_mutation: false,
        price_mutation: false,
        money_movement: false,
        raw_secret_export: false,
      });
    }
    if (request.method !== "POST") return reply(405, { error: "POST_required" });
    if (!(await authorized(request))) return reply(403, { error: "internal_authorization_required" });

    const sql = db();
    const service = await sql<Array<{ account_id: string }>>`
      select metadata->>'account_id' as account_id
      from integration_control.services
      where service_id='stripe'
      limit 1
    `;
    const accountId = service[0]?.account_id ?? "";
    if (!/^acct_[A-Za-z0-9]+$/.test(accountId)) throw new Error("stripe_platform_account_missing");

    const key = await vault("stripe_connect_live_secret_key_v1");
    if (!key.startsWith("sk_live_")) throw new Error("stripe_live_secret_unavailable");

    const runRows = await sql<Array<{ run_id: string }>>`
      insert into integration_control.stripe_payment_link_sync_runs_v4(
        provider_account_id,state,evidence
      ) values(
        ${accountId},'running',${sql.json({
          service: "stripe-payment-link-sync-v4",
          version: VERSION,
          mode: "provider_read_only",
          payment_link_mutation: false,
          money_movement: false,
        })}
      ) returning run_id::text
    `;
    runId = runRows[0]?.run_id ?? "";
    if (!runId) throw new Error("payment_link_sync_run_not_created");

    const observed: Array<{ id: string; active: boolean; hash: string }> = [];
    let startingAfter = "";
    let pages = 0;

    while (true) {
      pages += 1;
      if (pages > MAX_PAGES) throw new Error("payment_link_page_limit_exceeded");
      const parameters = new URLSearchParams({ limit: "100" });
      if (startingAfter) parameters.set("starting_after", startingAfter);
      const page = await stripeGet(`/v1/payment_links?${parameters.toString()}`, key);
      if (!Array.isArray(page.data)) throw new Error("stripe_payment_links_shape_invalid");

      for (const link of page.data) {
        const paymentLinkId = String(link?.id ?? "");
        const url = String(link?.url ?? "");
        if (!/^plink_[A-Za-z0-9]+$/.test(paymentLinkId) || !url.startsWith("https://")) continue;

        const lineParameters = new URLSearchParams({ limit: "100" });
        lineParameters.append("expand[]", "data.price.product");
        const lineItems = await stripeGet(
          `/v1/payment_links/${encodeURIComponent(paymentLinkId)}/line_items?${lineParameters.toString()}`,
          key,
        );
        const lineItemData = Array.isArray(lineItems?.data) ? lineItems.data : [];
        const primary = lineItemData[0] ?? {};
        const price = primary?.price ?? {};
        const product = price?.product && typeof price.product === "object" ? price.product : null;
        const productId = typeof price?.product === "string" ? price.product : product?.id ?? null;
        const priceId = typeof price?.id === "string" ? price.id : null;
        const billingMode = price?.type === "recurring" ? "recurring" : "one_time";
        const recurringInterval = price?.recurring?.interval == null ? null : String(price.recurring.interval);
        const safeLineItems = lineItemData.map((item: any) => ({
          price_id: typeof item?.price?.id === "string" ? item.price.id : null,
          product_id: typeof item?.price?.product === "string"
            ? item.price.product
            : item?.price?.product?.id ?? null,
          currency: item?.price?.currency == null ? null : String(item.price.currency),
          unit_amount: Number.isFinite(Number(item?.price?.unit_amount)) ? Number(item.price.unit_amount) : null,
          quantity: Number.isFinite(Number(item?.quantity)) ? Number(item.quantity) : null,
          recurring_interval: item?.price?.recurring?.interval == null
            ? null
            : String(item.price.recurring.interval),
        }));
        const safeObject = {
          id: paymentLinkId,
          url,
          active: link?.active === true,
          product_id: productId,
          price_id: priceId,
          product_name: product?.name == null ? null : String(product.name),
          product_description: product?.description == null ? null : String(product.description),
          currency: price?.currency == null ? null : String(price.currency),
          unit_amount: Number.isFinite(Number(price?.unit_amount)) ? Number(price.unit_amount) : null,
          billing_mode: billingMode,
          recurring_interval: recurringInterval,
          quantity: Number.isFinite(Number(primary?.quantity)) ? Number(primary.quantity) : null,
          after_completion_type: link?.after_completion?.type == null
            ? null
            : String(link.after_completion.type),
          after_completion_redirect_url: link?.after_completion?.redirect?.url == null
            ? null
            : String(link.after_completion.redirect.url),
          allow_promotion_codes: link?.allow_promotion_codes == null
            ? null
            : link.allow_promotion_codes === true,
          customer_creation: link?.customer_creation == null ? null : String(link.customer_creation),
          submit_type: link?.submit_type == null ? null : String(link.submit_type),
          collect_custom_fields: Array.isArray(link?.custom_fields) && link.custom_fields.length > 0,
          custom_field_count: Array.isArray(link?.custom_fields) ? link.custom_fields.length : 0,
          payment_method_collection: link?.payment_method_collection == null
            ? null
            : String(link.payment_method_collection),
          provider_created_at: Number.isFinite(Number(link?.created))
            ? new Date(Number(link.created) * 1000)
            : null,
          metadata: {
            ...safeMetadata(link?.metadata),
            product_metadata: safeMetadata(product?.metadata),
            line_item_count: String(safeLineItems.length),
            catalog_source: "stripe_api",
            sync_run_id: runId,
          },
        };
        const objectHash = await sha256(safeObject);
        const lineItemsHash = await sha256(safeLineItems);

        await sql`
          insert into integration_control.stripe_payment_link_inventory_v4(
            payment_link_id,provider_account_id,url,active,product_id,price_id,
            product_name,product_description,currency,unit_amount,billing_mode,
            recurring_interval,quantity,after_completion_type,after_completion_redirect_url,
            allow_promotion_codes,customer_creation,submit_type,collect_custom_fields,
            custom_field_count,payment_method_collection,provider_created_at,
            provider_object_sha256,provider_line_items_sha256,metadata,run_id,
            observed_at,updated_at
          ) values(
            ${paymentLinkId},${accountId},${url},${safeObject.active},${productId},${priceId},
            ${safeObject.product_name},${safeObject.product_description},${safeObject.currency},
            ${safeObject.unit_amount},${billingMode},${recurringInterval},${safeObject.quantity},
            ${safeObject.after_completion_type},${safeObject.after_completion_redirect_url},
            ${safeObject.allow_promotion_codes},${safeObject.customer_creation},${safeObject.submit_type},
            ${safeObject.collect_custom_fields},${safeObject.custom_field_count},
            ${safeObject.payment_method_collection},${safeObject.provider_created_at},
            ${objectHash},${lineItemsHash},${sql.json({
              ...safeObject.metadata,
              line_items: safeLineItems,
            })},${runId}::uuid,now(),now()
          )
          on conflict(payment_link_id) do update set
            provider_account_id=excluded.provider_account_id,
            url=excluded.url,
            active=excluded.active,
            product_id=excluded.product_id,
            price_id=excluded.price_id,
            product_name=excluded.product_name,
            product_description=excluded.product_description,
            currency=excluded.currency,
            unit_amount=excluded.unit_amount,
            billing_mode=excluded.billing_mode,
            recurring_interval=excluded.recurring_interval,
            quantity=excluded.quantity,
            after_completion_type=excluded.after_completion_type,
            after_completion_redirect_url=excluded.after_completion_redirect_url,
            allow_promotion_codes=excluded.allow_promotion_codes,
            customer_creation=excluded.customer_creation,
            submit_type=excluded.submit_type,
            collect_custom_fields=excluded.collect_custom_fields,
            custom_field_count=excluded.custom_field_count,
            payment_method_collection=excluded.payment_method_collection,
            provider_created_at=excluded.provider_created_at,
            provider_object_sha256=excluded.provider_object_sha256,
            provider_line_items_sha256=excluded.provider_line_items_sha256,
            metadata=excluded.metadata,
            run_id=excluded.run_id,
            observed_at=excluded.observed_at,
            updated_at=excluded.updated_at
        `;
        observed.push({ id: paymentLinkId, active: safeObject.active, hash: objectHash });
      }

      if (!page.has_more || page.data.length === 0) break;
      startingAfter = String(page.data[page.data.length - 1]?.id ?? "");
      if (!startingAfter) throw new Error("stripe_payment_link_cursor_missing");
    }

    observed.sort((a, b) => a.id.localeCompare(b.id));
    const payloadHash = await sha256(observed);
    const activeCount = observed.filter((item) => item.active).length;

    await sql`
      update integration_control.stripe_payment_link_inventory_v4
      set active=false,updated_at=now(),
          metadata=metadata || ${sql.json({
            state_change: "not_observed_in_complete_sync",
            sync_run_id: runId,
          })}
      where provider_account_id=${accountId}
        and run_id is distinct from ${runId}::uuid
        and observed_at < (select started_at from integration_control.stripe_payment_link_sync_runs_v4 where run_id=${runId}::uuid)
    `;

    const reconciliation = await sql<Array<{ result: any }>>`
      select integration_control.locticians_digital_product_stripe_snapshot_reconcile_v1() as result
    `;
    const reconcileResult = reconciliation[0]?.result ?? {};

    await sql`
      update integration_control.stripe_payment_link_sync_runs_v4
      set state='complete',pages=${pages},records_observed=${observed.length},
          active_records=${activeCount},payload_sha256=${payloadHash},completed_at=now(),
          evidence=evidence || ${sql.json({
            reconciliation: reconcileResult,
            payment_link_mutation: false,
            product_mutation: false,
            price_mutation: false,
            money_movement: false,
            raw_secret_export: false,
          })}
      where run_id=${runId}::uuid
    `;

    return reply(200, {
      service: "stripe-payment-link-sync-v4",
      version: VERSION,
      run_id: runId,
      state: "complete",
      pages,
      records_observed: observed.length,
      active_records: activeCount,
      payload_sha256: payloadHash,
      reconciliation: reconcileResult,
      payment_link_mutation: false,
      product_mutation: false,
      price_mutation: false,
      money_movement: false,
      raw_secret_export: false,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown_error";
    if (runId) {
      try {
        const sql = db();
        await sql`
          update integration_control.stripe_payment_link_sync_runs_v4
          set state=case when records_observed>0 then 'partial' else 'failed' end,
              error_code='sync_failed',error_message=${message.slice(0, 1000)},completed_at=now(),
              evidence=evidence || ${sql.json({
                payment_link_mutation: false,
                product_mutation: false,
                price_mutation: false,
                money_movement: false,
                raw_secret_export: false,
              })}
          where run_id=${runId}::uuid and state='running'
        `;
      } catch {
        // Preserve the original provider error.
      }
    }
    return reply(500, {
      service: "stripe-payment-link-sync-v4",
      version: VERSION,
      error: "payment_link_sync_failed",
      detail: message,
      run_id: runId || null,
      payment_link_mutation: false,
      product_mutation: false,
      price_mutation: false,
      money_movement: false,
      raw_secret_export: false,
    });
  }
});
