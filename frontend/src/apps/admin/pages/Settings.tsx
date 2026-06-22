import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, AlertTriangle, Loader2, Lock } from "lucide-react";
import {
  getOidcSettings,
  saveOidcSettings,
  type OidcSettings,
} from "@/shared/api/auth";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
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
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Switch } from "@/shared/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";
import { Separator } from "@/shared/components/ui/separator";
import { useToast } from "@/shared/hooks/use-toast";
import {
  api,
  type OllamaHostEntry,
  type LlmApiKeyEntry,
} from "@/shared/api/client";
import { modelsApi, type PipelineConfig } from "@/shared/api/models";
import { PillToggle } from "@/shared/components/PillToggle";
import { Checkbox } from "@/shared/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import { Combobox } from "@/shared/components/ui/combobox";
import { Pencil, Plus } from "lucide-react";

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

function InfrastructureCard() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: config } = useQuery({
    queryKey: ["infrastructureConfig"],
    queryFn: api.getInfrastructureConfig,
  });

  const updateMutation = useMutation({
    mutationFn: api.updateInfrastructureConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["infrastructureConfig"] });
      toast({ title: "Infrastructure settings saved." });
    },
    onError: () => {
      toast({
        title: "Failed to update infrastructure config",
        variant: "destructive",
      });
    },
  });

  const [esInput, setEsInput] = useState("");
  const [qdrantInput, setQdrantInput] = useState("");

  if (!config)
    return <p className="text-sm text-muted-foreground">Loading...</p>;

  const handleEsSave = () => {
    updateMutation.mutate({ elasticsearch_url: esInput });
  };

  const handleQdrantSave = () => {
    updateMutation.mutate({ qdrant_host: qdrantInput });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Infrastructure</CardTitle>
        <CardDescription>ES and Qdrant connection settings</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">
            Elasticsearch URL
          </Label>
          <div className="flex items-center gap-2">
            <Input
              defaultValue={config.elasticsearch_url}
              onChange={(e) => setEsInput(e.target.value)}
              className="flex-1"
            />
            <Button
              variant="outline"
              onClick={handleEsSave}
              disabled={!esInput || updateMutation.isPending}
            >
              Save Changes
            </Button>
          </div>
        </div>
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Qdrant Host</Label>
          <div className="flex items-center gap-2">
            <Input
              defaultValue={config.qdrant_host}
              onChange={(e) => setQdrantInput(e.target.value)}
              className="flex-1"
            />
            <Button
              variant="outline"
              onClick={handleQdrantSave}
              disabled={!qdrantInput || updateMutation.isPending}
            >
              Save Changes
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ModelHostsCard() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: hosts } = useQuery({
    queryKey: ["ollamaHosts"],
    queryFn: api.listOllamaHosts,
  });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [hostType, setHostType] = useState<"ollama" | "vllm">("ollama");

  const [deleteOpenId, setDeleteOpenId] = useState<string | null>(null);
  const [forceDelete, setForceDelete] = useState(false);
  const [deleteBlockedCount, setDeleteBlockedCount] = useState<number | null>(
    null,
  );

  const resetForm = () => {
    setName("");
    setUrl("");
    setHostType("ollama");
    setEditingId(null);
  };

  const createMutation = useMutation({
    mutationFn: (data: { name: string; url: string; host_type: string }) =>
      api.createOllamaHost(data.name, data.url, data.host_type),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ollamaHosts"] });
      setDialogOpen(false);
      resetForm();
    },
    onError: () =>
      toast({
        title:
          "Could not connect to this host. Check the URL and that the service is running, then try again.",
        variant: "destructive",
      }),
  });

  const updateMutation = useMutation({
    mutationFn: (data: {
      id: string;
      name: string;
      url: string;
      host_type: string;
    }) => api.updateOllamaHost(data.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ollamaHosts"] });
      setDialogOpen(false);
      resetForm();
    },
    onError: () =>
      toast({
        title:
          "Could not connect to this host. Check the URL and that the service is running, then try again.",
        variant: "destructive",
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteOllamaHost(id, forceDelete),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ollamaHosts"] });
      setDeleteOpenId(null);
      setForceDelete(false);
      setDeleteBlockedCount(null);
    },
    onError: (err: Error) => {
      if (err.message && err.message.includes("model_count")) {
        try {
          const match = err.message.match(/model_count['"]?\s*:\s*(\d+)/);
          if (match) setDeleteBlockedCount(parseInt(match[1], 10));
        } catch {
          // ignore
        }
      } else {
        toast({ title: "Failed to delete host", variant: "destructive" });
      }
    },
  });

  const handleOpenEdit = (host: OllamaHostEntry) => {
    setEditingId(host.id);
    setName(host.name);
    setUrl(host.url);
    setHostType(host.host_type);
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    if (editingId) {
      updateMutation.mutate({ id: editingId, name, url, host_type: hostType });
    } else {
      createMutation.mutate({ name, url, host_type: hostType });
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Model Hosts</CardTitle>
          <CardDescription>Ollama and vLLM servers for models</CardDescription>
        </div>
        <Button
          size="sm"
          onClick={() => {
            resetForm();
            setDialogOpen(true);
          }}
        >
          <Plus className="mr-2 h-4 w-4" /> Add Host
        </Button>
      </CardHeader>
      <CardContent>
        {!hosts || hosts.length === 0 ? (
          <div className="text-center py-4 text-sm text-muted-foreground">
            No hosts configured
            <br />
            Add an Ollama or vLLM host to start assigning models to it.
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>URL</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {hosts.map((host) => (
                <TableRow key={host.id}>
                  <TableCell className="font-medium">{host.name}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="uppercase text-[10px]">
                      {host.host_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground font-mono text-xs">
                    {host.url}
                  </TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleOpenEdit(host)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <AlertDialog
                      open={deleteOpenId === host.id}
                      onOpenChange={(v) => {
                        if (!v) {
                          setDeleteOpenId(null);
                          setForceDelete(false);
                          setDeleteBlockedCount(null);
                        } else {
                          setDeleteOpenId(host.id);
                        }
                      }}
                    >
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>
                            {deleteBlockedCount !== null
                              ? `Force delete host?`
                              : `Remove host?`}
                          </AlertDialogTitle>
                          <AlertDialogDescription>
                            {deleteBlockedCount !== null
                              ? `Cannot remove host — ${deleteBlockedCount} model(s) use this host. Reassign or delete those models first, or check 'Force delete' below to remove anyway.`
                              : `This will permanently delete this host. This cannot be undone.`}
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        {deleteBlockedCount !== null && (
                          <div className="flex items-center gap-2 px-1 py-2">
                            <Checkbox
                              id="force-delete-host"
                              checked={forceDelete}
                              onCheckedChange={(v) => setForceDelete(!!v)}
                            />
                            <Label
                              htmlFor="force-delete-host"
                              className="text-sm font-normal"
                            >
                              Force delete host? — {deleteBlockedCount} model(s)
                              using this host will be deleted along with it.
                              This cannot be undone.
                            </Label>
                          </div>
                        )}
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={(e) => {
                              e.preventDefault();
                              deleteMutation.mutate(host.id);
                            }}
                            disabled={
                              deleteBlockedCount !== null && !forceDelete
                            }
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                          >
                            {deleteMutation.isPending ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : null}
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <Dialog
        open={dialogOpen}
        onOpenChange={(v) => {
          if (!v) resetForm();
          setDialogOpen(v);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingId ? "Edit Host" : "Add Host"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1">
              <Label>Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My Local GPU"
              />
            </div>
            <div className="space-y-1">
              <Label>URL</Label>
              <Input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="http://127.0.0.1:11434"
              />
            </div>
            <div className="space-y-1">
              <Label>Type</Label>
              <Combobox
                options={["ollama", "vllm"]}
                value={hostType}
                onChange={(v) => setHostType(v as "ollama" | "vllm")}
                placeholder="Select type..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={
                !name ||
                !url ||
                createMutation.isPending ||
                updateMutation.isPending
              }
            >
              {createMutation.isPending || updateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function ApiKeysCard() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: keys } = useQuery({
    queryKey: ["llmApiKeys"],
    queryFn: api.listLlmApiKeys,
  });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");

  const resetForm = () => {
    setName("");
    setValue("");
    setEditingId(null);
  };

  const createMutation = useMutation({
    mutationFn: (data: { name: string; value: string }) =>
      api.createLlmApiKey(data.name, data.value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["llmApiKeys"] });
      setDialogOpen(false);
      resetForm();
    },
    onError: () =>
      toast({ title: "Failed to create API key", variant: "destructive" }),
  });

  const updateMutation = useMutation({
    mutationFn: (data: { id: string; name: string; value: string }) =>
      api.updateLlmApiKey(data.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["llmApiKeys"] });
      setDialogOpen(false);
      resetForm();
    },
    onError: () =>
      toast({ title: "Failed to update API key", variant: "destructive" }),
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteLlmApiKey,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["llmApiKeys"] });
      if (data.model_count > 0) {
        toast({
          title: `Disabled ${data.model_count} model(s) that used this key`,
        });
      }
    },
    onError: () =>
      toast({ title: "Failed to delete API key", variant: "destructive" }),
  });

  const handleOpenEdit = (key: LlmApiKeyEntry) => {
    setEditingId(key.id);
    setName(key.name);
    setValue("");
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    if (editingId) {
      updateMutation.mutate({ id: editingId, name, value });
    } else {
      createMutation.mutate({ name, value });
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>API Keys</CardTitle>
          <CardDescription>Keys for external LLM providers</CardDescription>
        </div>
        <Button
          size="sm"
          onClick={() => {
            resetForm();
            setDialogOpen(true);
          }}
        >
          <Plus className="mr-2 h-4 w-4" /> Add API Key
        </Button>
      </CardHeader>
      <CardContent>
        {!keys || keys.length === 0 ? (
          <div className="text-center py-4 text-sm text-muted-foreground">
            No API keys configured
            <br />
            Add an API key here, or paste one directly in the model form to
            create it inline.
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Value</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {keys.map((k) => (
                <TableRow key={k.id}>
                  <TableCell className="font-medium">{k.name}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-muted-foreground font-mono">
                        {k.value_set ? "••••••••" : "Not set"}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() => handleOpenEdit(k)}
                      >
                        {k.value_set ? "Update" : "Set key"}
                      </Button>
                    </div>
                  </TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleOpenEdit(k)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Remove API key?</AlertDialogTitle>
                          <AlertDialogDescription>
                            Remove API key? — Models using this key will be
                            disabled (not deleted). You can reassign a new key
                            to re-enable them.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() => deleteMutation.mutate(k.id)}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                          >
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <Dialog
        open={dialogOpen}
        onOpenChange={(v) => {
          if (!v) resetForm();
          setDialogOpen(v);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingId ? "Edit API Key" : "Add API Key"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1">
              <Label>Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="OpenAI Prod Key"
              />
            </div>
            <div className="space-y-1">
              <Label>Value</Label>
              <Input
                type="password"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={
                  editingId ? "Leave blank to keep unchanged" : "sk-..."
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={
                !name ||
                (!editingId && !value) ||
                createMutation.isPending ||
                updateMutation.isPending
              }
            >
              {createMutation.isPending || updateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
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
    indexStatus?.indices.filter((i) => i.type === "search") ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground">
          System settings and reset operations
        </p>
      </div>

      <Separator />

      <div className="space-y-6">
        <h3 className="text-xl font-semibold">Services</h3>
        <InfrastructureCard />
        <ModelHostsCard />
        <ApiKeysCard />
      </div>

      <Separator />

      {/* Search Pipeline */}
      <Card>
        <CardHeader>
          <CardTitle>Search Pipeline</CardTitle>
          <CardDescription>
            Runtime search tuning — changes take effect immediately.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {!pipelineConfig ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <>
              <div className="flex items-center gap-8">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium">Vector Search</span>
                  <PillToggle
                    value={pipelineConfig.vector_search_enabled}
                    onChange={(v) => handleToggle("vector_search_enabled", v)}
                  />
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium">Reranker</span>
                  <PillToggle
                    value={pipelineConfig.reranker_enabled}
                    onChange={(v) => handleToggle("reranker_enabled", v)}
                    disabled={!pipelineConfig.vector_search_enabled}
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
                    <Label className="text-xs text-muted-foreground">
                      {label}
                    </Label>
                    <Input
                      type="number"
                      defaultValue={pipelineConfig[field]}
                      onBlur={(e) => {
                        const v = parseInt(e.target.value, 10);
                        if (!isNaN(v) && v >= 0) handleNumericBlur(field, v);
                      }}
                      className="w-full"
                    />
                  </div>
                ))}
              </div>

              <div>
                <p className="text-sm font-medium mb-3">Agentic Search</p>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  {(
                    [
                      [
                        "agentic_max_refinement_rounds",
                        "Max Refinement Rounds",
                      ],
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
                        defaultValue={pipelineConfig[field]}
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
            </>
          )}
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
          {!pipelineConfig ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-1">
                <Label>Audit Log Retention (days, 0 = keep forever)</Label>
                <Input
                  type="number"
                  min={0}
                  defaultValue={pipelineConfig.audit_retention_days}
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
                  defaultValue={pipelineConfig.conversation_ttl_days}
                  onBlur={(e) => {
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v) && v >= 0)
                      handleNumericBlur("conversation_ttl_days", v);
                  }}
                  className="max-w-xs"
                />
              </div>
            </div>
          )}
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
