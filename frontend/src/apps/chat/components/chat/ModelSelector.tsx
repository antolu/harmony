import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";

interface ModelSelectorProps {
  value: string;
  onChange: (model: string) => void;
}

export function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const { data: registry, isLoading } = useQuery({
    queryKey: ["modelRegistry"],
    queryFn: api.getModelRegistry,
    staleTime: 60_000,
  });

  const llmModels = (registry ?? []).filter(
    (m) => m.model_type === "llm" && m.enabled,
  );

  useEffect(() => {
    if (!value && llmModels.length > 0) {
      onChange(llmModels[0].litellm_model_id);
    }
  }, [value, llmModels, onChange]);

  const effectiveValue = value || llmModels[0]?.litellm_model_id;

  return (
    <Select
      value={effectiveValue}
      onValueChange={onChange}
      disabled={isLoading}
    >
      <SelectTrigger className="h-9 text-sm w-auto min-w-[120px] border-0 bg-transparent px-2.5 focus:ring-0 focus:ring-offset-0">
        <SelectValue
          placeholder={isLoading ? "Loading models…" : "Select model"}
        />
      </SelectTrigger>
      <SelectContent>
        {llmModels.map((m) => (
          <SelectItem key={m.model_id} value={m.litellm_model_id}>
            {m.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
