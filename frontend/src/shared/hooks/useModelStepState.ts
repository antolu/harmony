import { useState } from "react";

export type ModelStepProvider = "ollama" | "hosted_vllm" | "litellm";

export interface ModelHostKeyIds {
  model_host_id?: string;
  api_key_id?: string;
}

export function useModelStepState(defaultProvider: ModelStepProvider) {
  const [provider, setProvider] = useState<ModelStepProvider>(defaultProvider);
  const [model, setModel] = useState("");
  const [validated, setValidated] = useState(true);
  const [hostKeyIds, setHostKeyIds] = useState<ModelHostKeyIds>({});

  const reset = (resetProvider: ModelStepProvider = "litellm") => {
    setModel("");
    setProvider(resetProvider);
    setValidated(true);
  };

  return {
    provider,
    setProvider,
    model,
    setModel,
    validated,
    setValidated,
    hostKeyIds,
    onHostKeyChange: (ids: ModelHostKeyIds) =>
      setHostKeyIds((prev) => ({ ...prev, ...ids })),
    reset,
  };
}
