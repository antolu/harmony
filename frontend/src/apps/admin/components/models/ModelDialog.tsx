import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Switch } from "@/shared/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { api } from "@/shared/api/client";
import type { ModelManifest, ModelRegistryEntry } from "@/shared/api/client";
import { Combobox } from "@/shared/components/ui/combobox";
import { useProviderModels } from "@/shared/hooks/useProviderModels";

export interface ModelFormValues {
  name: string;
  provider: string;
  model_id: string;
  model_type: string;
  api_key_id: string;
  new_api_key_value: string;
  new_api_key_name: string;
  cost_per_token: string;
  enabled: boolean;
  ollama_host_id: string;
  custom_model_id: string;
  use_custom_model_id: boolean;
}

const PROVIDER_LABELS: Record<string, string> = {
  hosted_vllm: "vLLM",
};

function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider;
}

function providerFromLabel(label: string, providers: string[]): string {
  return providers.find((p) => providerLabel(p) === label) ?? label;
}

export function deriveProviders(manifest: ModelManifest | undefined): string[] {
  if (!manifest) return [];
  const all = [
    ...manifest.chat,
    ...manifest.embedding,
    ...manifest.rerank,
    ...manifest.vision,
  ];
  const providers = new Set<string>();
  for (const entry of all) {
    const slash = entry.indexOf("/");
    if (slash > 0) providers.add(entry.slice(0, slash));
  }
  return [
    "ollama",
    "hosted_vllm",
    ...Array.from(providers)
      .filter((p) => p !== "ollama" && p !== "hosted_vllm")
      .sort(),
  ];
}

export function modelsForProvider(
  manifest: ModelManifest | undefined,
  provider: string,
  modelType: string,
): string[] {
  if (!manifest || !provider) return [];
  const key =
    modelType === "llm"
      ? "chat"
      : modelType === "embedding"
        ? "embedding"
        : modelType === "vision"
          ? "vision"
          : "rerank";
  const prefix = provider === "ollama" ? null : `${provider}/`;
  return manifest[key]
    .filter((m) => (prefix ? m.startsWith(prefix) : true))
    .map((m) => (prefix ? m.slice(prefix.length) : m));
}

export function ModelDialog({
  open,
  onOpenChange,
  initial,
  manifest,
  registry,
  onSubmit,
  isPending,
  title,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initial?: Partial<ModelFormValues>;
  manifest: ModelManifest | undefined;
  registry: ModelRegistryEntry[] | undefined;
  onSubmit: (values: ModelFormValues) => void;
  isPending: boolean;
  title: string;
}) {
  const defaultEnabled = (modelType: string) => {
    if (initial?.enabled !== undefined) return initial.enabled;
    if (
      modelType === "embedding" ||
      modelType === "reranker" ||
      modelType === "vision"
    ) {
      return !(registry ?? []).some((e) => e.model_type === modelType);
    }
    return true;
  };

  const [form, setForm] = useState<ModelFormValues>({
    name: initial?.name ?? "",
    provider: initial?.provider ?? "",
    model_id: initial?.model_id ?? "",
    model_type: initial?.model_type ?? "llm",
    api_key_id: initial?.api_key_id ?? "",
    new_api_key_value: "",
    new_api_key_name: "",
    cost_per_token: initial?.cost_per_token ?? "",
    enabled: defaultEnabled(initial?.model_type ?? "llm"),
    ollama_host_id: initial?.ollama_host_id ?? "",
    custom_model_id: "",
    use_custom_model_id: false,
  });

  const providers = deriveProviders(manifest);
  const isOllama = form.provider === "ollama";
  const isVllm = form.provider === "hosted_vllm";
  const isSelfHosted = isOllama || isVllm;
  const isValidProvider = providers.includes(form.provider);
  const providerModels = modelsForProvider(
    manifest,
    form.provider,
    form.model_type,
  );

  const { data: ollamaHosts } = useQuery({
    queryKey: ["ollamaHosts"],
    queryFn: api.listOllamaHosts,
    staleTime: 30_000,
  });

  const { data: llmApiKeys } = useQuery({
    queryKey: ["llmApiKeys"],
    queryFn: api.listLlmApiKeys,
    staleTime: 30_000,
  });

  const hostsForProvider = (ollamaHosts ?? []).filter(
    (h) => h.host_type === (isVllm ? "vllm" : "ollama"),
  );
  const selectedHost = hostsForProvider.find(
    (h) => h.id === form.ollama_host_id,
  );

  const { models: filteredHostModels, isFetching: hostModelsFetching } =
    useProviderModels(form.provider, selectedHost?.url, form.model_type, {
      enabled: isSelfHosted && !!selectedHost,
    });

  // model_id stored in DB is always bare (no provider prefix).
  // Strip the prefix if the user somehow typed the full string.
  const bareModelId = form.model_id.startsWith(`${form.provider}/`)
    ? form.model_id.slice(form.provider.length + 1)
    : form.model_id;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-lg"
        onFocusOutside={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <Tabs
            value={form.model_type}
            onValueChange={(v) =>
              setForm((f) => ({
                ...f,
                model_type: v,
                model_id: "",
                enabled: defaultEnabled(v),
              }))
            }
          >
            <TabsList className="w-full">
              <TabsTrigger value="llm" className="flex-1">
                LLM
              </TabsTrigger>
              <TabsTrigger value="embedding" className="flex-1">
                Embedding
              </TabsTrigger>
              <TabsTrigger value="reranker" className="flex-1">
                Reranker
              </TabsTrigger>
              <TabsTrigger value="vision" className="flex-1">
                Vision
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="space-y-1">
            <Label>Provider</Label>
            <Combobox
              options={providers.map(providerLabel)}
              value={providerLabel(form.provider)}
              onChange={(v) =>
                setForm((f) => ({
                  ...f,
                  provider: providerFromLabel(v, providers),
                  model_id: "",
                }))
              }
              placeholder="Select a provider…"
              searchPlaceholder="Search providers…"
            />
          </div>

          {isValidProvider &&
            ollamaHosts !== undefined &&
            llmApiKeys !== undefined && (
              <>
                {isSelfHosted && (
                  <div className="space-y-1">
                    <Label>{isVllm ? "vLLM Host" : "Ollama Host"}</Label>
                    <Combobox
                      options={hostsForProvider.map((h) => h.name)}
                      value={selectedHost?.name ?? ""}
                      onChange={(v) => {
                        const id =
                          hostsForProvider.find((h) => h.name === v)?.id ?? "";
                        setForm((f) => ({ ...f, ollama_host_id: id }));
                      }}
                      placeholder="Select host..."
                      searchPlaceholder="Search hosts..."
                    />
                  </div>
                )}

                <div className="space-y-1">
                  <Label>Model ID</Label>
                  {isSelfHosted ? (
                    filteredHostModels.length > 0 ? (
                      <Combobox
                        options={filteredHostModels.map((m) => m.name)}
                        value={form.model_id}
                        onChange={(v) =>
                          setForm((f) => ({ ...f, model_id: v }))
                        }
                        placeholder="Select a model…"
                        searchPlaceholder="Search models…"
                      />
                    ) : (
                      <Input
                        value={form.model_id}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, model_id: e.target.value }))
                        }
                        placeholder={
                          hostModelsFetching
                            ? "Loading models…"
                            : selectedHost
                              ? "No matching models — enter manually"
                              : "Enter host above to load models"
                        }
                      />
                    )
                  ) : providerModels.length === 0 ? (
                    <Input
                      value={form.model_id}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, model_id: e.target.value }))
                      }
                      placeholder="Enter model ID"
                    />
                  ) : (
                    <Combobox
                      options={providerModels}
                      value={form.model_id}
                      onChange={(v) => setForm((f) => ({ ...f, model_id: v }))}
                      placeholder="Select a model…"
                      searchPlaceholder="Search models…"
                    />
                  )}
                  {bareModelId && (
                    <p className="text-xs text-muted-foreground">
                      Stored as: <code>{bareModelId}</code> (LiteLLM:{" "}
                      <code>
                        {form.provider}/{bareModelId}
                      </code>
                      )
                    </p>
                  )}
                </div>

                <div className="space-y-1">
                  <Label>Name</Label>
                  <Input
                    value={form.name}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, name: e.target.value }))
                    }
                    placeholder="Display name"
                  />
                </div>

                <div className="space-y-3">
                  <div className="space-y-1">
                    <Label>API Key{isSelfHosted && " (optional)"}</Label>
                    <Combobox
                      options={(llmApiKeys ?? []).map((k) => k.name)}
                      value={
                        form.new_api_key_name ||
                        llmApiKeys?.find((k) => k.id === form.api_key_id)
                          ?.name ||
                        ""
                      }
                      onChange={(v) => {
                        const id =
                          llmApiKeys?.find((k) => k.name === v)?.id ?? "";
                        setForm((f) => ({
                          ...f,
                          api_key_id: id,
                          new_api_key_value: "",
                          new_api_key_name: "",
                        }));
                      }}
                      onCreate={(name) =>
                        setForm((f) => ({
                          ...f,
                          api_key_id: "",
                          new_api_key_name: name,
                          new_api_key_value: "",
                        }))
                      }
                      createLabel={(v) => `Create new key "${v}"`}
                      placeholder="Select or create a key..."
                      searchPlaceholder="Search keys..."
                    />
                  </div>
                  {form.new_api_key_name && (
                    <Input
                      type="password"
                      value={form.new_api_key_value}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          new_api_key_value: e.target.value,
                        }))
                      }
                      placeholder={`Paste secret value for "${form.new_api_key_name}"`}
                      autoFocus
                      onKeyDown={(e) => {
                        if (
                          e.key === "Enter" &&
                          isValidProvider &&
                          bareModelId &&
                          form.name &&
                          form.new_api_key_value
                        ) {
                          onSubmit({ ...form, model_id: bareModelId });
                        }
                      }}
                    />
                  )}
                </div>

                <div className="space-y-1">
                  <Label>Cost per token (optional)</Label>
                  <Input
                    type="number"
                    value={form.cost_per_token}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, cost_per_token: e.target.value }))
                    }
                    placeholder="0.000001"
                    step="0.000001"
                  />
                </div>

                <div className="flex items-center gap-3">
                  <Label>Enabled</Label>
                  <Switch
                    checked={form.enabled}
                    onCheckedChange={(v) =>
                      setForm((f) => ({ ...f, enabled: v }))
                    }
                  />
                </div>
              </>
            )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => onSubmit({ ...form, model_id: bareModelId })}
            disabled={
              isPending ||
              !isValidProvider ||
              !bareModelId ||
              !form.name ||
              (!!form.new_api_key_name && !form.new_api_key_value)
            }
          >
            {isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            {title}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
