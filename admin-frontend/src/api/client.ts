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

export interface ExportDomain {
  domain: string;
  doc_count: number;
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

export interface UserEntry {
  id: string;
  email: string;
  name: string | null;
  harmony_role: string;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  user_id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface WebhookEntry {
  id: string;
  url: string;
  events: string[];
  enabled: boolean;
  created_by: string;
  created_at: string;
}

export interface UrlEntry {
  id: string;
  url: string;
  domain: string;
  language: string | null;
  title: string | null;
  crawled_at: string | null;
}

export interface DomainStat {
  domain: string;
  document_count: number;
  languages: string[];
  last_crawled_at: string | null;
}

export interface BlacklistPattern {
  id: string;
  pattern: string;
  reason: string | null;
  created_by: string;
  created_at: string;
}

export interface ModelRegistryEntry {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  litellm_model_id: string;
  model_type: "llm" | "embedding" | "reranker";
  api_key_set: boolean;
  env_override: boolean;
  cost_per_token: number | null;
  enabled: boolean;
  ollama_host: string | null;
  allowed_groups: string[];
  created_at: string;
}

export interface ModelManifestEntry {
  model_id: string;
  name: string;
  type: string;
}

export interface ModelManifestProvider {
  id: string;
  name: string;
  models: ModelManifestEntry[];
}

export interface ModelManifest {
  chat: string[];
  embedding: string[];
  rerank: string[];
}

export interface OllamaModel {
  name: string;
  size: number;
  modified_at: string;
  model_type: "embedding" | "chat" | "reranker";
}

export interface ScheduleEntry {
  id: string;
  name: string;
  next_run_time: string | null;
  cron: string;
}

export interface StartJobRequest {
  config_name: string;
  job_type: "crawl" | "index" | "crawl+index" | "re-embed";
  start_fresh?: boolean;
}

export interface CrawlerConfigDetail {
  name: string;
  description: string | null;
  config_json: { start_urls?: string[]; [key: string]: unknown };
  created_at: string;
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
    fetchApi<{ configs: ConfigEntry[] }>("/admin/configs/crawler"),
  listIndexerConfigs: () =>
    fetchApi<{ configs: ConfigEntry[] }>("/admin/configs/indexer"),

  getCrawlerConfig: (name: string) =>
    fetchApi<Record<string, unknown>>(`/admin/configs/crawler/${name}`),
  getIndexerConfig: (name: string) =>
    fetchApi<Record<string, unknown>>(`/admin/configs/indexer/${name}`),

  createCrawlerConfig: (
    name: string,
    config: Record<string, unknown>,
    description?: string,
  ) =>
    fetchApi<ConfigEntry>("/admin/configs/crawler", {
      method: "POST",
      body: JSON.stringify({ name, config, description }),
    }),

  saveCrawlerConfig: (
    name: string,
    config: Record<string, unknown>,
    description?: string,
  ) =>
    fetchApi<ConfigEntry>(
      `/admin/configs/crawler/${encodeURIComponent(name)}`,
      {
        method: "PUT",
        body: JSON.stringify({ config, description }),
      },
    ),
  saveIndexerConfig: (config: Record<string, unknown>) =>
    fetchApi<{ config: Record<string, unknown> }>("/admin/configs/indexer", {
      method: "PUT",
      body: JSON.stringify({ config }),
    }),

  renameCrawlerConfig: (name: string, newName: string) =>
    fetchApi<ConfigEntry>(`/admin/configs/crawler/${name}`, {
      method: "PATCH",
      body: JSON.stringify({ name: newName }),
    }),
  renameIndexerConfig: (name: string, newName: string) =>
    fetchApi<ConfigEntry>(`/admin/configs/indexer/${name}/rename`, {
      method: "POST",
      body: JSON.stringify({ new_name: newName }),
    }),

  deleteCrawlerConfig: (name: string) =>
    fetchApi<{ deleted: boolean }>(`/admin/configs/crawler/${name}`, {
      method: "DELETE",
    }),
  deleteIndexerConfig: (name: string) =>
    fetchApi<{ deleted: boolean }>(`/admin/configs/indexer/${name}`, {
      method: "DELETE",
    }),

  exportCrawlerConfig: (name: string) =>
    fetchApi<{ name: string; yaml_content: string }>(
      `/admin/configs/crawler/${name}/export`,
    ),
  exportIndexerConfig: (name: string) =>
    fetchApi<{ name: string; yaml_content: string }>(
      `/admin/configs/indexer/${name}/export`,
    ),

  getCrawlerSchema: () =>
    fetchApi<Record<string, unknown>>("/admin/configs/crawler/schema"),
  getIndexerSchema: () =>
    fetchApi<Record<string, unknown>>("/admin/configs/indexer/schema"),

  validateElasticsearch: (url: string) =>
    fetchApi<{
      valid: boolean;
      status: string;
      cluster_name: string;
      number_of_nodes: number;
    }>(`/admin/configs/validate/elasticsearch?url=${encodeURIComponent(url)}`),

  // Job operations
  startJob: (req: StartJobRequest) =>
    fetchApi<Job>("/admin/jobs", {
      method: "POST",
      body: JSON.stringify({
        type:
          req.job_type === "re-embed"
            ? "embed"
            : req.job_type === "crawl+index"
              ? "index"
              : req.job_type,
        config_name: req.config_name,
        start_fresh: req.start_fresh ?? false,
      }),
    }),

  cancelJob: (jobId: string) =>
    fetchApi<Job>(`/admin/jobs/${jobId}`, {
      method: "PATCH",
      body: JSON.stringify({ action: "cancel" }),
    }),

  retriggerJob: (jobId: string) =>
    fetchApi<Job>("/admin/jobs", {
      method: "POST",
      body: JSON.stringify({ copy_from: jobId }),
    }),

  startFreshJob: (jobId: string) =>
    fetchApi<Job>(`/admin/jobs/${jobId}`, {
      method: "PATCH",
      body: JSON.stringify({ reset_checkpoint: true }),
    }),

  // Schedules
  listSchedules: () => fetchApi<ScheduleEntry[]>("/admin/schedules"),

  createSchedule: (config_name: string, cron_expr: string) =>
    fetchApi<ScheduleEntry>("/admin/schedules", {
      method: "POST",
      body: JSON.stringify({ config_name, cron_expr }),
    }),

  deleteSchedule: (config_name: string) =>
    fetchApi<void>(`/admin/schedules/${encodeURIComponent(config_name)}`, {
      method: "DELETE",
    }),

  // Crawler configs (detailed, for job picker)
  listCrawlerConfigsDetailed: () =>
    fetchApi<{ configs: CrawlerConfigDetail[] }>("/admin/configs/crawler"),

  duplicateCrawlerConfig: (name: string, new_name: string) =>
    fetchApi<CrawlerConfigDetail>("/admin/configs/crawler", {
      method: "POST",
      body: JSON.stringify({ name: new_name, copy_from: name }),
    }),

  // Jobs
  listJobs: (type?: string, status?: string) => {
    const params = new URLSearchParams();
    if (type) params.set("job_type", type);
    if (status) params.set("status", status);
    const query = params.toString() ? `?${params}` : "";
    return fetchApi<Job[]>(`/admin/jobs${query}`);
  },

  getJob: (jobId: string) => fetchApi<Job>(`/admin/jobs/${jobId}`),

  startCrawlJob: (configName: string, outputOverride?: string) =>
    fetchApi<Job>("/admin/jobs", {
      method: "POST",
      body: JSON.stringify({
        type: "crawl",
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
    }>("/admin/jobs/preflight"),

  startIndexJob: (configName: string) =>
    fetchApi<Job>("/admin/jobs", {
      method: "POST",
      body: JSON.stringify({ type: "index", config_name: configName }),
    }),

  startEmbedJob: () =>
    fetchApi<Job>("/admin/jobs", {
      method: "POST",
      body: JSON.stringify({ type: "embed" }),
    }),

  stopJob: (jobId: string, force = false) =>
    fetchApi<Job>(`/admin/jobs/${jobId}`, {
      method: "PATCH",
      body: JSON.stringify({ action: "stop", force }),
    }),

  pauseJob: (jobId: string) =>
    fetchApi<Job>(`/admin/jobs/${jobId}`, {
      method: "PATCH",
      body: JSON.stringify({ action: "pause" }),
    }),

  resumeJob: (jobId: string) =>
    fetchApi<Job>(`/admin/jobs/${jobId}`, {
      method: "PATCH",
      body: JSON.stringify({ action: "resume" }),
    }),

  getJobProgress: (jobId: string) =>
    fetchApi<JobProgress>(`/admin/jobs/${jobId}/progress`),

  getJobLogs: (jobId: string, lines = 100) =>
    fetchApi<{ lines: string[] }>(`/admin/jobs/${jobId}/logs?lines=${lines}`),

  getJobLogsStructured: (jobId: string) =>
    fetchApi<{
      logs: Array<{
        id: string;
        level: string;
        message: string;
        created_at: string;
      }>;
    }>(`/admin/jobs/${jobId}/logs`),

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

  // Users
  listUsers: () => fetchApi<{ users: UserEntry[] }>("/admin/users"),

  updateUserRole: (userId: string, role: string) =>
    fetchApi<UserEntry>(`/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),

  // Audit log
  queryAuditLog: (params: {
    user_id?: string;
    action?: string;
    days_back?: number;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params.user_id) query.set("user_id", params.user_id);
    if (params.action) query.set("action", params.action);
    if (params.days_back != null)
      query.set("days_back", String(params.days_back));
    if (params.limit != null) query.set("limit", String(params.limit));
    if (params.offset != null) query.set("offset", String(params.offset));
    const qs = query.toString() ? `?${query}` : "";
    return fetchApi<{ events: AuditEvent[]; total: number }>(
      `/admin/audit-log${qs}`,
    );
  },

  // Webhooks
  listWebhooks: () => fetchApi<WebhookEntry[]>("/admin/webhooks"),

  createWebhook: (data: { url: string; secret?: string; events: string[] }) =>
    fetchApi<WebhookEntry>("/admin/webhooks", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteWebhook: (id: string) =>
    fetchApi<void>(`/admin/webhooks/${id}`, { method: "DELETE" }),

  toggleWebhook: (webhookId: string, enabled: boolean) =>
    fetchApi<WebhookEntry>(`/admin/webhooks/${encodeURIComponent(webhookId)}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),

  // Documents (indexed URLs)
  listUrls: (params: {
    domain?: string;
    language?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params.domain) query.set("domain", params.domain);
    if (params.language) query.set("language", params.language);
    if (params.q) query.set("q", params.q);
    if (params.limit != null) query.set("limit", String(params.limit));
    if (params.offset != null) query.set("offset", String(params.offset));
    const qs = query.toString() ? `?${query}` : "";
    return fetchApi<{ urls: UrlEntry[]; total: number }>(
      `/admin/documents${qs}`,
    );
  },

  deleteDocument: (urlId: string) =>
    fetchApi<{ status: string } | { error: string; message: string }>(
      `/admin/documents/${urlId}`,
      { method: "DELETE" },
    ),

  getDomainStats: () => fetchApi<DomainStat[]>("/admin/documents/domains"),

  listBlacklist: () =>
    fetchApi<{ patterns: BlacklistPattern[] }>("/admin/documents/blacklist"),

  addBlacklist: (pattern: string, reason?: string) =>
    fetchApi<BlacklistPattern>("/admin/documents/blacklist", {
      method: "POST",
      body: JSON.stringify({ pattern, reason }),
    }),

  removeBlacklist: (patternId: string) =>
    fetchApi<void>(`/admin/documents/blacklist/${patternId}`, {
      method: "DELETE",
    }),

  // Export / Import
  listExportDomains: () =>
    fetchApi<{ domains: ExportDomain[] }>("/admin/export/domains").then(
      (r) => r.domains,
    ),

  exportArchive: (domains: string[]): Promise<Blob> =>
    fetch(`${API_BASE}/admin/export/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domains }),
      credentials: "include",
    }).then((r) => {
      if (!r.ok) throw new Error(`Export failed: ${r.statusText}`);
      return r.blob();
    }),

  importArchive: (file: File): Promise<{ imported_docs: number }> => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_BASE}/admin/export/import`, {
      method: "POST",
      body: form,
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(err.detail || "Import failed");
      }
      return r.json();
    });
  },

  // Model registry
  getModelRegistry: () => fetchApi<ModelRegistryEntry[]>("/admin/models"),

  getModelManifest: () => fetchApi<ModelManifest>("/admin/models/manifest"),

  listOllamaModels: (host?: string) =>
    fetchApi<{ models: OllamaModel[] }>(
      `/admin/models/ollama${host ? `?host=${encodeURIComponent(host)}` : ""}`,
    ).then((r) => r.models),

  createModel: (data: {
    name: string;
    provider: string;
    model_id: string;
    model_type: string;
    api_key?: string;
    cost_per_token?: number;
    enabled: boolean;
    ollama_host?: string;
  }) =>
    fetchApi<ModelRegistryEntry>("/admin/models", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateModel: (
    id: string,
    data: Partial<{
      name: string;
      api_key: string;
      cost_per_token: number;
      enabled: boolean;
      ollama_host: string;
    }>,
  ) =>
    fetchApi<ModelRegistryEntry>(`/admin/models/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteModel: (id: string) =>
    fetchApi<void>(`/admin/models/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),

  testModelConnectivity: (id: string) =>
    fetchApi<{ ok: boolean; latency_ms?: number; error?: string }>(
      `/admin/models/${encodeURIComponent(id)}/test`,
      { method: "POST" },
    ),

  updateModelGroups: (id: string, groups: string[]) =>
    fetchApi<ModelRegistryEntry>(
      `/admin/models/${encodeURIComponent(id)}/groups`,
      {
        method: "PATCH",
        body: JSON.stringify({ groups }),
      },
    ),

  getGroups: () =>
    fetchApi<{ groups: string[] }>("/admin/users/groups").then((r) => r.groups),

  // Singleton indexer config (for Models/IndexerConfig page)
  getSingletonIndexerConfig: () =>
    fetchApi<{ config_json: Record<string, unknown> }>(
      "/admin/configs/indexer",
    ),

  saveSingletonIndexerConfig: (config: Record<string, unknown>) =>
    fetchApi<{ config_json: Record<string, unknown> }>(
      "/admin/configs/indexer",
      {
        method: "PUT",
        body: JSON.stringify({ config }),
      },
    ),

  exportSingletonIndexerConfig: () =>
    fetchApi<string>("/admin/configs/indexer/export"),

  importSingletonIndexerConfig: (yamlContent: string): Promise<void> => {
    const form = new FormData();
    form.append(
      "file",
      new Blob([yamlContent], { type: "application/x-yaml" }),
      "config.yaml",
    );
    return fetch(`${API_BASE}/admin/configs/indexer/import`, {
      method: "POST",
      body: form,
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(err.detail || "Import failed");
      }
    });
  },
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
