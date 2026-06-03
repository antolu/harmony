import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { ConfigForm } from "@/components/config/ConfigForm";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/api/client";

const INDEXER_HIDDEN_FIELDS = new Set([
  "data_dir",
  "source",
  "es_config",
  "verbose",
]);

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
    description: "Qdrant collection name for vector storage",
  },
  embedding_model: {
    type: "string",
    default: "",
    title: "Embedding Model",
    description: "LiteLLM model ID for generating embeddings",
  },
  embedding_batch_size: {
    type: "integer",
    default: 64,
    title: "Embedding Batch Size",
    description: "Number of documents to embed per batch",
  },
  languages: {
    type: "string",
    default: "en",
    title: "Languages",
    description: "Comma-separated language codes to index (e.g. en,fr,de)",
  },
};

function patchSchema(
  schema: Record<string, unknown> | undefined,
): Record<string, unknown> {
  if (!schema) return { properties: INDEXER_EXTRA_SCHEMA_PATCH };
  const merged = {
    ...((schema.properties as Record<string, unknown>) ?? {}),
    ...INDEXER_EXTRA_SCHEMA_PATCH,
  };
  const filtered = Object.fromEntries(
    Object.entries(merged).filter(([k]) => !INDEXER_HIDDEN_FIELDS.has(k)),
  );
  return { ...schema, properties: filtered };
}

function getDefaultConfig(
  schema: Record<string, unknown> | undefined,
): Record<string, unknown> {
  if (!schema) return {};
  const props =
    (schema.properties as Record<string, { default?: unknown }>) ?? {};
  return Object.fromEntries(
    Object.entries(props)
      .filter(([k]) => !INDEXER_HIDDEN_FIELDS.has(k))
      .map(([k, v]) => [k, v.default ?? ""]),
  );
}

export function IndexerConfig() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: schema } = useQuery({
    queryKey: ["indexerSchema"],
    queryFn: () => api.getIndexerSchema(),
  });

  const patchedSchema = patchSchema(schema);

  const [config, setConfig] = useState<Record<string, unknown>>(() =>
    getDefaultConfig(schema),
  );

  const { data: loadedConfig, isLoading: configLoading } = useQuery({
    queryKey: ["indexerConfig"],
    queryFn: () => api.getIndexerConfig("default"),
  });

  useEffect(() => {
    if (loadedConfig) {
      setConfig(loadedConfig);
    }
  }, [loadedConfig]);

  const saveMutation = useMutation({
    mutationFn: () => api.saveIndexerConfig(config),
    onSuccess: () => {
      toast({ title: "Config saved" });
      queryClient.invalidateQueries({ queryKey: ["indexerConfig"] });
    },
    onError: (error) => {
      toast({
        title: "Save failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleExport = async () => {
    try {
      const result = await api.exportIndexerConfig("default");
      const blob = new Blob([result.yaml_content], {
        type: "application/x-yaml",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `indexer-config.yaml`;
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
      const response = await fetch(`/api/admin/configs/indexer/import`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({ detail: "Import failed" }));
        throw new Error(error.detail || "Import failed");
      }

      toast({ title: "Config imported" });
      queryClient.invalidateQueries({ queryKey: ["indexerConfig"] });
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

      <Card>
        <CardContent className="pt-6 flex items-center gap-4 flex-wrap">
          <Button variant="outline" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>

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
        </CardContent>
      </Card>

      {configLoading ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Loading configuration...
          </CardContent>
        </Card>
      ) : (
        <ConfigForm
          schema={patchedSchema}
          config={config}
          onChange={setConfig}
          onSave={() => saveMutation.mutate()}
          isSaving={saveMutation.isPending}
        />
      )}
    </div>
  );
}
