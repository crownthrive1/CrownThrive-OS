export type Disposition =
  | "PRESERVE_HOLD"
  | "CLOSE_REPRESENTED"
  | "MERGE_CANDIDATE"
  | "REPAIR_REQUIRED"
  | "RESTACK_REQUIRED"
  | "OBSERVE";

export interface PullRequestEvidence {
  number: number;
  title: string;
  body?: string | null;
  draft: boolean;
  mergeable: boolean | null;
  behindBy: number;
  aheadBy: number;
  checks: Array<{ name: string; conclusion: string | null; status?: string | null }>;
}

export interface ConvergenceDecision {
  pr: number;
  disposition: Disposition;
  reasons: string[];
  mutationAllowed: boolean;
}

const HOLD_MARKERS = [
  "draft/hold",
  "draft / hold",
  "hold —",
  "hold -",
  "merge_authorized: false",
  "merge authorized: false",
  "not approved",
  "independent review",
  "must not merge",
];

const success = (v: string | null | undefined) =>
  ["success", "neutral", "skipped"].includes(String(v ?? "").toLowerCase());

export function decidePullRequest(e: PullRequestEvidence): ConvergenceDecision {
  const text = `${e.title}\n${e.body ?? ""}`.toLowerCase();
  const reasons: string[] = [];
  const hold = e.draft || HOLD_MARKERS.some((marker) => text.includes(marker));

  if (hold) {
    if (e.draft) reasons.push("draft");
    reasons.push("explicit governance/HOLD marker");
    return { pr: e.number, disposition: "PRESERVE_HOLD", reasons, mutationAllowed: false };
  }

  if (e.aheadBy === 0) {
    return {
      pr: e.number,
      disposition: "CLOSE_REPRESENTED",
      reasons: ["head contributes no unique commits relative to current main"],
      mutationAllowed: true,
    };
  }

  const failed = e.checks.filter((c) => c.conclusion && !success(c.conclusion));
  const governed = e.checks.find((c) => c.name.toLowerCase().includes("governed merge gate"));

  if (failed.length > 0) {
    return {
      pr: e.number,
      disposition: "REPAIR_REQUIRED",
      reasons: [`${failed.length} non-passing exact-head check(s)`],
      mutationAllowed: false,
    };
  }

  if (e.behindBy > 0) {
    return {
      pr: e.number,
      disposition: "RESTACK_REQUIRED",
      reasons: [`head is ${e.behindBy} commit(s) behind current main`],
      mutationAllowed: false,
    };
  }

  if (e.mergeable === true && governed && success(governed.conclusion)) {
    return {
      pr: e.number,
      disposition: "MERGE_CANDIDATE",
      reasons: ["mergeable", "current with main", "Governed Merge Gate passed on exact head"],
      mutationAllowed: true,
    };
  }

  return {
    pr: e.number,
    disposition: "OBSERVE",
    reasons: ["insufficient evidence for destructive mutation or governed merge"],
    mutationAllowed: false,
  };
}

export interface ComponentNode {
  key: string;
  contract: string;
  state: string;
  dependencies?: string[];
}

export interface Gap {
  component: string;
  kind: "MISSING_IMPLEMENTATION" | "MISSING_CONTRACT" | "MISSING_BINDING" | "STALE";
  severity: "D0" | "D1" | "D2";
}

/**
 * Deterministic gap planner used by PentaVergence.
 * It never promotes a missing capability to PASS; it emits bounded build/repair work.
 */
export function planComponentGaps(nodes: ComponentNode[]): Gap[] {
  const keys = new Set(nodes.map((n) => n.key));
  const gaps: Gap[] = [];
  for (const node of nodes) {
    if (!node.contract) gaps.push({ component: node.key, kind: "MISSING_CONTRACT", severity: "D1" });
    if (["missing", "planned", "unbound"].includes(node.state)) {
      gaps.push({ component: node.key, kind: "MISSING_IMPLEMENTATION", severity: "D1" });
    }
    for (const dep of node.dependencies ?? []) {
      if (!keys.has(dep)) gaps.push({ component: node.key, kind: "MISSING_BINDING", severity: "D1" });
    }
  }
  return gaps.sort((a, b) => `${a.component}:${a.kind}`.localeCompare(`${b.component}:${b.kind}`));
}
