// Typed API client for backend communication

import type {
  IngestRequest,
  IngestStatusResponse,
  ChatResponse,
} from "@/types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Generic fetch helper ──────────────────────────────────────────────────────
async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `API error: ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ── Ingest ────────────────────────────────────────────────────────────────────
export async function startIngest(
  payload: IngestRequest
): Promise<IngestStatusResponse> {
  return apiFetch<IngestStatusResponse>("/api/v1/ingest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function pollIngestStatus(
  jobId: string
): Promise<IngestStatusResponse> {
  return apiFetch<IngestStatusResponse>(`/api/v1/ingest/${jobId}`);
}

// ── Chat (synchronous) ────────────────────────────────────────────────────────
export async function chatSync(
  repoId: string,
  question: string,
  topK = 8
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/api/v1/chat", {
    method: "POST",
    body: JSON.stringify({ repo_id: repoId, question, top_k: topK }),
  });
}

// ── Stream URL builder ─────────────────────────────────────────────────────────
export function buildStreamUrl(
  repoId: string,
  question: string,
  topK = 8
): string {
  const params = new URLSearchParams({
    repo_id: repoId,
    question,
    top_k: String(topK),
  });
  return `${API_BASE}/api/v1/chat/stream?${params.toString()}`;
}

// ── Health ────────────────────────────────────────────────────────────────────
export async function checkHealth(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/health");
}
