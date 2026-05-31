const API_BASE = "/api";

export interface ConversationListItem {
  id: string;
  title: string | null;
  mode: string;
  updated_at: string;
  message_count: number;
}

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
  flow?: string;
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

export async function fetchApi<T>(
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

  if (response.status === 401) {
    const rawRedirect = window.location.pathname + window.location.search;
    const safeRedirect =
      rawRedirect.startsWith("/") && !rawRedirect.startsWith("//")
        ? rawRedirect
        : "/";
    sessionStorage.setItem("harmony_redirect_after_login", safeRedirect);
    window.location.href = `/auth/login?redirect=${encodeURIComponent(safeRedirect)}`;
    throw new Error("Authentication required");
  }

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

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json();
}

export interface TokenUsageRecord {
  user_id: string;
  model: string;
  usage_date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface ReadinessStatus {
  status: string;
  dependencies: {
    elasticsearch: boolean;
    postgres: boolean;
    redis: boolean;
    qdrant: boolean | "disabled";
    ollama: boolean | "disabled";
  };
}

export const api = {
  getHealth: () =>
    fetchApi<{
      status: string;
      dependencies: {
        elasticsearch: boolean;
        qdrant: boolean | "disabled";
        redis: boolean;
        postgres: boolean;
        ollama: boolean | "disabled";
      };
    }>("/ready"),

  getReadiness: () => fetchApi<ReadinessStatus>("/ready"),

  getTokenUsage: (params?: { model?: string; date_range?: string }) => {
    const query = new URLSearchParams();
    if (params?.model) query.set("model", params.model);
    if (params?.date_range) query.set("date_range", params.date_range);
    const qs = query.toString() ? `?${query}` : "";
    return fetchApi<TokenUsageRecord[]>(`/admin/token-usage${qs}`);
  },

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

  indexPreflight: () =>
    fetchApi<{
      needs_recreate: boolean;
      reason: string | null;
      stored_model: string | null;
      actual_model: string | null;
      stored_dim: number | null;
      actual_dim: number | null;
    }>("/jobs/index/preflight"),

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

  startLogin: (provider: string) =>
    fetchApi<{
      flow: string;
      complete: boolean;
      auth_url?: string;
      message: string;
    }>(`/auth/login/${provider}`, { method: "POST" }),

  getLoginStatus: (provider: string) =>
    fetchApi<{ complete: boolean; message: string }>(
      `/auth/login/${provider}/status`,
    ),

  testProviderConnection: (provider: string) =>
    fetchApi<{ success: boolean; message: string }>(
      `/auth/providers/${provider}/test`,
      { method: "POST" },
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

  // Model policy
  getModelPolicy: () =>
    fetchApi<{ model_id: string; allowed_roles: string[] }[]>(
      "/settings/model-policy",
    ),

  addModelPolicyRole: (model_id: string, harmony_role: string) =>
    fetchApi<{ model_id: string; allowed_roles: string[] }>(
      `/settings/model-policy/${encodeURIComponent(model_id)}/roles`,
      {
        method: "POST",
        body: JSON.stringify({ harmony_role }),
      },
    ),

  removeModelPolicyRole: (model_id: string, harmony_role: string) =>
    fetchApi<{ model_id: string; allowed_roles: string[] }>(
      `/settings/model-policy/${encodeURIComponent(model_id)}/roles/${encodeURIComponent(harmony_role)}`,
      { method: "DELETE" },
    ),

  // External search providers
  getExternalProviders: () =>
    fetchApi<
      {
        provider: string;
        enabled: boolean;
        has_key: boolean;
        max_results: number;
      }[]
    >("/settings/external-providers"),

  saveProviderKey: (provider: string, key: string) =>
    fetchApi<{ success: boolean }>(
      `/settings/external-providers/${encodeURIComponent(provider)}/key`,
      {
        method: "POST",
        body: JSON.stringify({ key }),
      },
    ),

  updateProviderConfig: (
    provider: string,
    config: { enabled?: boolean; max_results?: number },
  ) =>
    fetchApi<{
      provider: string;
      enabled: boolean;
      has_key: boolean;
      max_results: number;
    }>(`/settings/external-providers/${encodeURIComponent(provider)}`, {
      method: "PATCH",
      body: JSON.stringify(config),
    }),

  // Conversations
  getConversations: (limit = 20, offset = 0) =>
    fetchApi<{ conversations: ConversationListItem[]; total: number }>(
      `/conversations/?limit=${limit}&offset=${offset}`,
    ),

  getConversation: (id: string) =>
    fetchApi<{ messages: unknown[] }>(`/conversations/${id}`),

  updateConversationTitle: (id: string, title: string) =>
    fetchApi<{ title: string }>(`/conversations/${id}/title`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),

  deleteConversation: (id: string) =>
    fetchApi<void>(`/conversations/${id}`, { method: "DELETE" }),

  // Feedback
  postFeedback: (payload: {
    conversation_id: string;
    message_id: number;
    rating: "up" | "down";
  }) =>
    fetchApi<{ success: boolean }>("/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  deleteFeedback: (conversation_id: string, message_id: number) =>
    fetchApi<void>(`/feedback/${conversation_id}/${message_id}`, {
      method: "DELETE",
    }),

  // Preferences
  getPreferences: () => fetchApi<{ theme: string }>("/preferences"),

  updatePreferences: (prefs: { theme?: string }) =>
    fetchApi<{ theme: string }>("/preferences", {
      method: "PATCH",
      body: JSON.stringify(prefs),
    }),

  // Current user
  getCurrentUser: () =>
    fetchApi<{
      id: string;
      email: string | null;
      display_name: string | null;
      harmony_role: string;
    }>("/me"),
};

// SSE Helpers

export function createSSEPostConnection(
  endpoint: string,
  body: Record<string, unknown>,
  eventTypes: string[],
  onMessage: (event: string, data: unknown) => void,
  onError?: (error: Error) => void,
): () => void {
  const controller = new AbortController();

  fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "include",
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok || !response.body) {
        onError?.(new Error(`HTTP ${response.status}`));
        return;
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          if (!part.trim()) continue;
          const lines = part.split("\n");
          let eventType = "message";
          let dataStr = "";
          for (const line of lines) {
            if (line.startsWith("event:")) eventType = line.slice(6).trim();
            else if (line.startsWith("data:")) dataStr = line.slice(5).trim();
          }
          if (!dataStr) continue;
          if (eventTypes.length === 0 || eventTypes.includes(eventType)) {
            try {
              const parsed = JSON.parse(dataStr);
              onMessage(eventType, parsed);
            } catch {
              onMessage(eventType, dataStr);
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError?.(err instanceof Error ? err : new Error(String(err)));
      }
    });

  return () => controller.abort();
}

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
