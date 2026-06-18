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
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { api } from "@/api/client";
import type {
  ModelManifest,
  ModelRegistryEntry,
  OllamaModel,
} from "@/api/client";
import { Combobox } from "@/components/ui/combobox";
import { useToast } from "@/hooks/use-toast";

interface ModelFormValues {
  name: string;
  provider: string;
  model_id: string;
  model_type: string;
  api_key: string;
  cost_per_token: string;
  enabled: boolean;
  ollama_host: string;
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
    api_key: "",
    cost_per_token: initial?.cost_per_token ?? "",
    enabled: defaultEnabled(initial?.model_type ?? "llm"),
    ollama_host: initial?.ollama_host ?? "",
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
  const { data: ollamaModels, isFetching: ollamaFetching } = useQuery({
    queryKey: ["ollamaModels", form.ollama_host],
    queryFn: () => api.listOllamaModels(form.ollama_host || undefined),
    enabled: isOllama && form.ollama_host.length > 0,
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

          {isValidProvider && (
            <>
              {isOllama && (
                <div className="space-y-1">
                  <Label>Ollama Host</Label>
                  <Input
                    value={form.ollama_host}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, ollama_host: e.target.value }))
                    }
                    placeholder="http://localhost:11434"
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
                      onChange={(v) => setForm((f) => ({ ...f, model_id: v }))}
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
                          : form.ollama_host
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
                <div className="space-y-1">
                  <Label>API Key</Label>
                  <Input
                    type="password"
                    value={form.api_key}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, api_key: e.target.value }))
                    }
                    placeholder="Optional"
                  />
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
              isPending || !isValidProvider || !bareModelId || !form.name
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

function ApiKeyCell({
  entry,
  onUpdate,
  isPending,
}: {
  entry: ModelRegistryEntry;
  onUpdate: (id: string, apiKey: string) => void;
  isPending: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");

  if (entry.env_override) {
    return (
      <div className="flex items-center gap-1 text-yellow-600">
        <Lock className="h-3 w-3" />
        <span className="text-xs">ENV override</span>
      </div>
    );
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <Input
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="h-7 w-32 text-xs"
          placeholder="New key"
          autoFocus
        />
        <Button
          size="sm"
          className="h-7 px-2 text-xs"
          onClick={() => {
            onUpdate(entry.id, value);
            setEditing(false);
            setValue("");
          }}
          disabled={!value || isPending}
        >
          Save
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-xs"
          onClick={() => {
            setEditing(false);
            setValue("");
          }}
        >
          Cancel
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <span className="text-xs text-muted-foreground">
        {entry.api_key_set ? "••••••••" : "Not set"}
      </span>
      <Button
        variant="ghost"
        size="sm"
        className="h-6 px-2 text-xs"
        onClick={() => setEditing(true)}
      >
        {entry.api_key_set ? "Update" : "Set key"}
      </Button>
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
      api_key?: string;
      cost_per_token?: number;
      enabled: boolean;
      ollama_host?: string;
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
        api_key: string;
        cost_per_token: number;
        enabled: boolean;
        ollama_host: string;
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

  const handleAddSubmit = (values: ModelFormValues) => {
    const cost = values.cost_per_token
      ? parseFloat(values.cost_per_token)
      : undefined;
    createMutation.mutate({
      name: values.name,
      provider: values.provider,
      model_id: values.model_id,
      model_type: values.model_type,
      api_key: values.api_key || undefined,
      cost_per_token: cost,
      enabled: values.enabled,
      ollama_host: values.ollama_host || undefined,
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
                      onUpdate={(id, apiKey) =>
                        updateMutation.mutate({ id, data: { api_key: apiKey } })
                      }
                      isPending={updateMutation.isPending}
                    />
                  </TableCell>
                  <TableCell className="text-xs">
                    {entry.cost_per_token != null
                      ? entry.cost_per_token.toExponential(2)
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={entry.enabled}
                      onCheckedChange={(v) =>
                        updateMutation.mutate({
                          id: entry.id,
                          data: { enabled: v },
                        })
                      }
                      disabled={entry.env_override || updateMutation.isPending}
                    />
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
            ollama_host: editEntry.ollama_host ?? "",
          }}
          manifest={manifest}
          registry={registry}
          onSubmit={(values) => {
            const cost = values.cost_per_token
              ? parseFloat(values.cost_per_token)
              : undefined;
            updateMutation.mutate({
              id: editEntry.id,
              data: {
                name: values.name,
                api_key: values.api_key || undefined,
                cost_per_token: cost,
                enabled: values.enabled,
                ollama_host: values.ollama_host || undefined,
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
