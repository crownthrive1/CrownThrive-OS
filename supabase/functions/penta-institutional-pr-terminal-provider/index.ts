import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const GH = Deno.env.get("PENTA_PR_GITHUB_TOKEN") ?? Deno.env.get("PENTAPR_GITHUB_TOKEN") ?? Deno.env.get("PENTA_PM_GITHUB_TOKEN") ?? Deno.env.get("GH_TOKEN") ?? Deno.env.get("GITHUB_TOKEN") ?? "";
const HEADERS = {"access-control-allow-origin":"*","access-control-allow-headers":"content-type","access-control-allow-methods":"POST,OPTIONS","cache-control":"no-store","content-type":"application/json"};
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: HEADERS });
const sha256 = async (value: unknown) => {
  const bytes = new TextEncoder().encode(typeof value === "string" ? value : JSON.stringify(value));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map(v => v.toString(16).padStart(2, "0")).join("");
};
const providerHeaders = () => {
  const h: Record<string,string> = { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "CrownThrive-PentaPR/1.0" };
  if (GH) h.Authorization = `Bearer ${GH}`;
  return h;
};
async function github(path: string, init: RequestInit = {}) {
  const r = await fetch(`https://api.github.com${path}`, { ...init, headers: { ...providerHeaders(), ...(init.headers ?? {}) } });
  const raw = await r.text();
  let body: any = null;
  try { body = raw ? JSON.parse(raw) : null; } catch { body = { message: "NON_JSON" }; }
  return { status: r.status, ok: r.ok, raw, body };
}

Deno.serve(async req => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: HEADERS });
  if (req.method !== "POST") return response({ state: "METHOD_NOT_ALLOWED" }, 405);
  if (!URL || !SERVICE) return response({ state: "HOLD", reason: "SUPABASE_RUNTIME_IDENTITY_UNAVAILABLE" }, 503);
  let input: any = {};
  try { input = await req.json(); } catch { return response({ state: "INVALID_JSON" }, 400); }
  if (!input.action_id || !input.wake_token) return response({ state: "HOLD", reason: "ONE_TIME_WAKE_REQUIRED" }, 401);

  const sb = createClient(URL, SERVICE, { auth: { persistSession: false, autoRefreshToken: false } });

  // The institutional change functions are intentionally owned by the
  // integration_control schema. Supabase RPC defaults to public; using the
  // default schema here caused the production provider to HOLD with
  // "Could not find public.penta_pr_closeout_claim_v1" even though the
  // canonical SECURITY DEFINER function existed and the action was queued.
  // Bind the RPC client to the owning schema rather than adding duplicate
  // public wrappers or widening function ACLs.
  const institutional = sb.schema("integration_control");
  const claim = await institutional.rpc("penta_pr_closeout_claim_v1", {
    p_action_id: input.action_id,
    p_wake_token: input.wake_token,
    p_worker_id: `penta-pr:${crypto.randomUUID()}`,
  });
  if (claim.error) return response({ state: "HOLD", reason: "CLAIM_REJECTED", detail: claim.error.message }, 409);
  const action: any = claim.data;
  if (action?.state === "completed") return response({ state: "completed", deduped: true });
  if (!action?.repository || !action?.action_kind) return response({ state: "HOLD", reason: "CLAIM_INCOMPLETE" }, 409);
  if (action.repository !== "crownthrive1/CrownThrive-OS") return response({ state: "HOLD", reason: "REPOSITORY_NOT_ALLOWLISTED" }, 403);

  const [owner, repo] = action.repository.split("/");
  let pr = Number(action.pr_number || 0);
  let pull: any = null;
  let status = 0;
  let raw = "";
  const record = (args: Record<string,unknown>) => institutional.rpc("penta_pr_closeout_result_v1", args);

  try {
    if (!pr) {
      if (!action.source_branch) throw new Error("PR_NUMBER_OR_SOURCE_BRANCH_REQUIRED");
      const list = await github(`/repos/${owner}/${repo}/pulls?state=all&head=${encodeURIComponent(`${owner}:${action.source_branch}`)}&per_page=20`);
      status = list.status; raw = list.raw;
      if (!list.ok || !Array.isArray(list.body)) throw new Error("PR_LOOKUP_FAILED");
      const hit = list.body.find((x: any) => x?.head?.ref === action.source_branch);
      if (!hit) throw new Error("PR_NOT_FOUND");
      pr = Number(hit.number);
    }

    const observed = await github(`/repos/${owner}/${repo}/pulls/${pr}`);
    status = observed.status; raw = observed.raw;
    if (!observed.ok || !observed.body?.head?.sha) throw new Error("PR_NOT_FOUND");
    pull = observed.body;

    if (action.action_kind === "observe") {
      const packet = {
        number: pr,
        state: pull.state,
        draft: Boolean(pull.draft),
        merged: Boolean(pull.merged),
        mergeable: pull.mergeable,
        mergeable_state: pull.mergeable_state,
        base_ref: pull.base?.ref,
        base_sha: pull.base?.sha,
        head_ref: pull.head?.ref,
        head_sha: pull.head?.sha,
        updated_at: pull.updated_at,
      };
      const result = await record({
        p_action_id: action.action_id,
        p_success: true,
        p_http_status: observed.status,
        p_provider_state: pull.state,
        p_object_ref: pull.html_url,
        p_request_sha256: await sha256({ action: "observe", repository: action.repository, source_branch: action.source_branch, pr }),
        p_response_sha256: await sha256(packet),
        p_readback_pass: true,
        p_receipt: { ...packet, authority_expansion: false, provider_write: false },
        p_error_code: null,
        p_pr_number: pr,
        p_base_ref: pull.base?.ref ?? null,
        p_head_sha: pull.head.sha,
        p_source_branch: pull.head?.ref ?? action.source_branch ?? null,
      });
      if (result.error) throw new Error(`OBSERVATION_RECORD_FAILED:${result.error.message}`);
      return response({ state: "observed", pr_number: pr, head_sha: pull.head.sha });
    }

    if (!GH) throw new Error("MISSING_GITHUB_PROVIDER_CREDENTIAL");
    if (!action.expected_head_sha || pull.head.sha !== action.expected_head_sha) throw new Error("EXACT_HEAD_MISMATCH");
    if (pull.state !== "open") throw new Error("PR_NOT_OPEN");

    let mutation: any;
    if (action.action_kind === "merge") {
      if (pull.draft) throw new Error("PR_DRAFT");
      mutation = await github(`/repos/${owner}/${repo}/pulls/${pr}/merge`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          sha: action.expected_head_sha,
          merge_method: "squash",
          commit_title: `Penta institutional change closeout (#${pr})`,
          commit_message: "Exact-head governed merge after active independent certification, three-DAIL completion, PentaDocs and three-way Drive readback.",
        }),
      });
    } else {
      mutation = await github(`/repos/${owner}/${repo}/pulls/${pr}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ state: "closed" }),
      });
    }

    const readback = await github(`/repos/${owner}/${repo}/pulls/${pr}`);
    const pass = action.action_kind === "merge"
      ? Boolean(readback.body?.merged_at) && readback.body?.state === "closed"
      : readback.body?.state === "closed";
    const packet = {
      mutation_status: mutation.status,
      mutation_ok: mutation.ok,
      mutation_message: mutation.body?.message ?? null,
      merge_sha: mutation.body?.sha ?? readback.body?.merge_commit_sha ?? null,
      readback_status: readback.status,
      readback_state: readback.body?.state ?? null,
      readback_merged_at: readback.body?.merged_at ?? null,
      readback_head_sha: readback.body?.head?.sha ?? null,
      readback_pass: pass,
    };
    const success = mutation.ok && readback.ok && pass;
    const result = await record({
      p_action_id: action.action_id,
      p_success: success,
      p_http_status: mutation.status,
      p_provider_state: readback.body?.state ?? "unknown",
      p_object_ref: readback.body?.html_url ?? pull.html_url,
      p_request_sha256: await sha256({ action: action.action_kind, repository: action.repository, pr, expected_head_sha: action.expected_head_sha }),
      p_response_sha256: await sha256(packet),
      p_readback_pass: pass,
      p_receipt: { ...packet, authority_expansion: false, credential_exposed: false },
      p_error_code: success ? null : (mutation.status === 409 ? "EXACT_HEAD_OR_MERGE_CONFLICT" : "PROVIDER_TERMINALIZATION_FAILED"),
      p_pr_number: pr,
      p_base_ref: readback.body?.base?.ref ?? pull.base?.ref ?? null,
      p_head_sha: readback.body?.head?.sha ?? pull.head.sha,
      p_source_branch: readback.body?.head?.ref ?? pull.head?.ref ?? null,
    });
    if (result.error) throw new Error(`PROVIDER_RESULT_RECORD_FAILED:${result.error.message}`);
    return response({ state: success ? "completed" : "HOLD", action: action.action_kind, pr_number: pr, readback_pass: pass }, success ? 200 : 409);
  } catch (error) {
    const code = (error instanceof Error ? error.message : "UNCLASSIFIED_PROVIDER_ERROR").slice(0, 200);
    await record({
      p_action_id: action.action_id,
      p_success: false,
      p_http_status: status,
      p_provider_state: pull?.state ?? "hold",
      p_object_ref: pull?.html_url ?? action.repository,
      p_request_sha256: await sha256({ action: action.action_kind, repository: action.repository, source_branch: action.source_branch, pr, expected_head_sha: action.expected_head_sha }),
      p_response_sha256: await sha256({ error_code: code, provider_http_status: status, response_sha256: await sha256(raw) }),
      p_readback_pass: false,
      p_receipt: { error_code: code, authority_expansion: false, credential_exposed: false },
      p_error_code: code,
      p_pr_number: pr || null,
      p_base_ref: pull?.base?.ref ?? null,
      p_head_sha: pull?.head?.sha ?? null,
      p_source_branch: pull?.head?.ref ?? action.source_branch ?? null,
    });
    return response({ state: "HOLD", reason: code }, 409);
  }
});
