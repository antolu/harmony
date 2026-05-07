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
}

export interface ValidationResult {
  ok: boolean;
  message: string;
}

export interface ValidationResponse {
  elasticsearch?: ValidationResult;
  redis?: ValidationResult;
}

export interface CompleteSetupRequest {
  elasticsearch_url: string;
  redis_url: string;
  embedding_provider?: string;
  embedding_model?: string;
  reranker_provider?: string;
  reranker_model?: string;
  llm_provider?: string;
  llm_model?: string;
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
};
