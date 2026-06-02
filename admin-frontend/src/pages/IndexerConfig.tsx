import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Download, Upload, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { Card, CardContent } from "@/components/ui/card";
import { ConfigForm } from "@/components/config/ConfigForm";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/api/client";
import { useConfigStore } from "@/stores/configStore";

const INDEXER_EXTRA_SCHEMA_PATCH: Record<string, unknown> = {
  skip_embedding: {
    type: "boolean",
    default: false,
    title: "Skip Embedding",
    description:
      "Skip vector embedding generation (index to Elasticsearch only)",
  },
  qdrant_host: {
    type: "string",
    default: "",
    title: "Qdrant Host",
    description: "URL of the Qdrant server for vector storage",
  },
  qdrant_collection: {
    type: "string",
    default: "harmony",
    title: "Qdrant Collection",
    description: "Name of the Qdrant collection to store vectors",
  },
  embedding_batch_size: {
    type: "integer",
    default: 64,
    title: "Embedding Batch Size",
    description: "Number of documents to embed per batch",
  },
  languages: {
    type: "array",
    items: { type: "string" },
    default: ["en"],
    title: "Languages",
    description: "Language codes to index (e.g. en, fr, de)",
  },
};

const getDefaultConfig = (
  schema: Record<string, unknown> | undefined,
): Record<string, unknown> => {
  if (!schema?.properties) {
    return {
      data_dir: "output",
      source: "disk",
      sync_deletions: false,
      missing_threshold: 3,
      batch_size: 100,
      es_host: "http://localhost:9200",
      index_base_name: "harmony",
      verbose: 0,
      skip_embedding: false,
      qdrant_host: "",
      qdrant_collection: "harmony",
      embedding_batch_size: 64,
      languages: ["en"],
    };
  }

  const defaults: Record<string, unknown> = {};
  const properties = schema.properties as Record<string, unknown>;

  Object.entries(properties).forEach(([key, propSchema]) => {
    const prop = propSchema as Record<string, unknown>;
    if ("default" in prop) {
      defaults[key] = prop.default;
    }
  });

  Object.entries(INDEXER_EXTRA_SCHEMA_PATCH).forEach(([key, propSchema]) => {
    const prop = propSchema as Record<string, unknown>;
    if (!defaults[key] && "default" in prop) {
      defaults[key] = prop.default;
    }
  });

  return defaults;
};

function patchSchema(
  schema: Record<string, unknown> | undefined,
): Record<string, unknown> {
  if (!schema) return { properties: INDEXER_EXTRA_SCHEMA_PATCH };
  const properties = {
    ...((schema.properties as Record<string, unknown>) ?? {}),
    ...INDEXER_EXTRA_SCHEMA_PATCH,
  };
  return { ...schema, properties };
}

export function IndexerConfig() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { selectedIndexerConfig, setSelectedIndexerConfig } = useConfigStore();

  const [newConfigName, setNewConfigName] = useState("");
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [duplicateName, setDuplicateName] = useState("");
  const [recreateWarning, setRecreateWarning] = useState<string | null>(null);

  const { data: configs } = useQuery({
    queryKey: ["indexerConfigs"],
    queryFn: () => api.listIndexerConfigs(),
  });

  const { data: schema } = useQuery({
    queryKey: ["indexerSchema"],
    queryFn: () => api.getIndexerSchema(),
  });

  const patchedSchema = patchSchema(schema);

  const [config, setConfig] = useState<Record<string, unknown>>(() =>
    getDefaultConfig(schema),
  );

  const {
    data: loadedConfig,
    isLoading: configLoading,
    isError: configError,
  } = useQuery({
    queryKey: ["indexerConfig", selectedIndexerConfig],
    queryFn: () => api.getIndexerConfig(selectedIndexerConfig!),
    enabled: !!selectedIndexerConfig,
  });

  useEffect(() => {
    if (loadedConfig) {
      setConfig(loadedConfig);
    }
  }, [loadedConfig]);

  useEffect(() => {
    if (configError) setSelectedIndexerConfig(null);
  }, [configError, setSelectedIndexerConfig]);

  const saveMutation = useMutation({
    mutationFn: () => api.saveIndexerConfig(selectedIndexerConfig!, config),
    onSuccess: () => {
      toast({ title: "Config saved" });
      queryClient.invalidateQueries({ queryKey: ["indexerConfigs"] });
    },
    onError: (error) => {
      toast({
        title: "Save failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteIndexerConfig(selectedIndexerConfig!),
    onSuccess: () => {
      toast({ title: "Config deleted" });
      setSelectedIndexerConfig(null);
      setConfig(getDefaultConfig(schema));
      queryClient.invalidateQueries({ queryKey: ["indexerConfigs"] });
    },
    onError: (error) => {
      toast({
        title: "Delete failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const runMutation = useMutation({
    mutationFn: () => api.startIndexJob(selectedIndexerConfig!),
    onSuccess: (job) => {
      toast({ title: "Index job started", description: `Job ID: ${job.id}` });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      setRecreateWarning(null);
    },
    onError: (error) => {
      toast({
        title: "Start failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleRunIndex = async () => {
    try {
      const preflight = await api.indexPreflight();
      if (preflight.needs_recreate) {
        setRecreateWarning(preflight.reason);
      } else {
        runMutation.mutate();
      }
    } catch {
      runMutation.mutate();
    }
  };

  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [renameConfigName, setRenameConfigName] = useState("");

  const renameMutation = useMutation({
    mutationFn: () =>
      api.renameIndexerConfig(selectedIndexerConfig!, renameConfigName),
    onSuccess: (newConfig) => {
      toast({ title: "Config renamed" });
      setRenameDialogOpen(false);
      setRenameConfigName("");
      setSelectedIndexerConfig(newConfig.name);
      queryClient.invalidateQueries({ queryKey: ["indexerConfigs"] });
    },
    onError: (error) => {
      toast({
        title: "Rename failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: () =>
      api.saveIndexerConfig(
        duplicateName,
        config,
        `Copy of ${selectedIndexerConfig}`,
      ),
    onSuccess: (newConfig) => {
      toast({
        title: "Config duplicated",
        description: `Saved as ${newConfig.name}`,
      });
      setDuplicateDialogOpen(false);
      setDuplicateName("");
      setSelectedIndexerConfig(newConfig.name);
      queryClient.invalidateQueries({ queryKey: ["indexerConfigs"] });
    },
    onError: (error) => {
      toast({
        title: "Duplicate failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleCreateNew = async () => {
    if (!newConfigName.trim()) return;
    try {
      const defaultConfig = getDefaultConfig(schema);
      await api.saveIndexerConfig(newConfigName, defaultConfig);
      setSelectedIndexerConfig(newConfigName);
      setConfig(defaultConfig);
      setShowNewDialog(false);
      setNewConfigName("");
      queryClient.invalidateQueries({ queryKey: ["indexerConfigs"] });
      toast({ title: "Configuration created" });
    } catch (error) {
      toast({
        title: "Create failed",
        description: (error as Error).message,
        variant: "destructive",
      });
    }
  };

  const handleExport = async () => {
    if (!selectedIndexerConfig) return;
    try {
      const result = await api.exportIndexerConfig(selectedIndexerConfig);
      const blob = new Blob([result.yaml_content], {
        type: "application/x-yaml",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${selectedIndexerConfig}.yaml`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast({
        title: "Export failed",
        description: (error as Error).message,
        variant: "destructive",
      });
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(
        `/api/configs/indexer/import?name=${file.name.replace(".yaml", "").replace(".yml", "")}`,
        {
          method: "POST",
          body: formData,
        },
      );

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({ detail: "Import failed" }));
        throw new Error(error.detail || "Import failed");
      }

      const result = await response.json();
      toast({
        title: "Config imported",
        description: `Saved as: ${result.name}`,
      });
      queryClient.invalidateQueries({ queryKey: ["indexerConfigs"] });
      setSelectedIndexerConfig(result.name);
    } catch (error) {
      toast({
        title: "Import failed",
        description: (error as Error).message,
        variant: "destructive",
      });
    }

    e.target.value = "";
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">
          Indexer Configuration
        </h2>
        <p className="text-muted-foreground">
          Configure Elasticsearch indexing settings
        </p>
      </div>

      {/* Config Selector */}
      <Card>
        <CardContent className="pt-6 flex items-end gap-4 flex-wrap">
          <div className="flex-1 min-w-48">
            <Label>Select Configuration</Label>
            <Select
              value={selectedIndexerConfig || ""}
              onValueChange={(value) => setSelectedIndexerConfig(value || null)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a configuration..." />
              </SelectTrigger>
              <SelectContent>
                {configs?.configs.map((c) => (
                  <SelectItem key={c.name} value={c.name}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <AlertDialog open={showNewDialog} onOpenChange={setShowNewDialog}>
            <AlertDialogTrigger asChild>
              <Button variant="outline">
                <Plus className="mr-2 h-4 w-4" />
                New
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Create New Configuration</AlertDialogTitle>
                <AlertDialogDescription>
                  Enter a name for the new configuration.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <Input
                value={newConfigName}
                onChange={(e) => setNewConfigName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newConfigName.trim()) {
                    e.preventDefault();
                    handleCreateNew();
                  }
                }}
                placeholder="config-name"
                autoFocus
              />
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleCreateNew}>
                  Create
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          {selectedIndexerConfig && (
            <>
              <AlertDialog
                open={renameDialogOpen}
                onOpenChange={setRenameDialogOpen}
              >
                <AlertDialogTrigger asChild>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setRenameConfigName(selectedIndexerConfig);
                      setRenameDialogOpen(true);
                    }}
                  >
                    Rename
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Rename Configuration</AlertDialogTitle>
                    <AlertDialogDescription>
                      Enter a new name for "{selectedIndexerConfig}".
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <Input
                    value={renameConfigName}
                    onChange={(e) => setRenameConfigName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && renameConfigName.trim()) {
                        e.preventDefault();
                        renameMutation.mutate();
                      }
                    }}
                    placeholder="new-name"
                    autoFocus
                  />
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={() => renameMutation.mutate()}>
                      Rename
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>

              <Dialog
                open={duplicateDialogOpen}
                onOpenChange={setDuplicateDialogOpen}
              >
                <Button
                  variant="outline"
                  onClick={() => {
                    setDuplicateName(`${selectedIndexerConfig}-copy`);
                    setDuplicateDialogOpen(true);
                  }}
                >
                  <Copy className="mr-2 h-4 w-4" />
                  Duplicate
                </Button>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Duplicate Configuration</DialogTitle>
                  </DialogHeader>
                  <Input
                    value={duplicateName}
                    onChange={(e) => setDuplicateName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && duplicateName.trim()) {
                        e.preventDefault();
                        duplicateMutation.mutate();
                      }
                    }}
                    placeholder="new-config-name"
                    autoFocus
                  />
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => setDuplicateDialogOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={() => duplicateMutation.mutate()}
                      disabled={
                        !duplicateName.trim() || duplicateMutation.isPending
                      }
                    >
                      Duplicate
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              <Button variant="outline" onClick={handleExport}>
                <Download className="mr-2 h-4 w-4" />
                Export
              </Button>
            </>
          )}

          <div>
            <Label htmlFor="import-indexer" className="cursor-pointer">
              <Button variant="outline" asChild>
                <span>
                  <Upload className="mr-2 h-4 w-4" />
                  Import
                </span>
              </Button>
            </Label>
            <input
              id="import-indexer"
              type="file"
              accept=".yaml,.yml"
              onChange={handleImport}
              className="hidden"
            />
          </div>

          <div className="flex-1" />

          {selectedIndexerConfig && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete Configuration</AlertDialogTitle>
                  <AlertDialogDescription>
                    Are you sure you want to delete "{selectedIndexerConfig}"?
                    This cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={() => deleteMutation.mutate()}>
                    Delete
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </CardContent>
      </Card>

      {selectedIndexerConfig && (
        <>
          {configLoading ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                Loading configuration...
              </CardContent>
            </Card>
          ) : (
            <>
              <ConfigForm
                schema={patchedSchema}
                config={config}
                onChange={setConfig}
                onSave={() => saveMutation.mutate()}
                onRun={handleRunIndex}
                isSaving={saveMutation.isPending}
                isRunning={runMutation.isPending}
              />

              <AlertDialog
                open={!!recreateWarning}
                onOpenChange={(open) => !open && setRecreateWarning(null)}
              >
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>
                      Recreate vector collection?
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                      {recreateWarning}. All existing vectors will be deleted
                      and re-embedded from scratch.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={() => runMutation.mutate()}>
                      Recreate and index
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </>
          )}
        </>
      )}

      {!selectedIndexerConfig && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Select a configuration or create a new one to get started.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
