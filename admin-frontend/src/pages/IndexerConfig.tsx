import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Download, Upload } from "lucide-react";
import { stringify as yamlStringify, parse as yamlParse } from "yaml";
import Editor from "@monaco-editor/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
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
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/api/client";
import { useConfigStore } from "@/stores/configStore";

const getDefaultConfig = (
  schema: Record<string, unknown> | undefined,
): Record<string, unknown> => {
  if (!schema?.properties) {
    return {
      data_dir: "output",
      source: "disk",
      state_index: "harmony-crawl-state",
      sync_deletions: false,
      missing_threshold: 3,
      batch_size: 100,
      es_host: "http://localhost:9200",
      index_base_name: "harmony",
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

  return defaults;
};

export function IndexerConfig() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { selectedIndexerConfig, setSelectedIndexerConfig } = useConfigStore();

  const [yamlContent, setYamlContent] = useState("");
  const [yamlError, setYamlError] = useState<string | null>(null);
  const [newConfigName, setNewConfigName] = useState("");
  const [showNewDialog, setShowNewDialog] = useState(false);

  const { data: configs, isLoading: configsLoading } = useQuery({
    queryKey: ["indexerConfigs"],
    queryFn: () => api.listIndexerConfigs(),
  });

  const { data: schema } = useQuery({
    queryKey: ["indexerSchema"],
    queryFn: () => api.getIndexerSchema(),
  });

  const [config, setConfig] = useState<Record<string, unknown>>(() =>
    getDefaultConfig(schema),
  );

  const { data: loadedConfig, isLoading: configLoading } = useQuery({
    queryKey: ["indexerConfig", selectedIndexerConfig],
    queryFn: () => api.getIndexerConfig(selectedIndexerConfig!),
    enabled: !!selectedIndexerConfig,
  });

  useEffect(() => {
    if (loadedConfig) {
      setConfig(loadedConfig);
      setYamlContent(yamlStringify(loadedConfig, { sortKeys: false }));
    }
  }, [loadedConfig]);

  useEffect(() => {
    try {
      setYamlContent(yamlStringify(config, { sortKeys: false }));
      setYamlError(null);
    } catch {
      // Keep existing content
    }
  }, [config]);

  const handleYamlChange = (value: string) => {
    setYamlContent(value);
    try {
      const parsed = yamlParse(value);
      setConfig(parsed);
      setYamlError(null);
    } catch (e) {
      setYamlError(e instanceof Error ? e.message : "Invalid YAML");
    }
  };

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
      const defaultConfig = getDefaultConfig(schema);
      setConfig(defaultConfig);
      setYamlContent(yamlStringify(defaultConfig, { sortKeys: false }));
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
    },
    onError: (error) => {
      toast({
        title: "Start failed",
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
      setYamlContent(yamlStringify(defaultConfig, { sortKeys: false }));
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

  const updateConfig = (key: string, value: unknown) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  if (configsLoading) {
    return <div>Loading...</div>;
  }

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
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardContent className="flex items-end gap-4">
          <div className="flex-1">
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
            <Button variant="outline" onClick={handleExport}>
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
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

          <div className="flex-1"></div>

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

      {/* Config Form */}
      {selectedIndexerConfig && (
        <>
          {configLoading ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                Loading configuration...
              </CardContent>
            </Card>
          ) : (
            <Tabs defaultValue="form">
              <div className="flex items-center justify-between mb-4">
                <TabsList>
                  <TabsTrigger value="form">Form</TabsTrigger>
                  <TabsTrigger value="yaml">YAML</TabsTrigger>
                </TabsList>

                <div className="flex gap-2">
                  <Button
                    onClick={() => saveMutation.mutate()}
                    disabled={saveMutation.isPending || !!yamlError}
                  >
                    {saveMutation.isPending ? "Saving..." : "Save"}
                  </Button>
                  <Button
                    onClick={() => runMutation.mutate()}
                    disabled={runMutation.isPending || !!yamlError}
                    variant="secondary"
                  >
                    {runMutation.isPending ? "Starting..." : "Run Index"}
                  </Button>
                </div>
              </div>

              <TabsContent value="form" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Data Source</CardTitle>
                    <CardDescription>
                      Where to read crawled data from
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label>Data Directory</Label>
                      <Input
                        value={(config.data_dir as string) || ""}
                        onChange={(e) =>
                          updateConfig("data_dir", e.target.value)
                        }
                        placeholder="output"
                      />
                      <p className="text-xs text-muted-foreground">
                        Directory containing crawled files
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label>Source</Label>
                      <Select
                        value={(config.source as string) || "disk"}
                        onValueChange={(v) => updateConfig("source", v)}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="disk">
                            Disk (metadata.jsonl)
                          </SelectItem>
                          <SelectItem value="elasticsearch">
                            Elasticsearch State
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label>State Index</Label>
                      <Input
                        value={(config.state_index as string) || ""}
                        onChange={(e) =>
                          updateConfig("state_index", e.target.value)
                        }
                      />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Elasticsearch</CardTitle>
                    <CardDescription>
                      Target Elasticsearch settings
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label>ES Host</Label>
                      <Input
                        value={(config.es_host as string) || ""}
                        onChange={(e) =>
                          updateConfig("es_host", e.target.value)
                        }
                        placeholder="http://localhost:9200"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label>Index Base Name</Label>
                      <Input
                        value={(config.index_base_name as string) || ""}
                        onChange={(e) =>
                          updateConfig("index_base_name", e.target.value)
                        }
                        placeholder="harmony"
                      />
                      <p className="text-xs text-muted-foreground">
                        Indices will be named: base-language (e.g., harmony-en)
                      </p>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Processing</CardTitle>
                    <CardDescription>Index processing options</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label>Batch Size</Label>
                      <Input
                        type="number"
                        value={(config.batch_size as number) || 100}
                        onChange={(e) =>
                          updateConfig("batch_size", parseInt(e.target.value))
                        }
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <Label>Sync Deletions</Label>
                        <p className="text-xs text-muted-foreground">
                          Delete documents missing from crawl state
                        </p>
                      </div>
                      <Switch
                        checked={(config.sync_deletions as boolean) || false}
                        onCheckedChange={(v) =>
                          updateConfig("sync_deletions", v)
                        }
                      />
                    </div>

                    <div className="space-y-2">
                      <Label>Missing Threshold</Label>
                      <Input
                        type="number"
                        value={(config.missing_threshold as number) || 3}
                        onChange={(e) =>
                          updateConfig(
                            "missing_threshold",
                            parseInt(e.target.value),
                          )
                        }
                      />
                      <p className="text-xs text-muted-foreground">
                        Number of crawls before deletion
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="yaml">
                <Card>
                  <CardHeader>
                    <CardTitle>YAML Configuration</CardTitle>
                    <CardDescription>
                      Edit configuration as YAML
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {yamlError && (
                      <div className="mb-2 p-2 bg-destructive/10 border border-destructive rounded">
                        <p className="text-sm text-destructive font-semibold">
                          Syntax Error:
                        </p>
                        <p className="text-sm text-destructive">{yamlError}</p>
                      </div>
                    )}
                    <div className="border rounded-md overflow-visible">
                      <Editor
                        height="500px"
                        defaultLanguage="yaml"
                        value={yamlContent}
                        onChange={(value) => {
                          if (value === undefined) return;
                          handleYamlChange(value);
                        }}
                        theme="light"
                        options={{
                          minimap: { enabled: false },
                          fontSize: 13,
                          lineNumbers: "on",
                          scrollBeyondLastLine: false,
                          wordWrap: "on",
                          automaticLayout: true,
                          hover: {
                            above: false,
                          },
                        }}
                      />
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
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
