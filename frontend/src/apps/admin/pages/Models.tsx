import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";
import { api } from "@/shared/api/client";
import type { ModelRegistryEntry } from "@/shared/api/client";
import { useToast } from "@/shared/hooks/use-toast";
import { useApiKeyCreation } from "@/shared/hooks/useApiKeyCreation";
import {
  ModelDialog,
  type ModelFormValues,
} from "@/apps/admin/components/models/ModelDialog";
import {
  ApiKeyCell,
  CLEAR_API_KEY,
} from "@/apps/admin/components/models/ApiKeyCell";
import { GroupSelector } from "@/apps/admin/components/models/GroupSelector";

export function Models() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { createKey } = useApiKeyCreation();

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
        const newKey = await createKey(
          values.new_api_key_name || "New Key",
          values.new_api_key_value,
        );
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
                          const newKey = await createKey(name, apiKey);
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
                const newKey = await createKey(
                  values.new_api_key_name || "New Key",
                  values.new_api_key_value,
                );
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
