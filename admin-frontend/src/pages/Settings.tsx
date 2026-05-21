import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, AlertTriangle, Database, Globe, Loader2 } from "lucide-react";
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
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/api/client";
import { modelsApi, type PipelineConfig } from "@/api/models";
import { PillToggle } from "@/components/PillToggle";
import {
  getOidcSettings,
  saveOidcSettings,
  testOidcConnection,
} from "@/api/auth";

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

  const [oidcEnabled, setOidcEnabled] = useState(false);
  const [issuerUrl, setIssuerUrl] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [scopes, setScopes] = useState("openid profile email");
  const [oidcErrors, setOidcErrors] = useState<Record<string, string>>({});
  const [testingConnection, setTestingConnection] = useState(false);

  useEffect(() => {
    getOidcSettings().then((s) => {
      setOidcEnabled(s.oidcEnabled);
      setIssuerUrl(s.issuerUrl);
      setClientId(s.clientId);
      setScopes(s.scopes || "openid profile email");
    });
  }, []);

  const saveOidc = async () => {
    if (oidcEnabled) {
      const errors: Record<string, string> = {};
      if (!issuerUrl) errors.issuerUrl = "Issuer URL is required";
      if (!clientId) errors.clientId = "Client ID is required";
      if (!clientSecret) errors.clientSecret = "Client Secret is required";
      if (Object.keys(errors).length > 0) {
        setOidcErrors(errors);
        return;
      }
    }
    setOidcErrors({});
    try {
      await saveOidcSettings({
        oidcEnabled,
        issuerUrl,
        clientId,
        clientSecret,
        scopes,
      });
      toast({ title: "Settings saved" });
    } catch (err) {
      toast({
        title: "Failed to save settings",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      });
    }
  };

  const testConnection = async () => {
    setTestingConnection(true);
    try {
      await testOidcConnection();
      toast({
        title: "Connection successful",
        description: "OIDC discovery endpoint responded.",
      });
    } catch (err) {
      toast({
        title: "Connection failed",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      });
    } finally {
      setTestingConnection(false);
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
      <Separator className="my-6" />

      {/* Single Sign-On (OIDC) */}
      <Card>
        <CardHeader>
          <CardTitle>Single Sign-On (OIDC)</CardTitle>
          <CardDescription>
            Configure OIDC/OAuth2 login for admin access.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Switch
              id="oidc-enabled"
              checked={oidcEnabled}
              onCheckedChange={setOidcEnabled}
            />
            <Label htmlFor="oidc-enabled">Enable OIDC Login</Label>
          </div>

          <div className="space-y-1">
            <Label>Issuer URL</Label>
            <Input
              placeholder="https://your-idp.example.com/realms/harmony"
              value={issuerUrl}
              onChange={(e) => setIssuerUrl(e.target.value)}
              disabled={!oidcEnabled}
            />
            {oidcErrors.issuerUrl && (
              <p className="text-xs text-destructive min-h-[1rem]">
                {oidcErrors.issuerUrl}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <Label>Client ID</Label>
            <Input
              placeholder="harmony-admin"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              disabled={!oidcEnabled}
            />
            {oidcErrors.clientId && (
              <p className="text-xs text-destructive min-h-[1rem]">
                {oidcErrors.clientId}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <Label>Client Secret</Label>
            <Input
              type="password"
              placeholder="••••••••"
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              disabled={!oidcEnabled}
            />
            {oidcErrors.clientSecret && (
              <p className="text-xs text-destructive min-h-[1rem]">
                {oidcErrors.clientSecret}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <Label>Scopes</Label>
            <Input
              value={scopes}
              onChange={(e) => setScopes(e.target.value)}
              disabled={!oidcEnabled}
            />
            <p className="text-xs text-muted-foreground">
              Space-separated. Must include openid.
            </p>
          </div>

          <div className="flex justify-end gap-2">
            {oidcEnabled && issuerUrl && (
              <Button
                variant="outline"
                onClick={testConnection}
                disabled={testingConnection}
              >
                {testingConnection ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Testing...
                  </>
                ) : (
                  "Test Connection"
                )}
              </Button>
            )}
            <Button onClick={saveOidc}>Save Settings</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
