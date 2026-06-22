import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Lock,
  Pencil,
  Trash2,
  Plus,
  Loader2,
  CheckCircle2,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/shared/components/ui/alert-dialog";
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
import { Badge } from "@/shared/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";
import { api } from "@/shared/api/client";
import type {
  ModelManifest,
  ModelRegistryEntry,
  OllamaModel,
} from "@/shared/api/client";
import { Combobox } from "@/shared/components/ui/combobox";
import { useToast } from "@/shared/hooks/use-toast";

interface ModelFormValues {
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

function deriveProviders(manifest: ModelManifest | undefined): string[] {
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
    ...Array.from(providers)
      .filter((p) => p !== "ollama")
      .sort(),
  ];
}

function modelsForProvider(
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

function ModelDialog({
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
  const isValidProvider = providers.includes(form.provider);
  const providerModels = modelsForProvider(
    manifest,
    form.provider,
    form.model_type,
  );

  const ollamaTypeKey =
    form.model_type === "llm"
      ? "chat"
      : form.model_type === "embedding"
        ? "embedding"
        : form.model_type === "vision"
          ? "vision"
          : "reranker";

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

  const selectedHost = ollamaHosts?.find((h) => h.id === form.ollama_host_id);

  const { data: ollamaModels, isFetching: ollamaFetching } = useQuery({
    queryKey: ["ollamaModels", selectedHost?.url],
    queryFn: () => api.listOllamaModels(selectedHost?.url),
    enabled: isOllama && !!selectedHost,
    staleTime: 30_000,
  });
  const filteredOllamaModels: OllamaModel[] = (ollamaModels ?? []).filter(
    (m) => m.model_type === ollamaTypeKey,
  );

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
              options={providers}
              value={form.provider}
              onChange={(v) =>
                setForm((f) => ({ ...f, provider: v, model_id: "" }))
              }
              placeholder="Select a provider…"
              searchPlaceholder="Search providers…"
            />
          </div>

          {isValidProvider &&
            ollamaHosts !== undefined &&
            llmApiKeys !== undefined && (
              <>
                {isOllama && (
                  <div className="space-y-1">
                    <Label>Ollama Host</Label>
                    <Combobox
                      options={(ollamaHosts ?? []).map((h) => h.name)}
                      value={selectedHost?.name ?? ""}
                      onChange={(v) => {
                        const id =
                          ollamaHosts?.find((h) => h.name === v)?.id ?? "";
                        setForm((f) => ({ ...f, ollama_host_id: id }));
                      }}
                      placeholder="Select host..."
                      searchPlaceholder="Search hosts..."
                    />
                  </div>
                )}

                <div className="space-y-1">
                  <Label>Model ID</Label>
                  {isOllama ? (
                    filteredOllamaModels.length > 0 ? (
                      <Combobox
                        options={filteredOllamaModels.map((m) => m.name)}
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
                          ollamaFetching
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

                {!isOllama && (
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <Label>API Key</Label>
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
                      />
                    )}
                  </div>
                )}

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

const NO_KEY_OPTION = "No key";
const CLEAR_API_KEY = "__clear__";

function ApiKeyCell({
  entry,
  onSelectExisting,
  onCreate,
  onClear,
  isPending,
}: {
  entry: ModelRegistryEntry;
  onSelectExisting: (id: string) => void;
  onCreate: (name: string, value: string) => void;
  onClear: () => void;
  isPending: boolean;
}) {
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyValue, setNewKeyValue] = useState("");

  const { data: llmApiKeys } = useQuery({
    queryKey: ["llmApiKeys"],
    queryFn: api.listLlmApiKeys,
    staleTime: 30_000,
  });

  if (entry.env_override) {
    return (
      <div className="flex items-center gap-1 text-yellow-600">
        <Lock className="h-3 w-3" />
        <span className="text-xs">ENV override</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <Combobox
        options={[NO_KEY_OPTION, ...(llmApiKeys ?? []).map((k) => k.name)]}
        value={newKeyName || entry.api_key_name || ""}
        onChange={(v) => {
          if (v === NO_KEY_OPTION) {
            onClear();
            setNewKeyName("");
            setNewKeyValue("");
            return;
          }
          const id = llmApiKeys?.find((k) => k.name === v)?.id;
          if (id) {
            onSelectExisting(id);
            setNewKeyName("");
            setNewKeyValue("");
          }
        }}
        onCreate={(name) => {
          setNewKeyName(name);
          setNewKeyValue("");
        }}
        createLabel={(v) => `Create new key "${v}"`}
        placeholder="Not set"
        searchPlaceholder="Search keys..."
        disabled={isPending}
        variant="inline"
      />
      {newKeyName && (
        <>
          <Input
            type="password"
            value={newKeyValue}
            onChange={(e) => setNewKeyValue(e.target.value)}
            className="h-7 w-32 text-xs"
            placeholder={`Secret for "${newKeyName}"`}
            autoFocus
          />
          <Button
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => {
              onCreate(newKeyName, newKeyValue);
              setNewKeyName("");
              setNewKeyValue("");
            }}
            disabled={!newKeyValue || isPending}
          >
            Save
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={() => {
              setNewKeyName("");
              setNewKeyValue("");
            }}
          >
            Cancel
          </Button>
        </>
      )}
    </div>
  );
}

function GroupSelector({
  entryId,
  allowedGroups,
  onUpdate,
}: {
  entryId: string;
  allowedGroups: string[];
  onUpdate: (id: string, groups: string[]) => void;
}) {
  const { data: groups } = useQuery({
    queryKey: ["adminGroups"],
    queryFn: api.getGroups,
    staleTime: 60_000,
  });

  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>(allowedGroups);

  const toggle = (role: string) => {
    setSelected((prev) =>
      prev.includes(role) ? prev.filter((g) => g !== role) : [...prev, role],
    );
  };

  const handleSave = () => {
    onUpdate(entryId, selected);
    setOpen(false);
  };

  if (!groups || groups.length === 0) {
    return <span className="text-xs text-muted-foreground">No groups</span>;
  }

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {allowedGroups.length === 0 ? (
        <span className="text-xs text-muted-foreground">All groups</span>
      ) : (
        allowedGroups.slice(0, 2).map((g) => (
          <Badge key={g} variant="secondary" className="text-xs">
            {g}
          </Badge>
        ))
      )}
      {allowedGroups.length > 2 && (
        <span className="text-xs text-muted-foreground">
          +{allowedGroups.length - 2}
        </span>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-1 text-xs"
          onClick={() => {
            setSelected(allowedGroups);
            setOpen(true);
          }}
        >
          Edit
        </Button>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Assign Groups</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {groups.map((role) => (
              <div
                key={role}
                className="flex items-center justify-between rounded border px-3 py-2"
              >
                <span className="text-sm">{role}</span>
                <Switch
                  checked={selected.includes(role)}
                  onCheckedChange={() => toggle(role)}
                />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function Models() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: registry, isLoading } = useQuery({
    queryKey: ["modelRegistry"],
    queryFn: api.getModelRegistry,
  });

  const { data: manifest } = useQuery({
    queryKey: ["modelManifest"],
    queryFn: api.getModelManifest,
  });

  const [addOpen, setAddOpen] = useState(false);
  const [editEntry, setEditEntry] = useState<ModelRegistryEntry | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  type SortColumn =
    | "name"
    | "provider"
    | "model_id"
    | "model_type"
    | "cost_per_token"
    | "enabled";
  type SortDir = "asc" | "desc";

  const MODEL_TYPE_ORDER: Record<string, number> = {
    llm: 0,
    embedding: 1,
    reranker: 2,
    vision: 3,
  };

  const [sortCol, setSortCol] = useState<SortColumn>("model_type");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const handleSort = (col: SortColumn) => {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  };

  const sortedRegistry = [...(registry ?? [])].sort((a, b) => {
    let cmp = 0;
    switch (sortCol) {
      case "name":
        cmp = a.name.localeCompare(b.name);
        break;
      case "provider":
        cmp = a.provider.localeCompare(b.provider);
        break;
      case "model_id":
        cmp = a.model_id.localeCompare(b.model_id);
        break;
      case "model_type":
        cmp =
          (MODEL_TYPE_ORDER[a.model_type] ?? 99) -
          (MODEL_TYPE_ORDER[b.model_type] ?? 99);
        break;
      case "cost_per_token":
        cmp = (a.cost_per_token ?? -1) - (b.cost_per_token ?? -1);
        break;
      case "enabled":
        cmp = Number(b.enabled) - Number(a.enabled);
        break;
    }
    return sortDir === "asc" ? cmp : -cmp;
  });

  function SortableHeader({
    col,
    children,
  }: {
    col: SortColumn;
    children: React.ReactNode;
  }) {
    const active = sortCol === col;
    return (
      <button
        className="group flex items-center gap-1 hover:text-foreground"
        onClick={() => handleSort(col)}
      >
        {children}
        {active ? (
          sortDir === "asc" ? (
            <ArrowUp className="h-3 w-3" />
          ) : (
            <ArrowDown className="h-3 w-3" />
          )
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-0 group-hover:opacity-40" />
        )}
      </button>
    );
  }

  const createMutation = useMutation({
    mutationFn: (values: {
      name: string;
      provider: string;
      model_id: string;
      model_type: string;
      api_key_id?: string;
      new_api_key_value?: string;
      new_api_key_name?: string;
      cost_per_token?: number;
      enabled: boolean;
      ollama_host_id?: string;
    }) => api.createModel(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["modelRegistry"] });
      toast({ title: "Model added" });
      setAddOpen(false);
    },
    onError: (e) => {
      toast({
        title: "Failed to add model",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Partial<{
        name: string;
        api_key_id: string;
        new_api_key_value: string;
        new_api_key_name: string;
        cost_per_token: number;
        enabled: boolean;
        ollama_host_id: string;
      }>;
    }) => api.updateModel(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["modelRegistry"] });
      toast({ title: "Model updated" });
      setEditEntry(null);
    },
    onError: (e) => {
      toast({
        title: "Update failed",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteModel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["modelRegistry"] });
      toast({ title: "Model removed" });
    },
    onError: (e) => {
      toast({
        title: "Delete failed",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const groupsMutation = useMutation({
    mutationFn: ({ id, groups }: { id: string; groups: string[] }) =>
      api.updateModelGroups(id, groups),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["modelRegistry"] });
    },
    onError: (e) => {
      toast({
        title: "Failed to update groups",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      const result = await api.testModelConnectivity(id);
      if (result.ok) {
        toast({
          title: `Connected ${result.latency_ms != null ? `(${result.latency_ms}ms)` : ""}`,
        });
      } else {
        toast({
          title: `Failed: ${result.error ?? "unknown error"}`,
          variant: "destructive",
        });
      }
    } catch (e) {
      toast({
        title: "Test failed",
        description: (e as Error).message,
        variant: "destructive",
      });
    } finally {
      setTestingId(null);
    }
  };

  const handleAddSubmit = async (values: ModelFormValues) => {
    let finalApiKeyId = values.api_key_id;
    if (values.new_api_key_value) {
      try {
        const newKey = await api.createLlmApiKey(
          values.new_api_key_name || "New Key",
          values.new_api_key_value,
        );
        await queryClient.invalidateQueries({ queryKey: ["llmApiKeys"] });
        finalApiKeyId = newKey.id;
      } catch (e) {
        toast({
          title: "Failed to create API key",
          description: (e as Error).message,
          variant: "destructive",
        });
        return;
      }
    }
    const cost = values.cost_per_token
      ? parseFloat(values.cost_per_token)
      : undefined;
    createMutation.mutate({
      name: values.name,
      provider: values.provider,
      model_id: values.model_id,
      model_type: values.model_type,
      api_key_id: finalApiKeyId || undefined,
      cost_per_token: cost,
      enabled: values.enabled,
      ollama_host_id: values.ollama_host_id || undefined,
    });
  };

  const hasOllamaModels = registry?.some((e) => e.provider === "ollama");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Models</h2>
        <p className="text-muted-foreground">
          Manage LLM, embedding, reranker, and vision models.
        </p>
      </div>

      {hasOllamaModels && (
        <Card>
          <CardHeader>
            <CardTitle>Ollama Host</CardTitle>
            <CardDescription>
              Ollama host is configured per model. Set it in the model row
              actions.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Model Registry</h3>
        <Button onClick={() => setAddOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Model
        </Button>
      </div>

      {isLoading ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Loading models...
          </CardContent>
        </Card>
      ) : !registry || registry.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No models configured. Add a model to get started.
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <SortableHeader col="name">Name</SortableHeader>
                </TableHead>
                <TableHead>
                  <SortableHeader col="provider">Provider</SortableHeader>
                </TableHead>
                <TableHead>
                  <SortableHeader col="model_id">Model ID</SortableHeader>
                </TableHead>
                <TableHead>
                  <SortableHeader col="model_type">Type</SortableHeader>
                </TableHead>
                <TableHead>API Key</TableHead>
                <TableHead>
                  <SortableHeader col="cost_per_token">
                    Cost/token
                  </SortableHeader>
                </TableHead>
                <TableHead>
                  <SortableHeader col="enabled">Enabled</SortableHeader>
                </TableHead>
                <TableHead>Groups</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedRegistry.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="font-medium">{entry.name}</TableCell>
                  <TableCell>{entry.provider}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {entry.model_id}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{entry.model_type}</Badge>
                  </TableCell>
                  <TableCell>
                    <ApiKeyCell
                      entry={entry}
                      onSelectExisting={(id) =>
                        updateMutation.mutate({
                          id: entry.id,
                          data: { api_key_id: id },
                        })
                      }
                      onClear={() =>
                        updateMutation.mutate({
                          id: entry.id,
                          data: { api_key_id: CLEAR_API_KEY },
                        })
                      }
                      onCreate={async (name, apiKey) => {
                        try {
                          const newKey = await api.createLlmApiKey(
                            name,
                            apiKey,
                          );
                          await queryClient.invalidateQueries({
                            queryKey: ["llmApiKeys"],
                          });
                          updateMutation.mutate({
                            id: entry.id,
                            data: { api_key_id: newKey.id },
                          });
                        } catch (e) {
                          toast({
                            title: "Failed to create API key",
                            description: (e as Error).message,
                            variant: "destructive",
                          });
                        }
                      }}
                      isPending={updateMutation.isPending}
                    />
                  </TableCell>
                  <TableCell className="text-xs">
                    {entry.cost_per_token != null
                      ? entry.cost_per_token.toExponential(2)
                      : "—"}
                  </TableCell>
                  <TableCell>
                    {entry.provider === "ollama" && !entry.ollama_host_id ? (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="inline-flex cursor-not-allowed">
                              <Switch
                                checked={entry.enabled}
                                disabled
                                className="pointer-events-none"
                              />
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>
                            Assign a host to this model before enabling it.
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    ) : entry.provider !== "ollama" && !entry.api_key_id ? (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="inline-flex cursor-not-allowed">
                              <Switch
                                checked={entry.enabled}
                                disabled
                                className="pointer-events-none"
                              />
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>
                            Assign an API key to this model before enabling it.
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    ) : (
                      <Switch
                        checked={entry.enabled}
                        onCheckedChange={(v) =>
                          updateMutation.mutate({
                            id: entry.id,
                            data: { enabled: v },
                          })
                        }
                        disabled={
                          entry.env_override || updateMutation.isPending
                        }
                      />
                    )}
                  </TableCell>
                  <TableCell>
                    {entry.model_type === "llm" ? (
                      <GroupSelector
                        entryId={entry.id}
                        allowedGroups={entry.allowed_groups ?? []}
                        onUpdate={(id, groups) =>
                          groupsMutation.mutate({ id, groups })
                        }
                      />
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <TooltipProvider>
                      <div className="flex items-center justify-end gap-1">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              aria-label="Test connectivity"
                              onClick={() => handleTest(entry.id)}
                              disabled={testingId === entry.id}
                            >
                              {testingId === entry.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <CheckCircle2 className="h-4 w-4" />
                              )}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Test connectivity</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              aria-label={`Edit ${entry.name}`}
                              onClick={() => setEditEntry(entry)}
                              disabled={entry.env_override}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Edit model</TooltipContent>
                        </Tooltip>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-destructive hover:text-destructive"
                              aria-label={`Delete ${entry.name}`}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Remove model?</AlertDialogTitle>
                              <AlertDialogDescription>
                                Remove {entry.name}? This cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => deleteMutation.mutate(entry.id)}
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              >
                                Remove
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </TooltipProvider>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <ModelDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        manifest={manifest}
        registry={registry}
        onSubmit={handleAddSubmit}
        isPending={createMutation.isPending}
        title="Add Model"
      />

      {editEntry && (
        <ModelDialog
          open={!!editEntry}
          onOpenChange={(v) => !v && setEditEntry(null)}
          initial={{
            name: editEntry.name,
            provider: editEntry.provider,
            model_id: editEntry.model_id,
            model_type: editEntry.model_type,
            cost_per_token: editEntry.cost_per_token?.toString() ?? "",
            enabled: editEntry.enabled,
            ollama_host_id: editEntry.ollama_host_id ?? "",
            api_key_id: editEntry.api_key_id ?? "",
          }}
          manifest={manifest}
          registry={registry}
          onSubmit={async (values) => {
            let finalApiKeyId = values.api_key_id;
            if (values.new_api_key_value) {
              try {
                const newKey = await api.createLlmApiKey(
                  values.new_api_key_name || "New Key",
                  values.new_api_key_value,
                );
                await queryClient.invalidateQueries({
                  queryKey: ["llmApiKeys"],
                });
                finalApiKeyId = newKey.id;
              } catch (e) {
                toast({
                  title: "Failed to create API key",
                  description: (e as Error).message,
                  variant: "destructive",
                });
                return;
              }
            }
            const cost = values.cost_per_token
              ? parseFloat(values.cost_per_token)
              : undefined;
            updateMutation.mutate({
              id: editEntry.id,
              data: {
                name: values.name,
                api_key_id: finalApiKeyId || undefined,
                cost_per_token: cost,
                enabled: values.enabled,
                ollama_host_id: values.ollama_host_id || undefined,
              },
            });
          }}
          isPending={updateMutation.isPending}
          title="Edit Model"
        />
      )}
    </div>
  );
}
