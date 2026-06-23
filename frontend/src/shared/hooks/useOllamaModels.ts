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

export function useOllamaModels(
  hostUrl: string | undefined,
  modelType: string,
  options?: { enabled?: boolean; retry?: number },
) {
  const { data, isFetching, isLoading, isError } = useQuery({
    queryKey: ["ollamaModels", hostUrl],
    queryFn: () => api.listOllamaModels(hostUrl),
    enabled: options?.enabled ?? true,
    retry: options?.retry,
    staleTime: 30_000,
  });

  const allModels = data ?? [];
  const typeKey = ollamaTypeKey(modelType);
  const models = allModels.filter((m) => m.model_type === typeKey);

  return { models, allModels, isFetching, isLoading, isError };
}
