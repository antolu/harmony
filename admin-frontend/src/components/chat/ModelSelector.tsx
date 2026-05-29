import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { modelsApi } from "@/api/models";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface ModelSelectorProps {
  value: string;
  onChange: (model: string) => void;
}

export function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const { data: policies, isLoading: policiesLoading } = useQuery({
    queryKey: ["model-policy"],
    queryFn: () => api.getModelPolicy(),
    staleTime: 60_000,
  });

  const { data: modelSettings, isLoading: settingsLoading } = useQuery({
    queryKey: ["model-settings-default"],
    queryFn: () => modelsApi.getSettings(),
    staleTime: 60_000,
  });

  const isLoading = policiesLoading || settingsLoading;
  const models = policies ?? [];
  const defaultModel = modelSettings?.llm_model ?? null;

  useEffect(() => {
    if (!value && defaultModel) {
      onChange(defaultModel);
    }
  }, [value, defaultModel, onChange]);

  const options =
    models.length > 0
      ? models
      : defaultModel
        ? [{ model_id: defaultModel }]
        : [];

  return (
    <Select
      value={value || undefined}
      onValueChange={onChange}
      disabled={isLoading}
    >
      <SelectTrigger className="h-7 text-xs w-auto min-w-[120px] border-0 bg-transparent px-2 focus:ring-0 focus:ring-offset-0">
        <SelectValue
          placeholder={isLoading ? "Loading models..." : "Default model"}
        />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.model_id} value={option.model_id}>
            {option.model_id}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
