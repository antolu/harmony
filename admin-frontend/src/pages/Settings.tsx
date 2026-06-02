import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Trash2,
  AlertTriangle,
  Database,
  Globe,
  Loader2,
  Lock,
} from "lucide-react";
import {
  getOidcSettings,
  saveOidcSettings,
  type OidcSettings,
} from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/api/client";
import { modelsApi, type PipelineConfig } from "@/api/models";
import { PillToggle } from "@/components/PillToggle";

const PROVIDER_LABELS: Record<string, string> = {
  brave: "Brave Search",
  google: "Google Search",
};

function ExternalProviderRow({
  provider,
  enabled,
  has_key,
  max_results,
  onSaveKey,
  onToggle,
  onMaxResultsChange,
}: {
  provider: string;
  enabled: boolean;
  has_key: boolean;
  max_results: number;
  onSaveKey: (provider: string, key: string) => Promise<void>;
  onToggle: (provider: string, enabled: boolean) => void;
  onMaxResultsChange: (provider: string, value: number) => void;
}) {
  const [keyInput, setKeyInput] = useState("");
  const [keySaved, setKeySaved] = useState(false);
  const [isSavingKey, setIsSavingKey] = useState(false);
  const { toast } = useToast();

  const handleSaveKey = async () => {
    if (!keyInput) return;
    setIsSavingKey(true);
    try {
      await onSaveKey(provider, keyInput);
      setKeyInput("");
      setKeySaved(true);
      toast({ title: "API key saved." });
    } catch {
      toast({
        title: "Failed to save API key. Try again or check API connectivity.",
        variant: "destructive",
      });
    } finally {
      setIsSavingKey(false);
    }
  };

  const showHasKey = has_key || keySaved;

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">
          {PROVIDER_LABELS[provider] ?? provider}
        </span>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Switch
                  checked={enabled}
                  onCheckedChange={(v) => onToggle(provider, v)}
                  disabled={!showHasKey}
                  aria-label={`Enable ${provider}`}
                />
              </span>
            </TooltipTrigger>
            {!showHasKey && (
              <TooltipContent>
                Save an API key before enabling this provider.
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </div>

      <div className="space-y-1">
        <Label className="text-xs text-muted-foreground">API Key</Label>
        <div className="flex items-center gap-2">
          <Input
            type="password"
            placeholder={
              showHasKey ? "Enter new key to replace" : "Enter API key"
            }
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            className="flex-1"
          />
          <Button
            variant="outline"
            onClick={handleSaveKey}
            disabled={!keyInput || isSavingKey}
          >
            {isSavingKey ? (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
            ) : null}
            Save Key
          </Button>
          {showHasKey && <Badge variant="secondary">Saved</Badge>}
        </div>
      </div>

      <div className="space-y-1">
        <Label className="text-xs text-muted-foreground">Max results</Label>
        <Input
          type="number"
          min={1}
          max={10}
          defaultValue={max_results}
          className="w-24"
          onBlur={(e) => {
            const v = parseInt(e.target.value, 10);
            if (!isNaN(v) && v >= 1 && v <= 10) onMaxResultsChange(provider, v);
          }}
        />
      </div>

      {enabled && showHasKey && (
        <Button variant="outline" size="sm">
          Test connection
        </Button>
      )}
    </div>
  );
}

export function Settings() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: indexStatus } = useQuery({
    queryKey: ["indexStatus"],
    queryFn: () => api.getIndexStatus(),
  });

  const { data: pipelineConfig } = useQuery({
    queryKey: ["pipelineConfig"],
    queryFn: modelsApi.getPipelineConfig,
  });

  const { data: externalProviders } = useQuery({
    queryKey: ["externalProviders"],
    queryFn: api.getExternalProviders,
  });

  const { data: oidcSettings } = useQuery({
    queryKey: ["oidcSettings"],
    queryFn: getOidcSettings,
  });

  const { data: currentUser } = useQuery({
    queryKey: ["currentUser"],
    queryFn: () => api.getCurrentUser(),
  });

  const isAdmin = currentUser?.harmony_role === "admin";

  const [oidcForm, setOidcForm] = useState<OidcSettings | null>(null);
  const oidcValues = oidcForm ??
    oidcSettings ?? {
      oidcEnabled: false,
      issuerUrl: "",
      clientId: "",
      clientSecret: "",
      scopes: "openid profile email",
    };

  const saveOidcMutation = useMutation({
    mutationFn: saveOidcSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["oidcSettings"] });
      setOidcForm(null);
      toast({ title: "OIDC settings saved." });
    },
    onError: () => {
      toast({ title: "Failed to save OIDC settings", variant: "destructive" });
    },
  });

  const updatePipelineMutation = useMutation({
    mutationFn: modelsApi.updatePipelineConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelineConfig"] });
    },
    onError: () => {
      toast({
        title: "Failed to update pipeline config",
        variant: "destructive",
      });
    },
  });

  const handleToggle = (field: keyof PipelineConfig, value: boolean) => {
    updatePipelineMutation.mutate({ [field]: value });
  };

  const handleNumericBlur = (field: keyof PipelineConfig, value: number) => {
    updatePipelineMutation.mutate({ [field]: value });
  };

  const resetStateMutation = useMutation({
    mutationFn: () => api.resetCrawlState(),
    onSuccess: (data) => {
      toast({
        title: "Crawl state reset",
        description: data.message,
      });
      queryClient.invalidateQueries({ queryKey: ["indexStatus"] });
    },
    onError: (error) => {
      toast({
        title: "Reset failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const resetSearchMutation = useMutation({
    mutationFn: () => api.resetSearchIndices(),
    onSuccess: (data) => {
      toast({
        title: "Search indices reset",
        description: data.message,
      });
      queryClient.invalidateQueries({ queryKey: ["indexStatus"] });
    },
    onError: (error) => {
      toast({
        title: "Reset failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleProviderToggle = async (provider: string, enabled: boolean) => {
    try {
      await api.updateProviderConfig(provider, { enabled });
      queryClient.invalidateQueries({ queryKey: ["externalProviders"] });
    } catch {
      toast({
        title: "Failed to update provider",
        variant: "destructive",
      });
    }
  };

  const handleMaxResultsChange = async (
    provider: string,
    max_results: number,
  ) => {
    try {
      await api.updateProviderConfig(provider, { max_results });
      queryClient.invalidateQueries({ queryKey: ["externalProviders"] });
    } catch {
      toast({
        title: "Failed to update provider",
        variant: "destructive",
      });
    }
  };

  const stateIndex = indexStatus?.indices.find((i) => i.type === "state");
  const searchIndices =
    indexStatus?.indices.filter((i) => i.type === "search") || [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground">
          System settings and reset operations
        </p>
      </div>

      {/* Search Pipeline */}
      <Card>
        <CardHeader>
          <CardTitle>Search Pipeline</CardTitle>
          <CardDescription>
            Runtime search tuning — changes take effect immediately.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">Vector Search</span>
              <PillToggle
                value={pipelineConfig?.vector_search_enabled ?? true}
                onChange={(v) => handleToggle("vector_search_enabled", v)}
              />
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">Reranker</span>
              <PillToggle
                value={pipelineConfig?.reranker_enabled ?? false}
                onChange={(v) => handleToggle("reranker_enabled", v)}
                disabled={!(pipelineConfig?.vector_search_enabled ?? true)}
              />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {(
              [
                ["keyword_candidates_n", "Keyword candidates"],
                ["vector_top_k", "Vector top-k"],
                ["search_top_k", "Results"],
              ] as const
            ).map(([field, label]) => (
              <div key={field} className="space-y-1">
                <Label className="text-xs text-muted-foreground">{label}</Label>
                <Input
                  type="number"
                  defaultValue={pipelineConfig?.[field] ?? 0}
                  onBlur={(e) => {
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v) && v >= 0) handleNumericBlur(field, v);
                  }}
                  className="w-full"
                />
              </div>
            ))}
          </div>

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">
              Reranker model
            </Label>
            <Input
              defaultValue={pipelineConfig?.reranker_model ?? ""}
              onBlur={(e) => {
                updatePipelineMutation.mutate({
                  reranker_model: e.target.value,
                });
              }}
              placeholder="e.g. bge-reranker-v2-m3"
              className="max-w-xs"
            />
          </div>

          <div>
            <p className="text-sm font-medium mb-3">Agentic Search</p>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {(
                [
                  ["agentic_max_refinement_rounds", "Max Refinement Rounds"],
                  ["agentic_max_query_variants", "Max Query Variants"],
                  ["agentic_search_top_k", "Agentic Search Top K"],
                  ["agentic_max_sources_returned", "Agentic Max Sources"],
                ] as const
              ).map(([field, label]) => (
                <div key={field} className="space-y-1">
                  <Label className="text-xs text-muted-foreground">
                    {label}
                  </Label>
                  <Input
                    type="number"
                    defaultValue={pipelineConfig?.[field] ?? 0}
                    onBlur={(e) => {
                      const v = parseInt(e.target.value, 10);
                      if (!isNaN(v) && v >= 0) handleNumericBlur(field, v);
                    }}
                    className="w-full"
                  />
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Retention */}
      <Card>
        <CardHeader>
          <CardTitle>Retention</CardTitle>
          <CardDescription>
            Data retention periods. Set to 0 to keep forever.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <Label>Audit Log Retention (days, 0 = keep forever)</Label>
              <Input
                type="number"
                min={0}
                defaultValue={pipelineConfig?.audit_retention_days ?? 0}
                onBlur={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (!isNaN(v) && v >= 0)
                    handleNumericBlur("audit_retention_days", v);
                }}
                className="max-w-xs"
              />
            </div>
            <div className="space-y-1">
              <Label>Conversation Retention (days, 0 = keep forever)</Label>
              <Input
                type="number"
                min={0}
                defaultValue={pipelineConfig?.conversation_ttl_days ?? 0}
                onBlur={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (!isNaN(v) && v >= 0)
                    handleNumericBlur("conversation_ttl_days", v);
                }}
                className="max-w-xs"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Index Status */}
      <Card>
        <CardHeader>
          <CardTitle>Elasticsearch Indices</CardTitle>
          <CardDescription>
            Current index status and document counts
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* State Index */}
            <div className="rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Globe className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="font-medium">Crawl State Index</p>
                    <p className="text-sm text-muted-foreground">
                      {stateIndex?.name || "Not created"}
                    </p>
                  </div>
                </div>
                <Badge variant="secondary">
                  {stateIndex?.doc_count || 0} URLs
                </Badge>
              </div>
            </div>

            {/* Search Indices */}
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
          </div>
        </CardContent>
      </Card>

      {/* External Search Providers */}
      <Card>
        <CardHeader>
          <CardTitle>External Search Providers</CardTitle>
          <CardDescription>
            Providers are off by default. API keys are stored encrypted and
            cannot be retrieved after saving.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!externalProviders || externalProviders.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No external providers configured. Add an API key to enable web
              search.
            </p>
          ) : (
            externalProviders.map((p) => (
              <ExternalProviderRow
                key={p.provider}
                provider={p.provider}
                enabled={p.enabled}
                has_key={p.has_key}
                max_results={p.max_results}
                onSaveKey={async (provider, key) => {
                  await api.saveProviderKey(provider, key);
                  queryClient.invalidateQueries({
                    queryKey: ["externalProviders"],
                  });
                }}
                onToggle={handleProviderToggle}
                onMaxResultsChange={handleMaxResultsChange}
              />
            ))
          )}
        </CardContent>
      </Card>

      {/* OIDC / Authentication */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5" />
            Authentication (OIDC)
          </CardTitle>
          <CardDescription>
            Connect an OIDC provider (e.g. Keycloak) to enable user login.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isAdmin ? (
            <>
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium">Enable OIDC</span>
                <Switch
                  checked={oidcValues.oidcEnabled}
                  onCheckedChange={(v) =>
                    setOidcForm({ ...oidcValues, oidcEnabled: v })
                  }
                />
              </div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-1">
                  <Label>Issuer URL</Label>
                  <Input
                    placeholder="https://keycloak.example.com/realms/myrealm"
                    value={oidcValues.issuerUrl}
                    onChange={(e) =>
                      setOidcForm({ ...oidcValues, issuerUrl: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label>Client ID</Label>
                  <Input
                    placeholder="harmony"
                    value={oidcValues.clientId}
                    onChange={(e) =>
                      setOidcForm({ ...oidcValues, clientId: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label>Client Secret</Label>
                  <Input
                    type="password"
                    placeholder="Leave blank to keep existing"
                    value={oidcValues.clientSecret}
                    onChange={(e) =>
                      setOidcForm({
                        ...oidcValues,
                        clientSecret: e.target.value,
                      })
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label>Scopes</Label>
                  <Input
                    placeholder="openid profile email"
                    value={oidcValues.scopes}
                    onChange={(e) =>
                      setOidcForm({ ...oidcValues, scopes: e.target.value })
                    }
                  />
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Button
                  onClick={() => saveOidcMutation.mutate(oidcValues)}
                  disabled={saveOidcMutation.isPending || !oidcForm}
                >
                  {saveOidcMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  Save
                </Button>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Admin role required to manage OIDC settings.
            </p>
          )}
        </CardContent>
      </Card>

      <Separator />

      {/* Reset Operations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Danger Zone
          </CardTitle>
          <CardDescription>
            Irreversible actions that delete data
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Reset Crawl State */}
          <div className="flex items-center justify-between rounded-lg border border-destructive/50 p-4">
            <div>
              <p className="font-medium">Reset Crawl State</p>
              <p className="text-sm text-muted-foreground">
                Delete the crawl state index. URLs will need to be re-crawled.
                {stateIndex && ` (${stateIndex.doc_count} URLs)`}
              </p>
            </div>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Reset State
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Reset Crawl State</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will delete the crawl state index containing{" "}
                    <strong>{stateIndex?.doc_count || 0}</strong> tracked URLs.
                    <br />
                    <br />
                    The crawler will treat all URLs as new and re-crawl
                    everything. This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() => resetStateMutation.mutate()}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    Delete State Index
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>

          {/* Reset Search Indices */}
          <div className="flex items-center justify-between rounded-lg border border-destructive/50 p-4">
            <div>
              <p className="font-medium">Reset Search Indices</p>
              <p className="text-sm text-muted-foreground">
                Delete all search indices. You will need to re-index after
                crawling.
                {searchIndices.length > 0 && (
                  <>
                    {" "}
                    ({searchIndices.reduce(
                      (sum, i) => sum + i.doc_count,
                      0,
                    )}{" "}
                    documents in {searchIndices.length} indices)
                  </>
                )}
              </p>
            </div>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Reset Indices
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Reset Search Indices</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will delete <strong>{searchIndices.length}</strong>{" "}
                    search indices containing{" "}
                    <strong>
                      {searchIndices.reduce((sum, i) => sum + i.doc_count, 0)}
                    </strong>{" "}
                    documents.
                    <br />
                    <br />
                    Search will not work until you run the indexer again. This
                    action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() => resetSearchMutation.mutate()}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    Delete Search Indices
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
