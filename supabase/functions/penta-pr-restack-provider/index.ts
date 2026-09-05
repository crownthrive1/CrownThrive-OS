import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const GH = "https://api.github.com";
const REPO = "crownthrive1/CrownThrive-OS";
const [OWNER, REPO_NAME] = REPO.split("/");
const VERSION = "2.0.0";
const sb = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  { auth: { persistSession: false, autoRefreshToken: false } },
);
let ghToken: string | null = null;

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json" },
  });
}
function need(v: unknown, name: string) {
  const s = String(v ?? "").trim();
  if (!s) throw new Error(`${name}_required`);
  return s;
}
function jwtRole(req: Request) {
  const raw = req.headers.get("authorization")?.replace(/^Bearer\s+/i, "") ?? "";
  const part = raw.split(".")[1];
  if (!part) return "";
  try {
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(part.length / 4) * 4, "=");
    return String(JSON.parse(atob(b64))?.role ?? "");
  } catch {
    return "";
  }
}
async function rpc(name: string, args: Record<string, unknown> = {}) {
  const { data, error } = await sb.rpc(name, args);
  if (error) throw new Error(`${name}:${error.message}`);
  return data;
}
async function token() {
  if (ghToken) return ghToken;
  const t = await rpc("penta_pm_github_token");
  if (!t) throw new Error("vault_binding_unavailable");
  ghToken = String(t);
  return ghToken;
}
async function gh(path: string, init: RequestInit = {}) {
  const res = await fetch(GH + path, {
    ...init,
    headers: {
      authorization: `Bearer ${await token()}`,
      accept: "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "content-type": "application/json",
      "user-agent": "CrownThrive-PentaPR-Restack/2.0",
      ...(init.headers ?? {}),
    },
  });
  const text = await res.text();
  let body: any = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = { message: text.slice(0, 500) }; }
  return { ok: res.ok, status: res.status, body };
}
async function record(
  requestId: string,
  state: "RUNNING" | "HOLD" | "SUCCEEDED" | "FAILED",
  status: number | null,
  holdCode: string | null,
  successor: { number?: number; head?: string; branch?: string } = {},
  evidence: Record<string, unknown> = {},
) {
  return await rpc("penta_pr_restack_record_provider_result_v2", {
    p_request_id: requestId,
    p_state: state,
    p_provider_http_status: status,
    p_hold_code: holdCode,
    p_successor_pr_number: successor.number ?? null,
    p_successor_head_sha: successor.head ?? null,
    p_successor_branch: successor.branch ?? null,
    p_evidence: evidence,
  });
}
function hold(code: string, detail: Record<string, unknown> = {}) {
  return { ok: false, hold: true, code, ...detail };
}

async function executeRestack(requestId: string) {
  const req: any = await rpc("penta_pr_restack_request_get_v2", { p_request_id: requestId });
  if (!req) return { ok: false, status: 404, result: hold("HOLD_RESTACK_REQUEST_NOT_FOUND") };
  if (req.state === "SUCCEEDED") {
    return { ok: true, status: 200, result: { state: "SUCCEEDED_IDEMPOTENT", request: req } };
  }
  if (req.source_repo !== REPO) {
    await record(requestId, "HOLD", null, "HOLD_RESTACK_REPO_FORBIDDEN", {}, { source_repo: req.source_repo });
    return { ok: false, status: 409, result: hold("HOLD_RESTACK_REPO_FORBIDDEN") };
  }

  await record(requestId, "RUNNING", null, null, {}, { provider_operation: "draft_current_main_restack", authority_created: false });

  const main = await gh(`/repos/${REPO}/branches/main`);
  if (!main.ok) {
    await record(requestId, "HOLD", main.status, "HOLD_GITHUB_MAIN_READBACK_FAILED", {}, { provider_status: main.status });
    return { ok: false, status: 502, result: hold("HOLD_GITHUB_MAIN_READBACK_FAILED", { provider_status: main.status }) };
  }
  const mainSha = String(main.body?.commit?.sha ?? "");
  if (mainSha !== req.expected_main_sha) {
    await record(requestId, "HOLD", 200, "HOLD_CURRENT_MAIN_DRIFT", {}, { expected_main_sha: req.expected_main_sha, observed_main_sha: mainSha });
    return { ok: false, status: 409, result: hold("HOLD_CURRENT_MAIN_DRIFT", { expected_main_sha: req.expected_main_sha, observed_main_sha: mainSha }) };
  }

  const predecessor = await gh(`/repos/${REPO}/pulls/${Number(req.source_pr_number)}`);
  if (!predecessor.ok) {
    await record(requestId, "HOLD", predecessor.status, "HOLD_PREDECESSOR_READBACK_FAILED", {}, { provider_status: predecessor.status });
    return { ok: false, status: 502, result: hold("HOLD_PREDECESSOR_READBACK_FAILED") };
  }
  if (predecessor.body?.state !== "open" || predecessor.body?.merged === true) {
    await record(requestId, "HOLD", 200, "HOLD_PREDECESSOR_NOT_OPEN", {}, { state: predecessor.body?.state, merged: predecessor.body?.merged === true });
    return { ok: false, status: 409, result: hold("HOLD_PREDECESSOR_NOT_OPEN") };
  }
  const predecessorHead = String(predecessor.body?.head?.sha ?? "");
  if (predecessorHead !== req.predecessor_head_sha) {
    await record(requestId, "HOLD", 200, "HOLD_PREDECESSOR_HEAD_DRIFT", {}, { expected_head: req.predecessor_head_sha, observed_head: predecessorHead });
    return { ok: false, status: 409, result: hold("HOLD_PREDECESSOR_HEAD_DRIFT") };
  }

  const branch = `penta/restack-pr${req.source_pr_number}-current-${mainSha.slice(0, 7)}-${requestId.slice(0, 8)}`;
  const existing = await gh(`/repos/${REPO}/pulls?state=open&head=${OWNER}:${encodeURIComponent(branch)}&base=main&per_page=10`);
  if (existing.ok && Array.isArray(existing.body) && existing.body.length > 0) {
    const pr = existing.body[0];
    const readback = await gh(`/repos/${REPO}/pulls/${pr.number}`);
    const head = String(readback.body?.head?.sha ?? "");
    if (readback.ok && head && readback.body?.state === "open" && readback.body?.draft === true) {
      await record(requestId, "SUCCEEDED", readback.status, null, { number: Number(pr.number), head, branch }, {
        idempotent_existing_successor: true,
        base_ref: readback.body?.base?.ref,
        predecessor_preserved: true,
        merge_performed: false,
        authority_created: false,
      });
      return { ok: true, status: 200, result: { state: "SUCCEEDED", successor_pr_number: Number(pr.number), successor_head_sha: head, successor_branch: branch, idempotent: true } };
    }
  }

  const files = await gh(`/repos/${REPO}/pulls/${Number(req.source_pr_number)}/files?per_page=100`);
  if (!files.ok || !Array.isArray(files.body)) {
    await record(requestId, "HOLD", files.status, "HOLD_PREDECESSOR_DIFF_READBACK_FAILED", {}, { provider_status: files.status });
    return { ok: false, status: 502, result: hold("HOLD_PREDECESSOR_DIFF_READBACK_FAILED") };
  }
  if (files.body.length === 0) {
    await record(requestId, "HOLD", 200, "HOLD_PREDECESSOR_ZERO_DELTA_RECLASSIFY", {}, { changed_files: 0 });
    return { ok: false, status: 409, result: hold("HOLD_PREDECESSOR_ZERO_DELTA_RECLASSIFY") };
  }
  if (files.body.length >= 100) {
    await record(requestId, "HOLD", 200, "HOLD_RESTACK_DIFF_PAGINATION_REQUIRED", {}, { first_page_count: files.body.length });
    return { ok: false, status: 409, result: hold("HOLD_RESTACK_DIFF_PAGINATION_REQUIRED") };
  }

  const mainCommit = await gh(`/repos/${REPO}/commits/${mainSha}`);
  const headTree = await gh(`/repos/${REPO}/git/trees/${predecessorHead}?recursive=1`);
  if (!mainCommit.ok || !headTree.ok) {
    await record(requestId, "HOLD", !mainCommit.ok ? mainCommit.status : headTree.status, "HOLD_RESTACK_TREE_READBACK_FAILED");
    return { ok: false, status: 502, result: hold("HOLD_RESTACK_TREE_READBACK_FAILED") };
  }
  const baseTreeSha = String(mainCommit.body?.commit?.tree?.sha ?? "");
  const modeByPath = new Map<string, string>();
  for (const x of (headTree.body?.tree ?? [])) if (x?.path && x?.type === "blob") modeByPath.set(String(x.path), String(x.mode ?? "100644"));

  const tree = files.body.map((f: any) => ({
    path: String(f.filename),
    mode: f.status === "removed" ? "100644" : (modeByPath.get(String(f.filename)) ?? "100644"),
    type: "blob",
    sha: f.status === "removed" ? null : String(f.sha),
  }));
  const newTree = await gh(`/repos/${REPO}/git/trees`, { method: "POST", body: JSON.stringify({ base_tree: baseTreeSha, tree }) });
  if (!newTree.ok) {
    await record(requestId, "HOLD", newTree.status, "HOLD_RESTACK_TREE_CREATE_FAILED", {}, { provider_status: newTree.status, changed_files: tree.length });
    return { ok: false, status: 502, result: hold("HOLD_RESTACK_TREE_CREATE_FAILED") };
  }

  const commitMessage = `chore(pentapr): restack #${req.source_pr_number} on current main\n\nAssignment: ${requestId}\nPredecessor head: ${predecessorHead}\nBase: ${mainSha}\nAuthority created: false`;
  const commit = await gh(`/repos/${REPO}/git/commits`, {
    method: "POST",
    body: JSON.stringify({ message: commitMessage, tree: newTree.body?.sha, parents: [mainSha] }),
  });
  if (!commit.ok) {
    await record(requestId, "HOLD", commit.status, "HOLD_RESTACK_COMMIT_CREATE_FAILED", {}, { provider_status: commit.status });
    return { ok: false, status: 502, result: hold("HOLD_RESTACK_COMMIT_CREATE_FAILED") };
  }
  const successorHead = String(commit.body?.sha ?? "");

  const ref = await gh(`/repos/${REPO}/git/refs`, {
    method: "POST",
    body: JSON.stringify({ ref: `refs/heads/${branch}`, sha: successorHead }),
  });
  if (!ref.ok) {
    await record(requestId, "HOLD", ref.status, "HOLD_RESTACK_BRANCH_CREATE_FAILED", {}, { provider_status: ref.status, branch, successor_head_sha: successorHead });
    return { ok: false, status: 502, result: hold("HOLD_RESTACK_BRANCH_CREATE_FAILED") };
  }

  const title = `chore(pentapr): restack #${req.source_pr_number} on current main`;
  const body = [
    `PR-v2 successor generated by the bounded PentaPR restack provider.`,
    ``,
    `- Assignment: \`${requestId}\``,
    `- Predecessor: #${req.source_pr_number} @ \`${predecessorHead}\``,
    `- Current protected main used: \`${mainSha}\``,
    `- Successor head: \`${successorHead}\``,
    `- Changed paths overlaid from predecessor: ${tree.length}`,
    ``,
    `Predecessor branch/head/diff/history are preserved. This PR is draft and inherits no provider result, review, governance PASS, security PASS, certificate, merge authority, deployment authority, D3 authority, or rights authority from its predecessor.`,
    ``,
    `Required current-subject path remains PentaSecurity -> CHLOM -> CIE only where applicable -> independent PentaCertifier, plus all applicable exact-head provider/check/review gates. Originator self-certification is forbidden.`,
    ``,
    `No force merge, protected-main direct write, branch deletion, credential action, money movement, predecessor close, vote/quorum effect, or authority expansion is performed by this restack.`,
    ``,
    `<!-- CT-RESTACK-REQUEST:${requestId} -->`,
  ].join("\n");
  const pr = await gh(`/repos/${REPO}/pulls`, {
    method: "POST",
    body: JSON.stringify({ title, head: branch, base: "main", body, draft: true, maintainer_can_modify: true }),
  });
  if (!pr.ok) {
    await record(requestId, "HOLD", pr.status, "HOLD_RESTACK_PR_CREATE_FAILED", {}, { provider_status: pr.status, branch, successor_head_sha: successorHead });
    return { ok: false, status: 502, result: hold("HOLD_RESTACK_PR_CREATE_FAILED") };
  }

  const number = Number(pr.body?.number ?? 0);
  const readback = await gh(`/repos/${REPO}/pulls/${number}`);
  const ok = readback.ok && readback.body?.state === "open" && readback.body?.draft === true && String(readback.body?.head?.sha ?? "") === successorHead && String(readback.body?.base?.ref ?? "") === "main";
  if (!ok) {
    await record(requestId, "HOLD", readback.status, "HOLD_RESTACK_PR_READBACK_FAILED", {}, { successor_pr_number: number, branch, successor_head_sha: successorHead });
    return { ok: false, status: 502, result: hold("HOLD_RESTACK_PR_READBACK_FAILED") };
  }

  await record(requestId, "SUCCEEDED", readback.status, null, { number, head: successorHead, branch }, {
    changed_files: tree.length,
    base_main_sha: mainSha,
    predecessor_pr_number: Number(req.source_pr_number),
    predecessor_head_sha: predecessorHead,
    predecessor_preserved: true,
    draft: true,
    merge_performed: false,
    predecessor_close_performed: false,
    certification_claimed: false,
    authority_created: false,
  });
  return { ok: true, status: 200, result: { state: "SUCCEEDED", successor_pr_number: number, successor_head_sha: successorHead, successor_branch: branch, changed_files: tree.length } };
}

Deno.serve(async (req) => {
  try {
    if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);
    if (jwtRole(req) !== "service_role") return json({ error: "service_role_required" }, 403);
    const input = await req.json().catch(() => ({}));
    const op = String(input?.op ?? "probe");
    if (op === "probe") {
      const main = await gh(`/repos/${REPO}/branches/main`);
      return json({ service: "PentaPR Restack Provider", version: VERSION, bound: true, provider_ok: main.ok, provider_status: main.status, main_sha: main.body?.commit?.sha ?? null, merge_authority: false, close_authority: false, certification_authority: false, authority_created: false }, main.ok ? 200 : 502);
    }
    if (op !== "execute_restack") return json({ error: "unsupported_operation", op }, 400);
    const requestId = need(input?.request_id, "request_id");
    const result = await executeRestack(requestId);
    return json({ service: "PentaPR Restack Provider", version: VERSION, ...result.result }, result.status);
  } catch (e) {
    return json({ service: "PentaPR Restack Provider", version: VERSION, state: "FAILED", error: String((e as Error)?.message ?? e).slice(0, 1000), authority_created: false }, 500);
  }
});
