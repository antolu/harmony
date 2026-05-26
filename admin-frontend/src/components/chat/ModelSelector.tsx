import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
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
  const { data: policies, isLoading } = useQuery({
    queryKey: ["model-policy"],
    queryFn: () => api.getModelPolicy(),
    staleTime: 60_000,
  });

  const models = policies ?? [];

  return (
    <Select value={value} onValueChange={onChange} disabled={isLoading}>
      <SelectTrigger className="h-7 text-xs w-auto min-w-[120px] border-0 bg-transparent px-2 focus:ring-0 focus:ring-offset-0">
        <SelectValue
          placeholder={isLoading ? "Loading models..." : "Default model"}
        />
      </SelectTrigger>
      <SelectContent>
        {models.length === 0 ? (
          <SelectItem value="">Default model</SelectItem>
        ) : (
          models.map((policy) => (
            <SelectItem key={policy.model_id} value={policy.model_id}>
              {policy.model_id}
            </SelectItem>
          ))
        )}
      </SelectContent>
    </Select>
  );
}
