const API_BASE = "/api";

export interface ConfigEntry {
  name: string;
  type: "crawler" | "indexer";
  created_at: string;
  updated_at: string;
  description?: string;
}

export interface Job {
  id: string;
  type: "crawl" | "index" | "embed";
  status: "pending" | "running" | "paused" | "completed" | "failed" | "stopped";
  config_name: string;
  progress: JobProgress;
  started_at?: string;
  finished_at?: string;
  error?: string;
  pid?: number;
  log_file?: string;
  stats_file?: string;
}

export interface JobProgress {
  pages_crawled: number;
  pages_pending: number;
  requests_made: number;
  pages_per_min: number;
  current_url?: string;
  documents_indexed: number;
  total_documents: number;
  current_phase?: string;
  timestamp?: string;
}

export interface AuthProvider {
  name: string;
  type: string;
  domains: string[];
  has_session: boolean;
}

export interface AuthSession {
  provider: string;
  created_at: string;
  domains: string[];
}

export interface IndexStatus {
  name: string;
  type: "state" | "search";
  language?: string;
  doc_count: number;
}

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    const detail = Array.isArray(error.detail)
      ? error.detail
          .map((e: { loc?: string[]; msg?: string }) =>
            [e.loc?.join("."), e.msg].filter(Boolean).join(": "),
          )
          .join("; ")
      : error.detail;
    throw new Error(detail || "Request failed");
  }

  return response.json();
}

export const api = {
  getHealth: () => fetchApi<{ status: string }>("/health"),

  // Configs
  listCrawlerConfigs: () =>
    fetchApi<{ configs: ConfigEntry[] }>("/configs/crawler"),
  listIndexerConfigs: () =>
    fetchApi<{ configs: ConfigEntry[] }>("/configs/indexer"),

  getCrawlerConfig: (name: string) =>
    fetchApi<Record<string, unknown>>(`/configs/crawler/${name}`),
  getIndexerConfig: (name: string) =>
    fetchApi<Record<string, unknown>>(`/configs/indexer/${name}`),

  saveCrawlerConfig: (
    name: string,
    config: Record<string, unknown>,
    description?: string,
  ) =>
    fetchApi<ConfigEntry>("/configs/crawler", {
      method: "POST",
      body: JSON.stringify({ name, config, description }),
    }),
  saveIndexerConfig: (
    name: string,
    config: Record<string, unknown>,
    description?: string,
  ) =>
    fetchApi<ConfigEntry>("/configs/indexer", {
      method: "POST",
      body: JSON.stringify({ name, config, description }),
    }),

  renameCrawlerConfig: (name: string, newName: string) =>
    fetchApi<ConfigEntry>(`/configs/crawler/${name}/rename`, {
      method: "POST",
      body: JSON.stringify({ new_name: newName }),
    }),
  renameIndexerConfig: (name: string, newName: string) =>
    fetchApi<ConfigEntry>(`/configs/indexer/${name}/rename`, {
      method: "POST",
      body: JSON.stringify({ new_name: newName }),
    }),

  deleteCrawlerConfig: (name: string) =>
    fetchApi<{ deleted: boolean }>(`/configs/crawler/${name}`, {
      method: "DELETE",
    }),
  deleteIndexerConfig: (name: string) =>
    fetchApi<{ deleted: boolean }>(`/configs/indexer/${name}`, {
      method: "DELETE",
    }),

  exportCrawlerConfig: (name: string) =>
    fetchApi<{ name: string; yaml_content: string }>(
      `/configs/crawler/${name}/export`,
    ),
  exportIndexerConfig: (name: string) =>
    fetchApi<{ name: string; yaml_content: string }>(
      `/configs/indexer/${name}/export`,
    ),

  getCrawlerSchema: () =>
    fetchApi<Record<string, unknown>>("/configs/crawler/schema"),
  getIndexerSchema: () =>
    fetchApi<Record<string, unknown>>("/configs/indexer/schema"),

  validateElasticsearch: (url: string) =>
    fetchApi<{
      valid: boolean;
      status: string;
      cluster_name: string;
      number_of_nodes: number;
    }>(`/configs/validate/elasticsearch?url=${encodeURIComponent(url)}`),

  // Jobs
  listJobs: (type?: string, status?: string) => {
    const params = new URLSearchParams();
    if (type) params.set("job_type", type);
    if (status) params.set("status", status);
    const query = params.toString() ? `?${params}` : "";
    return fetchApi<Job[]>(`/jobs${query}`);
  },

  getJob: (jobId: string) => fetchApi<Job>(`/jobs/${jobId}`),

  startCrawlJob: (configName: string, outputOverride?: string) =>
    fetchApi<Job>("/jobs/crawl", {
      method: "POST",
      body: JSON.stringify({
        config_name: configName,
        output_override: outputOverride,
      }),
    }),

  startIndexJob: (configName: string) =>
    fetchApi<Job>("/jobs/index", {
      method: "POST",
      body: JSON.stringify({ config_name: configName }),
    }),

  startEmbedJob: () => fetchApi<Job>("/jobs/embed", { method: "POST" }),

  stopJob: (jobId: string, force = false) =>
    fetchApi<Job>(`/jobs/${jobId}/stop`, {
      method: "POST",
      body: JSON.stringify({ force }),
    }),

  pauseJob: (jobId: string) =>
    fetchApi<Job>(`/jobs/${jobId}/pause`, { method: "POST" }),

  resumeJob: (jobId: string) =>
    fetchApi<Job>(`/jobs/${jobId}/resume`, { method: "POST" }),

  getJobProgress: (jobId: string) =>
    fetchApi<JobProgress>(`/jobs/${jobId}/progress`),

  getJobLogs: (jobId: string, lines = 100) =>
    fetchApi<{ lines: string[] }>(`/jobs/${jobId}/logs?lines=${lines}`),

  // Reset
  resetCrawlState: () =>
    fetchApi<{ success: boolean; message: string; indices_deleted: string[] }>(
      "/reset/crawl-state",
      {
        method: "POST",
        body: JSON.stringify({ confirm: true }),
      },
    ),

  resetSearchIndices: () =>
    fetchApi<{ success: boolean; message: string; indices_deleted: string[] }>(
      "/reset/search-indices",
      {
        method: "POST",
        body: JSON.stringify({ confirm: true }),
      },
    ),

  getIndexStatus: () => fetchApi<{ indices: IndexStatus[] }>("/reset/status"),

  // Auth
  listAuthProviders: () =>
    fetchApi<{ providers: AuthProvider[] }>("/auth/providers"),

  listAuthSessions: () =>
    fetchApi<{ sessions: AuthSession[] }>("/auth/sessions"),

  startSSOLogin: (provider: string) =>
    fetchApi<{ vnc_url: string; session_id: string; message: string }>(
      `/auth/login/${provider}`,
      {
        method: "POST",
      },
    ),

  getLoginStatus: (provider: string) =>
    fetchApi<{ complete: boolean; message: string }>(
      `/auth/login/${provider}/status`,
    ),

  completeSSOLogin: (provider: string) =>
    fetchApi<{ success: boolean; message: string }>(
      `/auth/login/${provider}/complete`,
      {
        method: "POST",
      },
    ),

  clearAuthSession: (provider: string) =>
    fetchApi<{ success: boolean; message: string }>(
      `/auth/sessions/${provider}`,
      {
        method: "DELETE",
      },
    ),

  publishSafetyDecision: (jobId: string, pattern: string, decision: string) =>
    fetchApi<{ status: string }>(`/internal/safety-decision/${jobId}`, {
      method: "POST",
      body: JSON.stringify({ pattern, decision }),
    }),
};

// SSE Helpers
export function createSSEConnection(
  endpoint: string,
  onMessage: (event: string, data: unknown) => void,
  onError?: (error: Error) => void,
): () => void {
  const eventSource = new EventSource(`${API_BASE}${endpoint}`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage("message", data);
    } catch {
      onMessage("message", event.data);
    }
  };

  eventSource.onerror = () => {
    onError?.(new Error("SSE connection error"));
    eventSource.close();
  };

  const eventTypes = [
    "progress",
    "log",
    "done",
    "error",
    "status",
    "safety_pending",
  ];
  eventTypes.forEach((type) => {
    eventSource.addEventListener(type, (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(type, data);
      } catch {
        onMessage(type, event.data);
      }
    });
  });

  return () => eventSource.close();
}
