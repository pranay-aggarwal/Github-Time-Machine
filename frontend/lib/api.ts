export type JobStatus = "queued" | "cloning" | "fetching" | "analyzing" | "ready" | "failed";

export type StatusResponse = {
  job_id: string;
  repo_id: string | null;
  status: JobStatus;
  progress: number;
  message: string;
};

export type SummaryResponse = {
  repo_id: string;
  name: string;
  url: string;
  metrics: Record<string, number>;
  suggested_questions: string[];
};

export type Evidence = {
  id: string;
  source_type: string;
  source_id: string;
  title: string;
  url?: string | null;
  snippet: string;
};

export type ChatResponse = {
  answer: string;
  reasoning_chain: string[];
  evidence: Evidence[];
  confidence: number;
};

export type TimelineResponse = {
  events: Array<{ date: string; title: string; summary: string; evidence: Evidence[]; category?: string | null; confidence?: number | null }>;
};

export type ActivityResponse = {
  total_commits: number;
  active_days: number;
  has_hour_data: boolean;
  commits_with_hour: number;
  by_date: Array<{ date: string; count: number }>;
  by_hour: Array<{ hour: number; count: number }>;
  top_dates: Array<{ date: string; count: number }>;
  top_time_windows: Array<{ label: string; start_hour: number; end_hour: number; count: number }>;
  by_contributor: Array<{ name: string; count: number }>;
};

export type GraphResponse = {
  nodes: Array<{
    id: string;
    position: { x: number; y: number };
    className?: string;
    style?: Record<string, string | number>;
    data: {
      label: string;
      type?: string;
      summary?: string;
      evidenceCount?: number;
      evidenceIds?: string[];
      color?: string;
      properties?: Record<string, unknown>;
    };
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    label: string;
    animated?: boolean;
    style?: Record<string, string | number>;
    data?: { relationship?: string; label?: string; evidenceIds?: string[]; properties?: Record<string, unknown> };
  }>;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8080";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function analyzeRepo(repoUrl: string) {
  return api<{ job_id: string }>("/repo/analyze", {
    method: "POST",
    body: JSON.stringify({ repo_url: repoUrl })
  });
}

export function getStatus(jobId: string) {
  return api<StatusResponse>(`/repo/${jobId}/status`);
}

export function getSummary(repoId: string) {
  return api<SummaryResponse>(`/repo/${repoId}/summary`);
}

export function askQuestion(repoId: string, question: string) {
  return api<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ repo_id: repoId, question })
  });
}

export function getGraph(repoId: string) {
  return api<GraphResponse>(`/graph?repo_id=${encodeURIComponent(repoId)}`);
}

export function getTimeline(repoId: string) {
  return api<TimelineResponse>(`/timeline?repo_id=${encodeURIComponent(repoId)}`);
}

export function getActivity(repoId: string) {
  return api<ActivityResponse>(`/activity?repo_id=${encodeURIComponent(repoId)}`);
}
