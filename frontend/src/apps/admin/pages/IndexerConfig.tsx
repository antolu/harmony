import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Database, Globe } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Switch } from "@/shared/components/ui/switch";
import { Badge } from "@/shared/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import { useToast } from "@/shared/hooks/use-toast";
import { api } from "@/shared/api/client";

interface IndexerFormState {
  sync_deletions: boolean;
  missing_threshold: number;
  batch_size: number;
}

const DEFAULTS: IndexerFormState = {
  sync_deletions: false,
  missing_threshold: 3,
  batch_size: 64,
};

function toFormState(config: Record<string, unknown>): IndexerFormState {
  return {
    sync_deletions: Boolean(config.sync_deletions ?? DEFAULTS.sync_deletions),
    missing_threshold: Number(
      config.missing_threshold ?? DEFAULTS.missing_threshold,
    ),
    batch_size: Number(config.batch_size ?? DEFAULTS.batch_size),
  };
}

export function IndexerConfig() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [form, setForm] = useState<IndexerFormState>(DEFAULTS);

  const { data: loadedConfig } = useQuery({
    queryKey: ["indexerConfig"],
    queryFn: () => api.getSingletonIndexerConfig(),
  });

  const { data: indexStatus } = useQuery({
    queryKey: ["indexStatus"],
    queryFn: () => api.getIndexStatus(),
  });

  const { data: qdrantStatus } = useQuery({
    queryKey: ["qdrantStatus"],
    queryFn: () => api.getQdrantStatus(),
  });

  const [prevLoadedConfig, setPrevLoadedConfig] = useState(loadedConfig);
  if (loadedConfig !== prevLoadedConfig) {
    setPrevLoadedConfig(loadedConfig);
    if (loadedConfig) setForm(toFormState(loadedConfig));
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      api.saveIndexerConfig(form as unknown as Record<string, unknown>),
    onSuccess: () => {
      toast({ title: "Indexer config saved" });
      queryClient.invalidateQueries({ queryKey: ["indexerConfig"] });
    },
    onError: (error) => {
      toast({
        title: "Save failed",
        description: (error as Error).message,
        variant: "destructive",
      });
    },
  });

  const stateIndex = indexStatus?.indices.find((i) => i.type === "state");
  const searchIndices =
    indexStatus?.indices.filter((i) => i.type === "search") ?? [];

  return (
    <div className="space-y-6">
      {/* Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Indexer</CardTitle>
          <CardDescription>Runtime indexing settings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="sync_deletions">Sync deletions</Label>
              <p className="text-xs text-muted-foreground mt-0.5">
                Remove documents from ES and Qdrant when they disappear from the
                crawl
              </p>
            </div>
            <Switch
              id="sync_deletions"
              checked={form.sync_deletions}
              onCheckedChange={(v) =>
                setForm((f) => ({ ...f, sync_deletions: v }))
              }
            />
          </div>

          {form.sync_deletions && (
            <div className="space-y-1">
              <Label htmlFor="missing_threshold">Missing threshold</Label>
              <p className="text-xs text-muted-foreground">
                Number of crawls a document must be absent before it is deleted
              </p>
              <Input
                id="missing_threshold"
                type="number"
                min={1}
                value={form.missing_threshold}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    missing_threshold: Number(e.target.value),
                  }))
                }
                className="w-32"
              />
            </div>
          )}

          <div className="space-y-1">
            <Label htmlFor="batch_size">Batch size</Label>
            <p className="text-xs text-muted-foreground">
              Number of documents per bulk indexing and embedding batch
            </p>
            <Input
              id="batch_size"
              type="number"
              min={1}
              value={form.batch_size}
              onChange={(e) =>
                setForm((f) => ({ ...f, batch_size: Number(e.target.value) }))
              }
              className="w-32"
            />
          </div>

          <Button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending ? "Saving…" : "Save"}
          </Button>
        </CardContent>
      </Card>

      {/* Elasticsearch Indices */}
      <Card>
        <CardHeader>
          <CardTitle>Elasticsearch Indices</CardTitle>
          <CardDescription>
            Current index status and document counts
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Globe className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="font-medium">Crawl State Index</p>
                  <p className="text-sm text-muted-foreground">
                    {stateIndex?.name ?? "Not created"}
                  </p>
                </div>
              </div>
              <Badge variant="secondary">
                {stateIndex?.doc_count ?? 0} URLs
              </Badge>
            </div>
          </div>

          <div className="rounded-lg border p-4">
            <div className="flex items-center gap-3 mb-4">
              <Database className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="font-medium">Search Indices</p>
                <p className="text-sm text-muted-foreground">
                  Per-language document indices
                </p>
              </div>
            </div>
            {searchIndices.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No search indices created
              </p>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {searchIndices.map((index) => (
                  <div key={index.name} className="rounded border p-2">
                    <p className="font-medium">
                      {index.language?.toUpperCase()}
                    </p>
                    <p className="text-lg font-bold">{index.doc_count}</p>
                    <p className="text-xs text-muted-foreground truncate">
                      {index.name}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Qdrant */}
      <Card>
        <CardHeader>
          <CardTitle>Qdrant</CardTitle>
          <CardDescription>Vector store collection status</CardDescription>
        </CardHeader>
        <CardContent>
          {!qdrantStatus ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : !qdrantStatus.available ? (
            <p className="text-sm text-destructive">
              Unavailable: {qdrantStatus.reason}
            </p>
          ) : !qdrantStatus.exists ? (
            <p className="text-sm text-muted-foreground">
              Collection "{qdrantStatus.collection}" does not exist yet. Run the
              indexer to create it.
            </p>
          ) : (
            <div className="rounded-lg border p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Collection
                </span>
                <span className="text-sm font-medium">
                  {qdrantStatus.collection}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Vectors</span>
                <Badge variant="secondary">
                  {qdrantStatus.points_count?.toLocaleString()} points
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Vector size
                </span>
                <span className="text-sm font-medium">
                  {qdrantStatus.vector_size}
                </span>
              </div>
              {qdrantStatus.embedding_model && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    Embedding model
                  </span>
                  <span className="text-sm font-mono">
                    {qdrantStatus.embedding_model}
                  </span>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
