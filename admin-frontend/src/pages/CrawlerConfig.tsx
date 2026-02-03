import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Download, Upload } from "lucide-react";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfigForm } from "@/components/config/ConfigForm";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/api/client";
import { useConfigStore } from "@/stores/configStore";

const getDefaultConfig = (
  schema: Record<string, unknown> | undefined,
): Record<string, unknown> => {
  if (!schema?.properties) {
    return {
      start_urls: [],
      output: "output",
      max_depth: 100,
      delay: 1.0,
      concurrent: 5,
      domain_routing: { exact: {}, patterns: [], default: "generic" },
      spider_settings: {
        docs: {
          skip_versions: false,
          version_allowlist: [],
          deny_patterns: [],
        },
        drupal: { deny_patterns: [] },
        generic: { deny_patterns: [] },
      },
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

  // Ensure nested objects have defaults even if schema doesn't expose them directly
  if (!defaults.domain_routing) {
    defaults.domain_routing = { exact: {}, patterns: [], default: "generic" };
  }
  if (!defaults.spider_settings) {
    defaults.spider_settings = {
      docs: { skip_versions: false, version_allowlist: [], deny_patterns: [] },
      drupal: { deny_patterns: [] },
      generic: { deny_patterns: [] },
    };
  }

  return defaults;
};

export function CrawlerConfig() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { selectedCrawlerConfig, setSelectedCrawlerConfig } = useConfigStore();

  const [newConfigName, setNewConfigName] = useState("");
  const [showNewDialog, setShowNewDialog] = useState(false);

  const { data: configs, isLoading: configsLoading } = useQuery({
    queryKey: ["crawlerConfigs"],
    queryFn: () => api.listCrawlerConfigs(),
  });

  const { data: schema } = useQuery({
    queryKey: ["crawlerSchema"],
    queryFn: () => api.getCrawlerSchema(),
  });

  const [config, setConfig] = useState<Record<string, unknown>>(() =>
    getDefaultConfig(schema),
  );

  const { data: loadedConfig, isLoading: configLoading } = useQuery({
    queryKey: ["crawlerConfig", selectedCrawlerConfig],
    queryFn: () => api.getCrawlerConfig(selectedCrawlerConfig!),
    enabled: !!selectedCrawlerConfig,
  });

  useEffect(() => {
    if (loadedConfig) {
      setConfig(loadedConfig);
    }
  }, [loadedConfig]);

  const saveMutation = useMutation({
    mutationFn: () => api.saveCrawlerConfig(selectedCrawlerConfig!, config),
    onSuccess: () => {
      toast({ title: "Config saved" });
      queryClient.invalidateQueries({ queryKey: ["crawlerConfigs"] });
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
    mutationFn: () => api.deleteCrawlerConfig(selectedCrawlerConfig!),
    onSuccess: () => {
      toast({ title: "Config deleted" });
      setSelectedCrawlerConfig(null);
      setConfig(getDefaultConfig(schema));
      queryClient.invalidateQueries({ queryKey: ["crawlerConfigs"] });
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
    mutationFn: () => api.startCrawlJob(selectedCrawlerConfig!),
    onSuccess: (job) => {
      toast({ title: "Crawl started", description: `Job ID: ${job.id}` });
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
      await api.saveCrawlerConfig(newConfigName, defaultConfig);
      setSelectedCrawlerConfig(newConfigName);
      setConfig(defaultConfig);
      setShowNewDialog(false);
      setNewConfigName("");
      queryClient.invalidateQueries({ queryKey: ["crawlerConfigs"] });
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
    if (!selectedCrawlerConfig) return;

    try {
      const result = await api.exportCrawlerConfig(selectedCrawlerConfig);
      const blob = new Blob([result.yaml_content], {
        type: "application/x-yaml",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${selectedCrawlerConfig}.yaml`;
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
        `/api/configs/crawler/import?name=${file.name.replace(".yaml", "").replace(".yml", "")}`,
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
      queryClient.invalidateQueries({ queryKey: ["crawlerConfigs"] });
      setSelectedCrawlerConfig(result.name);
    } catch (error) {
      toast({
        title: "Import failed",
        description: (error as Error).message,
        variant: "destructive",
      });
    }

    e.target.value = "";
  };

  if (configsLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">
          Crawler Configuration
        </h2>
        <p className="text-muted-foreground">Configure web crawling settings</p>
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
              value={selectedCrawlerConfig || ""}
              onValueChange={(value) => setSelectedCrawlerConfig(value || null)}
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

          {selectedCrawlerConfig && (
            <Button variant="outline" onClick={handleExport}>
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
          )}

          <div>
            <Label htmlFor="import" className="cursor-pointer">
              <Button variant="outline" asChild>
                <span>
                  <Upload className="mr-2 h-4 w-4" />
                  Import
                </span>
              </Button>
            </Label>
            <input
              id="import"
              type="file"
              accept=".yaml,.yml"
              onChange={handleImport}
              className="hidden"
            />
          </div>

          <div className="flex-1"></div>

          {selectedCrawlerConfig && (
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
                    Are you sure you want to delete "{selectedCrawlerConfig}"?
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
      {selectedCrawlerConfig && (
        <>
          {configLoading || !schema ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                Loading configuration...
              </CardContent>
            </Card>
          ) : (
            <ConfigForm
              schema={schema}
              config={config}
              onChange={setConfig}
              onSave={() => saveMutation.mutate()}
              onRun={() => runMutation.mutate()}
              isSaving={saveMutation.isPending}
              isRunning={runMutation.isPending}
            />
          )}
        </>
      )}

      {!selectedCrawlerConfig && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Select a configuration or create a new one to get started.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
