import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: { "Content-Type": "application/json" },
});

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
}

export const modelsApi = {
  getSettings: async (): Promise<ModelSettings> => {
    const r = await apiClient.get<ModelSettings>("/settings/models");
    return r.data;
  },

  updateSettings: async (
    patch: Partial<ModelSettings>,
  ): Promise<ModelSettings> => {
    const r = await apiClient.patch<ModelSettings>("/settings/models", patch);
    return r.data;
  },

  validateModel: async (
    model: string,
    provider: string,
    model_type: string,
  ): Promise<{ valid: boolean; error?: string }> => {
    const r = await apiClient.post("/settings/models/validate", {
      model,
      provider,
      model_type,
    });
    return r.data;
  },

  listOllamaModels: async (
    host?: string,
  ): Promise<{ models: OllamaModel[] }> => {
    const r = await apiClient.get("/models/ollama", {
      params: host ? { host } : undefined,
    });
    return r.data;
  },

  deleteOllamaModel: async (name: string): Promise<{ deleted: boolean }> => {
    const r = await apiClient.delete(
      `/models/ollama/${encodeURIComponent(name)}`,
    );
    return r.data;
  },

  getPipelineConfig: async (): Promise<PipelineConfig> => {
    const r = await apiClient.get<PipelineConfig>("/settings/pipeline");
    return r.data;
  },

  updatePipelineConfig: async (
    patch: Partial<PipelineConfig>,
  ): Promise<PipelineConfig> => {
    const r = await apiClient.patch<PipelineConfig>(
      "/settings/pipeline",
      patch,
    );
    return r.data;
  },
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
  const response = await fetch(`${API_BASE_URL}/api/models/ollama/pull`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, host: host || undefined }),
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
