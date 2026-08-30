import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const GH = "https://api.github.com";
const VERSION = "3.1.0";
const sb = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  { auth: { persistSession: false, autoRefreshToken: false } },
);
let tokenCache: string | null = null;

const need = (v: unknown, n: string) => {
  const s = String(v ?? "").trim();
  if (!s) throw new Error(`${n}_required`);
  return s;
};

async function rpc(name: string, args: Record<string, unknown> = {}) {
  const { data, error } = await sb.rpc(name, args);
  if (error) throw new Error(`${name}:${error.message}`);
  return data;
}

async function token() {
  if (tokenCache) return tokenCache;
  const value = await rpc("penta_pm_github_token");
  if (!value) throw new Error("github_token_unavailable");
  return tokenCache = String(value);
}

async function gh(repo: string, path: string, init: RequestInit = {}) {
  const response = await fetch(`${GH}/repos/${repo}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${await token()}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "CrownThrive-PentaPR-Terminal/3.1",
      ...(init.headers || {}),
    },
  });
  const text = await response.text();
  let body: any = null;
  try { body = text ? JSON.parse(text) : null; }
  catch { body = { message: text.slice(0, 500) }; }
  return { ok: response.ok, status: response.status, body };
}

async function allowed(repo: string) {
  return !!(await rpc("penta_pr_repo_allowed_v3", { p_repo: repo }));
}

async function read(repo: string, pr: number) {
  const result = await gh(repo, `/pulls/${pr}`);
  return {
    ...result,
    head: String(result.body?.head?.sha ?? ""),
    state: String(result.body?.state ?? ""),
    merged: !!result.body?.merged,
    draft: !!result.body?.draft,
  };
}

async function zeroEvidence(repo: string, pr: number, currentHead: string) {
  const z: any = await rpc("penta_pr_latest_zero_delta_v3", { p_repo: repo, p_pr_number: pr });
  if (!z?.eligible) return { eligible: false };
  if (String(z.head_sha) === currentHead) return { ...z, eligible: true, mode: "EXACT_HEAD" };

  const finding = String(z.finding_id ?? "");
  if (!finding || !/^[0-9a-f-]{36}$/i.test(finding)) return { eligible: false };
  const compare = await gh(repo, `/compare/${encodeURIComponent(String(z.head_sha))}...${encodeURIComponent(currentHead)}`);
  if (!compare.ok) return { eligible: false, mode: "COMPARE_FAILED", status: compare.status };
  const files = Array.isArray(compare.body?.files) ? compare.body.files : [];
  const allowedPath = `penta/remediations/${finding}.execution.json`;
  const safe = files.length > 0 && files.every((file: any) => String(file.filename ?? "") === allowedPath);
  return safe
    ? { ...z, eligible: true, mode: "EVIDENCE_ONLY_DESCENDANT", current_head: currentHead, changed_files: files.map((f: any) => f.filename) }
    : { eligible: false, mode: "NON_EVIDENCE_DELTA", verified_head: z.head_sha, current_head: currentHead, changed_files: files.map((f: any) => f.filename) };
}

async function recordDecision(x: any) {
  return rpc("penta_pr_record_terminal_decision_v3", {
    p_repo: x.repo,
    p_pr_number: x.pr,
    p_head_sha: x.head,
    p_classification: x.classification,
    p_action: x.action,
    p_state: x.decision_state,
    p_reason: x.reason,
    p_evidence: x.evidence ?? {},
    p_http_status: x.http_status ?? null,
    p_provider_state: x.provider_state ?? null,
    p_merged: x.merged ?? false,
    p_merge_commit_sha: x.merge_commit_sha ?? null,
    p_readback: x.readback ?? {},
  });
}

async function recordTruth(repo: string, pr: number, result: any) {
  return rpc("penta_pr_record_provider_truth_v3", {
    p_repo: repo,
    p_pr_number: pr,
    p_head_sha: result.head,
    p_state: result.state,
    p_merged: result.merged,
    p_merge_commit_sha: result.body?.merge_commit_sha ?? null,
    p_http_status: result.status,
    p_readback: {
      state: result.state,
      merged: result.merged,
      draft: result.draft,
      head_sha: result.head,
      merge_commit_sha: result.body?.merge_commit_sha ?? null,
      updated_at: result.body?.updated_at ?? null,
    },
  });
}

async function closeExact(repo: string, pr: number, expected: string, classification: string, reason: string, evidence: any = {}) {
  if (!await allowed(repo)) throw new Error("repository_not_allowed");
  if (!["VERIFIED_ZERO_DELTA", "SUPERSEDED"].includes(classification)) throw new Error("close_classification_not_allowed");
  const before = await read(repo, pr);
  if (!before.ok) throw new Error(`pr_read_failed:${before.status}`);
  if (before.head !== expected) return { ok: false, state: "DEFERRED_HEAD_MOVED", expected_head: expected, observed_head: before.head };
  if (before.state !== "open") {
    await recordTruth(repo, pr, before);
    return { ok: true, state: "ALREADY_TERMINAL", provider_state: before.state, merged: before.merged, head: before.head };
  }

  if (classification === "VERIFIED_ZERO_DELTA") {
    const z: any = await zeroEvidence(repo, pr, expected);
    if (!z?.eligible) return { ok: false, state: "DEFERRED_ZERO_DELTA_NOT_CURRENT", head: expected, verification: z };
    evidence = { ...evidence, execution_id: z.execution_id, finding_id: z.finding_id, verified_at: z.verified_at, verification_mode: z.mode, verified_head: z.head_sha, changed_files: z.changed_files ?? [] };
  }

  await recordDecision({ repo, pr, head: expected, classification, action: "CLOSE", decision_state: "DISPATCHED", reason, evidence });
  const write = await gh(repo, `/pulls/${pr}`, { method: "PATCH", body: JSON.stringify({ state: "closed" }) });
  const after = await read(repo, pr);
  const success = write.ok && after.ok && after.state === "closed" && after.head === expected;
  await recordDecision({
    repo, pr, head: expected, classification, action: "CLOSE", decision_state: success ? "SUCCEEDED" : "FAILED", reason, evidence,
    http_status: write.status, provider_state: after.state, merged: after.merged, merge_commit_sha: after.body?.merge_commit_sha ?? null,
    readback: { write_status: write.status, read_status: after.status, state: after.state, head_sha: after.head, merged: after.merged },
  });
  if (after.ok) await recordTruth(repo, pr, after);
  return { ok: success, state: success ? "CLOSED" : "FAILED", write_status: write.status, read_status: after.status, head: after.head, provider_state: after.state, merged: after.merged };
}

async function mergeExact(repo: string, pr: number, expected: string, evidence: any = {}) {
  if (!await allowed(repo)) throw new Error("repository_not_allowed");
  if (evidence?.exact_head_certified !== true) throw new Error("exact_head_certification_required");
  const before = await read(repo, pr);
  if (!before.ok) throw new Error(`pr_read_failed:${before.status}`);
  if (before.head !== expected) return { ok: false, state: "DEFERRED_HEAD_MOVED", expected_head: expected, observed_head: before.head };
  if (before.draft) return { ok: false, state: "DEFERRED_DRAFT" };
  if (before.state !== "open") {
    await recordTruth(repo, pr, before);
    return { ok: true, state: "ALREADY_TERMINAL", provider_state: before.state, merged: before.merged };
  }

  await recordDecision({ repo, pr, head: expected, classification: "MERGE_READY", action: "MERGE", decision_state: "DISPATCHED", reason: "exact-head governed merge", evidence });
  const write = await gh(repo, `/pulls/${pr}/merge`, { method: "PUT", body: JSON.stringify({ sha: expected, merge_method: "squash" }) });
  const after = await read(repo, pr);
  const success = write.ok && !!write.body?.merged && after.ok && after.merged && after.head === expected;
  await recordDecision({
    repo, pr, head: expected, classification: "MERGE_READY", action: "MERGE", decision_state: success ? "SUCCEEDED" : "FAILED", reason: "exact-head governed merge", evidence,
    http_status: write.status, provider_state: after.state, merged: after.merged, merge_commit_sha: write.body?.sha ?? after.body?.merge_commit_sha ?? null,
    readback: { write_status: write.status, write_message: write.body?.message ?? null, read_status: after.status, state: after.state, head_sha: after.head, merged: after.merged },
  });
  if (after.ok) await recordTruth(repo, pr, after);
  return { ok: success, state: success ? "MERGED" : "FAILED", write_status: write.status, read_status: after.status, head: after.head, merged: after.merged, message: write.body?.message ?? null };
}

async function reconcile(repo = "crownthrive1/CrownThrive-OS", limit = 100) {
  if (!await allowed(repo)) throw new Error("repository_not_allowed");
  const result = await gh(repo, `/pulls?state=open&per_page=${Math.min(Math.max(limit, 1), 100)}&sort=updated&direction=asc`);
  if (!result.ok) throw new Error(`open_pr_list_failed:${result.status}`);
  const terminal: any[] = [];
  for (const pr of (Array.isArray(result.body) ? result.body : [])) {
    const number = Number(pr.number);
    const head = String(pr.head?.sha ?? "");
    if (!number || !head) continue;
    const z: any = await zeroEvidence(repo, number, head);
    if (z?.eligible) terminal.push({ pr: number, ...await closeExact(repo, number, head, "VERIFIED_ZERO_DELTA", "PentaSELF verified zero-code-delta; terminal close without merge", { source: "PentaPR terminal reconcile v3.1", verification_mode: z.mode }) });
  }
  return { ok: true, service: "ct.penta-pr-terminal-reconciliation.v3", version: VERSION, repo, examined: Array.isArray(result.body) ? result.body.length : 0, terminal_actions: terminal.length, results: terminal };
}

Deno.serve(async (req) => {
  try {
    if (req.method !== "POST") return Response.json({ error: "method_not_allowed" }, { status: 405 });
    const input = await req.json().catch(() => ({}));
    const op = String(input.op ?? "reconcile");
    if (op === "probe") return Response.json({ ok: true, service: "ct.penta-pr-terminal-reconciliation.v3", version: VERSION });
    if (op === "read") {
      const repo = need(input.repo, "repo");
      if (!await allowed(repo)) throw new Error("repository_not_allowed");
      return Response.json(await read(repo, Number(input.pr_number)));
    }
    if (op === "reconcile") return Response.json(await reconcile(String(input.repo ?? "crownthrive1/CrownThrive-OS"), Number(input.limit ?? 100)));
    if (op === "close_exact") return Response.json(await closeExact(need(input.repo, "repo"), Number(input.pr_number), need(input.expected_head_sha, "expected_head_sha"), need(input.classification, "classification"), String(input.reason ?? "governed terminal close"), input.evidence ?? {}));
    if (op === "merge_exact") return Response.json(await mergeExact(need(input.repo, "repo"), Number(input.pr_number), need(input.expected_head_sha, "expected_head_sha"), input.evidence ?? {}));
    return Response.json({ error: "unsupported_operation", op }, { status: 400 });
  } catch (error) {
    return Response.json({ ok: false, service: "ct.penta-pr-terminal-reconciliation.v3", version: VERSION, error: String((error as Error)?.message ?? error) }, { status: 500 });
  }
});
