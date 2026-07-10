import { useQuery } from "@tanstack/react-query";
import { api } from "@/shared/api/client";

function ollamaTypeKey(
  modelType: string,
): "embedding" | "chat" | "reranker" | "vision" {
  switch (modelType) {
    case "embedding":
      return "embedding";
    case "reranker":
      return "reranker";
    case "vision":
      return "vision";
    default:
      return "chat";
  }
}

export function useProviderModels(
  provider: string,
  hostUrl: string | undefined,
  modelType: string,
  options?: { enabled?: boolean; retry?: number },
) {
  const isVllm = provider === "hosted_vllm";

  const { data, isFetching, isLoading, isError } = useQuery({
    queryKey: [isVllm ? "vllmModels" : "ollamaModels", hostUrl],
    queryFn: () =>
      isVllm
        ? api.listVllmModels(hostUrl as string)
        : api.listOllamaModels(hostUrl),
    enabled: (options?.enabled ?? true) && (!isVllm || !!hostUrl),
    retry: options?.retry,
    staleTime: 30_000,
    meta: { suppressErrorToast: true },
  });

  const allModels = data ?? [];
  // vLLM's /v1/models doesn't report a role, so models aren't filtered by
  // model_type the way Ollama's are — every model is available regardless
  // of which model_type tab the user is configuring.
  const typeKey = ollamaTypeKey(modelType);
  const models = isVllm
    ? allModels
    : allModels.filter((m) => "model_type" in m && m.model_type === typeKey);

  return { models, allModels, isFetching, isLoading, isError };
}
