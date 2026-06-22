/**
 * Typed API client for the evaluation service (via Next.js BFF proxies).
 * All paths are relative to /api/eval — never calls the eval_service directly.
 */

import type {
  EvalResult,
  EvalSummary,
  EvalScenario,
  TrendResponse,
  CompareResult,
  FrameworkMetrics,
} from "@/types/eval";

const BASE = "/api/eval";
const EVAL_SERVICE_BASE = process.env.NEXT_PUBLIC_EVAL_SERVICE_URL ?? "http://localhost:8000";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`[EvalAPI] ${res.status} ${path}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Scenarios ─────────────────────────────────────────────────────────────────

export async function fetchScenarios(params?: {
  category?: string;
  role?:     string;
  language?: string;
}): Promise<EvalScenario[]> {
  const qs = params ? "?" + new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v != null)) as Record<string, string>
  ) : "";
  return req<EvalScenario[]>(`/scenarios${qs}`);
}

// ── Run scenario end-to-end ───────────────────────────────────────────────────

export async function runScenario(scenarioId: string): Promise<EvalResult> {
  return req<EvalResult>(`/run/${scenarioId}`, { method: "POST" });
}

// ── Manual evaluation ─────────────────────────────────────────────────────────

export interface ManualEvalPayload {
  user_message:        string;
  agent_response:      string;
  reference_response?: string;
  language?:           string;
  role?:               string;
  include_rouge?:      boolean;
  include_bleu?:       boolean;
}

export async function runManualEval(payload: ManualEvalPayload): Promise<EvalResult> {
  return req<EvalResult>("/evaluate", {
    method: "POST",
    body:   JSON.stringify({
      ...payload,
      include_bert_score:       true,
      include_rouge:            payload.include_rouge ?? true,
      include_bleu:             payload.include_bleu  ?? false,
      include_em:               true,
      include_esm:              true,
      include_answer_metrics:   true,
      include_context_precision:false,
    }),
  });
}

// ── History ───────────────────────────────────────────────────────────────────

export async function fetchHistory(limit = 100): Promise<EvalSummary[]> {
  return req<EvalSummary[]>(`/results/history?limit=${limit}`);
}

export async function fetchResults(params?: {
  limit?:       number;
  skip?:        number;
  scenario_id?: string;
  role?:        string;
  language?:    string;
}): Promise<EvalSummary[]> {
  const qs = params ? "?" + new URLSearchParams(
    Object.fromEntries(
      Object.entries(params)
        .filter(([, v]) => v != null)
        .map(([k, v]) => [k, String(v)])
    )
  ) : "";
  return req<EvalSummary[]>(`/results${qs}`);
}

export async function fetchResult(id: string): Promise<EvalResult> {
  return req<EvalResult>(`/results/${id}`);
}

// ── Trends ────────────────────────────────────────────────────────────────────

export async function fetchTrends(limit = 200, scenarioId?: string): Promise<TrendResponse> {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (scenarioId) qs.set("scenario_id", scenarioId);
  return req<TrendResponse>(`/results/trends?${qs}`);
}

export async function fetchFrameworkResults(limit = 200): Promise<FrameworkMetrics> {
  const res = await fetch(`${EVAL_SERVICE_BASE}/results/framework?limit=${limit}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`[EvalAPI] ${res.status} /results/framework: ${text}`);
  }
  return res.json() as Promise<FrameworkMetrics>;
}

// ── Compare ───────────────────────────────────────────────────────────────────

export async function compareResults(idA: string, idB: string): Promise<CompareResult> {
  return req<CompareResult>("/results/compare", {
    method: "POST",
    body:   JSON.stringify({ id_a: idA, id_b: idB }),
  });
}

// ── Delete ────────────────────────────────────────────────────────────────────

export async function deleteResult(id: string): Promise<void> {
  await req<{ deleted: string }>(`/results/${id}`, { method: "DELETE" });
}

// ── Export helpers (direct fetch, streaming) ──────────────────────────────────

export function exportCsvUrl(limit = 200, scenarioId?: string): string {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (scenarioId) qs.set("scenario_id", scenarioId);
  return `${BASE}/results/export/csv?${qs}`;
}

export function exportJsonUrl(limit = 200, scenarioId?: string): string {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (scenarioId) qs.set("scenario_id", scenarioId);
  return `${BASE}/results/export/json?${qs}`;
}
