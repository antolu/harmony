import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    "Content-Type": "application/json",
  },
});

export interface SetupStatus {
  is_configured: boolean;
  missing_configs: string[];
}

export interface ValidationRequest {
  elasticsearch_url?: string;
  redis_url?: string;
  ollama_host?: string;
  qdrant_host?: string;
}

export interface ValidationResult {
  ok: boolean;
  message: string;
}

export interface ValidationResponse {
  elasticsearch?: ValidationResult;
  redis?: ValidationResult;
  ollama?: ValidationResult;
  qdrant?: ValidationResult;
}

export interface CompleteSetupRequest {
  elasticsearch_url: string;
  redis_url: string;
  ollama_host?: string;
  qdrant_host?: string;
  embedding_provider?: string;
  embedding_model?: string;
  reranker_provider?: string;
  reranker_model?: string;
  llm_provider?: string;
  llm_model?: string;
}

export interface OllamaHostStatus {
  value: string;
  from_env: boolean;
}

export interface QdrantHostStatus {
  value: string;
  from_env: boolean;
}

export interface SetupDefaults {
  embedding_model: string;
  reranker_model: string;
  llm_model: string;
}

export const setupApi = {
  getStatus: async (): Promise<SetupStatus> => {
    const response = await apiClient.get<SetupStatus>("/setup/status");
    return response.data;
  },

  validate: async (config: ValidationRequest): Promise<ValidationResponse> => {
    const response = await apiClient.post<ValidationResponse>(
      "/setup/validate",
      config,
    );
    return response.data;
  },

  complete: async (
    config: CompleteSetupRequest,
  ): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post("/setup/complete", config);
    return response.data;
  },

  getOllamaHost: async (): Promise<OllamaHostStatus> => {
    const response =
      await apiClient.get<OllamaHostStatus>("/setup/ollama-host");
    return response.data;
  },

  updateOllamaHost: async (value: string): Promise<OllamaHostStatus> => {
    const response = await apiClient.patch<OllamaHostStatus>(
      "/setup/ollama-host",
      { value },
    );
    return response.data;
  },

  getQdrantHost: async (): Promise<QdrantHostStatus> => {
    const response =
      await apiClient.get<QdrantHostStatus>("/setup/qdrant-host");
    return response.data;
  },

  updateQdrantHost: async (value: string): Promise<QdrantHostStatus> => {
    const response = await apiClient.patch<QdrantHostStatus>(
      "/setup/qdrant-host",
      { value },
    );
    return response.data;
  },

  getDefaults: async (): Promise<SetupDefaults> => {
    const response = await apiClient.get<SetupDefaults>("/setup/defaults");
    return response.data;
  },
};
