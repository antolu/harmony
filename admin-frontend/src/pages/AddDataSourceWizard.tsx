import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ProviderTypeCard } from "@/components/data-sources/ProviderTypeCard";
import { ProviderConfigForm } from "@/components/data-sources/ProviderConfigForm";
import { useToast } from "@/hooks/use-toast";
import { api, type ProviderTypeInfo } from "@/api/client";
import { cn } from "@/lib/utils";

const STEPS = [
  { id: 1, label: "Choose type" },
  { id: 2, label: "Configure" },
] as const;

export function AddDataSourceWizard() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [step, setStep] = useState<1 | 2>(1);
  const [selectedType, setSelectedType] = useState<ProviderTypeInfo | null>(
    null,
  );
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [name, setName] = useState<string>("");

  const { data: providerTypesData } = useQuery({
    queryKey: ["providerTypes"],
    queryFn: () => api.listProviderTypes(),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createDataSource(name, selectedType!.type, config),
    onSuccess: (result) => {
      toast({ title: "Data source created" });
      queryClient.invalidateQueries({ queryKey: ["dataSources"] });
      navigate(`/admin/data-sources/${result.id}`);
    },
    onError: () => {
      toast({
        title: "Failed to save. Check the fields below and try again.",
        variant: "destructive",
      });
    },
  });

  const handleTypeSelect = (type: ProviderTypeInfo) => {
    setSelectedType(type);
    setStep(2);
  };

  const handleBack = () => {
    setStep(1);
    setSelectedType(null);
  };

  const providerTypes = providerTypesData?.types ?? [];

  return (
    <div className="space-y-6">
      <Link
        to="/admin/data-sources"
        className="text-sm text-muted-foreground hover:underline"
      >
        ← Data Sources
      </Link>

      <div className="flex items-center gap-2">
        {STEPS.map((s, i) => {
          const clickable = s.id === 1 && step !== 1;
          return (
            <div key={s.id} className="flex items-center gap-2">
              <button
                type="button"
                disabled={!clickable}
                onClick={clickable ? handleBack : undefined}
                className={cn(
                  "flex items-center gap-2",
                  clickable ? "cursor-pointer" : "cursor-default",
                )}
              >
                <div
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium",
                    step === s.id
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground",
                  )}
                >
                  {s.id}
                </div>
                <span
                  className={cn(
                    "text-sm text-muted-foreground",
                    clickable && "hover:underline hover:text-foreground",
                  )}
                >
                  {s.label}
                </span>
              </button>
              {i < STEPS.length - 1 && (
                <div className="h-px w-8 bg-muted-foreground/30" />
              )}
            </div>
          );
        })}
      </div>

      {step === 1 && (
        <div className="space-y-4">
          <div>
            <h1 className="text-xl font-bold">Choose a source type</h1>
            <p className="text-sm text-muted-foreground">
              Select the type of data source you want to connect. Only installed
              provider types are shown.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {providerTypes.map((type) => (
              <ProviderTypeCard
                key={type.type}
                type={type.type}
                displayName={type.display_name}
                description={type.description}
                selected={selectedType?.type === type.type}
                onClick={() => handleTypeSelect(type)}
              />
            ))}
          </div>
        </div>
      )}

      {step === 2 && selectedType && (
        <div className="space-y-4">
          <h1 className="text-xl font-bold">
            Configure {selectedType.display_name}
          </h1>
          <div className="space-y-2">
            <Label htmlFor="data-source-name">
              Source name<span className="text-destructive">*</span>
            </Label>
            <Input
              id="data-source-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <ProviderConfigForm
            schema={selectedType.schema}
            value={config}
            onChange={setConfig}
          />
          <div className="flex items-center justify-between pt-4">
            <Button variant="outline" onClick={handleBack}>
              Back
            </Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={!name || createMutation.isPending}
            >
              {createMutation.isPending ? "Creating..." : "Create Source"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
