import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const CPANEL_BASE = "https://crownthrive.io:2083/execute";
const CPANEL_USERNAME_ENV = "CPANEL_UAPI_USERNAME";
const CPANEL_SECRET_NAME_ENV = "CPANEL_RUNTIME_SECRET_NAME";
const SAFE_BINDING = /^[A-Za-z0-9._:-]{1,128}$/;
const SAFE_BUILD_RUN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const MAX_PROVIDER_RESPONSE_BYTES = 1_000_000;

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
    },
  });
}

function requiredBinding(name: string): string {
  const value = (Deno.env.get(name) ?? "").trim();
  if (!SAFE_BINDING.test(value)) throw new Error(`missing_or_invalid_${name.toLowerCase()}`);
  return value;
}

function providerFieldCount(value: unknown): number {
  if (Array.isArray(value)) return value.length;
  return value == null ? 0 : 1;
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)]
    .map((item) => item.toString(16).padStart(2, "0"))
    .join("");
}

function supabaseBindings(): { url: string; serviceRoleKey: string } {
  const url = (Deno.env.get("SUPABASE_URL") ?? "").trim();
  const serviceRoleKey = (Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "").trim();
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error("supabase_binding_invalid");
  }
  if (
    parsed.protocol !== "https:" ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash ||
    !serviceRoleKey
  ) {
    throw new Error("supabase_binding_invalid");
  }
  return { url: url.replace(/\/$/, ""), serviceRoleKey };
}

async function runtimeSecret(): Promise<string> {
  const secretName = requiredBinding(CPANEL_SECRET_NAME_ENV);
  const { url, serviceRoleKey } = supabaseBindings();
  const response = await fetch(`${url}/rest/v1/rpc/get_runtime_secret`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      apikey: serviceRoleKey,
      authorization: `Bearer ${serviceRoleKey}`,
    },
    body: JSON.stringify({ secret_name: secretName }),
  });
  if (!response.ok) return "";
  const value = await response.json();
  return typeof value === "string" && value ? value : "";
}

Deno.serve(async (request) => {
  try {
    if (request.method !== "POST") return jsonResponse({ error: "POST required" }, 405);

    const payload = await request.json();
    const buildRunId = typeof payload?.build_run_id === "string"
      ? payload.build_run_id
      : "";
    if (!SAFE_BUILD_RUN.test(buildRunId)) {
      return jsonResponse({ ok: false, error: "build_run_id_invalid" }, 400);
    }

    const username = requiredBinding(CPANEL_USERNAME_ENV);
    const token = await runtimeSecret();
    if (!token) return jsonResponse({ ok: false, error: "cpanel_token_unavailable" }, 503);

    const { url: supabaseUrl, serviceRoleKey } = supabaseBindings();
    const packageResponse = await fetch(
      `${supabaseUrl}/rest/v1/ct_factory_release_packages?build_run_id=eq.${encodeURIComponent(buildRunId)}&channel=eq.production&select=release_version,sha256,status`,
      { headers: { apikey: serviceRoleKey, authorization: `Bearer ${serviceRoleKey}` } },
    );
    if (!packageResponse.ok) {
      return jsonResponse({ ok: false, error: "production_candidate_readback_failed" }, 503);
    }
    const packages = await packageResponse.json();
    const candidate = Array.isArray(packages) ? packages[0] : null;
    if (
      !candidate ||
      candidate.status !== "candidate" ||
      typeof candidate.release_version !== "string" ||
      !candidate.release_version ||
      typeof candidate.sha256 !== "string" ||
      !SHA256.test(candidate.sha256)
    ) {
      return jsonResponse({ ok: false, error: "production_candidate_required" }, 409);
    }

    const file = `crownthrive-factory-${buildRunId}.json`;
    const directory = "public_html/.well-known";
    const content = JSON.stringify({
      contract: "ct.factory.cpanel.v1",
      build_run_id: buildRunId,
      release_version: candidate.release_version,
      package_sha256: candidate.sha256,
      implemented_at: new Date().toISOString(),
    });
    const providerHeaders = {
      accept: "application/json",
      authorization: `cpanel ${username}:${token}`,
    };

    const beforeResponse = await fetch(
      `${CPANEL_BASE}/Fileman/get_file_content?dir=${encodeURIComponent(directory)}&file=${encodeURIComponent(file)}`,
      { headers: providerHeaders },
    );
    const beforeText = await beforeResponse.text();
    if (beforeText.length > MAX_PROVIDER_RESPONSE_BYTES) {
      return jsonResponse({ ok: false, error: "cpanel_response_too_large" }, 502);
    }
    const rollbackRef = beforeResponse.ok ? `sha256:${await sha256(beforeText)}` : "absent";

    const parameters = new URLSearchParams({
      dir: directory,
      file,
      content,
      from_charset: "UTF-8",
      to_charset: "UTF-8",
    });
    const writeResponse = await fetch(
      `${CPANEL_BASE}/Fileman/save_file_content?${parameters.toString()}`,
      { method: "GET", headers: providerHeaders },
    );
    const writeText = await writeResponse.text();
    if (writeText.length > MAX_PROVIDER_RESPONSE_BYTES) {
      return jsonResponse({ ok: false, error: "cpanel_response_too_large" }, 502);
    }
    let writeJson: Record<string, unknown> = {};
    try {
      writeJson = JSON.parse(writeText);
    } catch {
      // Invalid provider JSON remains a bounded, digest-only failure.
    }
    if (!writeResponse.ok || writeJson.status !== 1) {
      return jsonResponse({
        ok: false,
        error: "cpanel_write_not_certified",
        provider_status: writeResponse.status,
        provider_error_count: providerFieldCount(writeJson.errors),
        provider_message_count: providerFieldCount(writeJson.messages),
        provider_response_sha256: await sha256(writeText),
      }, 502);
    }

    const readbackResponse = await fetch(
      `${CPANEL_BASE}/Fileman/get_file_content?dir=${encodeURIComponent(directory)}&file=${encodeURIComponent(file)}`,
      { headers: providerHeaders },
    );
    const readbackText = await readbackResponse.text();
    if (readbackText.length > MAX_PROVIDER_RESPONSE_BYTES) {
      return jsonResponse({ ok: false, error: "cpanel_response_too_large" }, 502);
    }
    let readbackJson: Record<string, any> = {};
    try {
      readbackJson = JSON.parse(readbackText);
    } catch {
      // Invalid provider JSON fails exact readback below.
    }
    const returned = typeof readbackJson?.data?.content === "string"
      ? readbackJson.data.content
      : JSON.stringify(readbackJson?.data ?? {});
    const matches = readbackResponse.ok &&
      readbackJson.status === 1 &&
      returned.includes(candidate.sha256) &&
      returned.includes(buildRunId);
    if (!matches) {
      return jsonResponse({
        ok: false,
        error: "cpanel_readback_mismatch",
        provider_status: readbackResponse.status,
        provider_response_sha256: await sha256(readbackText),
      }, 502);
    }

    return jsonResponse({
      ok: true,
      adapter: "ct.adapter.cpanel.uapi.v1",
      provider_write_performed: true,
      path: `/${directory}/${file}`,
      rollback_ref: rollbackRef,
      read_after_write: true,
      readback_sha256: await sha256(returned),
    });
  } catch {
    return jsonResponse({ ok: false, error: "internal_adapter_error" }, 500);
  }
});
