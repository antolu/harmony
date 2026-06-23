import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/shared/api/client";

export function useApiKeyCreation() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);

  const createKey = async (name: string, value: string) => {
    setCreating(true);
    try {
      const key = await api.createLlmApiKey(name, value);
      await queryClient.invalidateQueries({ queryKey: ["llmApiKeys"] });
      return key;
    } finally {
      setCreating(false);
    }
  };

  return { creating, createKey };
}
