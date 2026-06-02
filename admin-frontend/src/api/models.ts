import { fetchApi } from "./client";

export interface ModelSettings {
  embedding_provider: "ollama" | "litellm";
  embedding_model: string;
  reranker_provider: "ollama" | "litellm";
  reranker_model: string;
  llm_provider: "ollama" | "litellm";
  llm_model: string;
  embedding_model_changed_since_last_embed: "true" | "false";
}

export interface OllamaModel {
  name: string;
  size: number;
  modified_at: string;
  model_type: "embedding" | "chat" | "reranker";
}

export interface PipelineConfig {
  keyword_candidates_n: number;
  vector_top_k: number;
  search_top_k: number;
  vector_search_enabled: boolean;
  reranker_enabled: boolean;
  reranker_model: string;
  agentic_max_refinement_rounds: number;
  agentic_max_query_variants: number;
  agentic_search_top_k: number;
  agentic_max_sources_returned: number;
  audit_retention_days: number;
  conversation_ttl_days: number;
}

export const modelsApi = {
  getSettings: (): Promise<ModelSettings> =>
    fetchApi<ModelSettings>("/settings/models"),

  updateSettings: (patch: Partial<ModelSettings>): Promise<ModelSettings> =>
    fetchApi<ModelSettings>("/settings/models", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  validateModel: (
    model: string,
    provider: string,
    model_type: string,
  ): Promise<{ valid: boolean; error?: string }> =>
    fetchApi("/settings/models/validate", {
      method: "POST",
      body: JSON.stringify({ model, provider, model_type }),
    }),

  listOllamaModels: (host?: string): Promise<{ models: OllamaModel[] }> => {
    const params = host ? `?host=${encodeURIComponent(host)}` : "";
    return fetchApi<{ models: OllamaModel[] }>(`/models/ollama${params}`);
  },

  deleteOllamaModel: (name: string): Promise<{ deleted: boolean }> =>
    fetchApi(`/models/ollama/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),

  getPipelineConfig: (): Promise<PipelineConfig> =>
    fetchApi<PipelineConfig>("/settings/pipeline"),

  updatePipelineConfig: (
    patch: Partial<PipelineConfig>,
  ): Promise<PipelineConfig> =>
    fetchApi<PipelineConfig>("/settings/pipeline", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  getAvailableModels: (): Promise<{ models: string[] }> =>
    fetchApi<{ models: string[] }>("/settings/models/available"),

  setAvailableModels: (models: string[]): Promise<{ models: string[] }> =>
    fetchApi<{ models: string[] }>("/settings/models/available", {
      method: "PUT",
      body: JSON.stringify({ models }),
    }),
};

// Ollama pull uses POST+SSE — use fetch ReadableStream
export async function* pullOllamaModelStream(
  name: string,
  host?: string,
): AsyncGenerator<{
  status: string;
  completed?: number;
  total?: number;
  error?: string;
}> {
  const response = await fetch(`/api/models/ollama/pull`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, host: host || undefined }),
    credentials: "include",
  });

  if (!response.ok) {
    const err = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    yield { status: "", error: err.detail ?? "Pull failed" };
    return;
  }

  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          yield JSON.parse(line.slice(6));
        } catch {
          // skip malformed line
        }
      }
    }
  }
}
