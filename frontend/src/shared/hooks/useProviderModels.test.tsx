import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useProviderModels } from "./useProviderModels";

vi.mock("@/shared/api/client", () => ({
  api: {
    listOllamaModels: vi.fn(),
    listVllmModels: vi.fn(),
  },
}));

import { api } from "@/shared/api/client";

const mockListOllamaModels = vi.mocked(api.listOllamaModels);
const mockListVllmModels = vi.mocked(api.listVllmModels);

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useProviderModels", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls listOllamaModels and filters by model_type for ollama provider", async () => {
    mockListOllamaModels.mockResolvedValue([
      { name: "qwen3:8b", size: 1, modified_at: "", model_type: "chat" },
      {
        name: "qwen3-embedding:0.6b",
        size: 1,
        modified_at: "",
        model_type: "embedding",
      },
    ]);

    const { result } = renderHook(
      () => useProviderModels("ollama", "http://localhost:11434", "llm"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isFetching).toBe(false));

    expect(mockListOllamaModels).toHaveBeenCalledWith("http://localhost:11434");
    expect(mockListVllmModels).not.toHaveBeenCalled();
    expect(result.current.models).toEqual([
      { name: "qwen3:8b", size: 1, modified_at: "", model_type: "chat" },
    ]);
  });

  it("calls listVllmModels and does not filter by model_type for vllm provider", async () => {
    mockListVllmModels.mockResolvedValue([
      { name: "Qwen/Qwen3.5-9B" },
      { name: "meta-llama/Llama-3-8B" },
    ]);

    const { result } = renderHook(
      () => useProviderModels("hosted_vllm", "http://localhost:8000", "llm"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isFetching).toBe(false));

    expect(mockListVllmModels).toHaveBeenCalledWith("http://localhost:8000");
    expect(mockListOllamaModels).not.toHaveBeenCalled();
    expect(result.current.models).toEqual([
      { name: "Qwen/Qwen3.5-9B" },
      { name: "meta-llama/Llama-3-8B" },
    ]);
  });

  it("does not query vllm models when hostUrl is missing", () => {
    renderHook(() => useProviderModels("hosted_vllm", undefined, "llm"), {
      wrapper,
    });

    expect(mockListVllmModels).not.toHaveBeenCalled();
  });

  it("maps embedding/reranker/vision model types to ollama type keys", async () => {
    mockListOllamaModels.mockResolvedValue([
      {
        name: "bge-reranker-v2-m3",
        size: 1,
        modified_at: "",
        model_type: "reranker",
      },
    ]);

    const { result } = renderHook(
      () => useProviderModels("ollama", "http://localhost:11434", "reranker"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isFetching).toBe(false));

    expect(result.current.models).toHaveLength(1);
  });
});
