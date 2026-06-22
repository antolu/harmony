import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, Loader2, CheckCircle2, XCircle, PlugZap } from "lucide-react";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";
import { useToast } from "@/shared/hooks/use-toast";
import {
  api,
  type OllamaHostEntry,
  type LlmApiKeyEntry,
} from "@/shared/api/client";
import { setupApi, type ValidationResult } from "@/shared/api/setup";
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

function ValidatedConnectionField({
  label,
  defaultValue,
  placeholder,
  onSave,
}: {
  label: string;
  defaultValue: string;
  placeholder?: string;
  onSave: (value: string) => Promise<void>;
}) {
  const [value, setValue] = useState(defaultValue);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [validating, setValidating] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleTestConnection = async () => {
    setValidating(true);
    setValidation(null);
    try {
      const result = await setupApi.validate(
        label === "Elasticsearch URL"
          ? { elasticsearch_url: value }
          : { qdrant_host: value },
      );
      const fieldResult =
        label === "Elasticsearch URL" ? result.elasticsearch : result.qdrant;
      setValidation(fieldResult ?? null);
    } finally {
      setValidating(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(value);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Input
            value={value}
            placeholder={placeholder}
            onChange={(e) => {
              setValue(e.target.value);
              setValidation(null);
            }}
            disabled={validating || saving}
            className={validation ? "pr-8" : ""}
          />
          {validation && (
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2">
              {validation.ok ? (
                <CheckCircle2
                  className="h-4 w-4 text-green-500"
                  aria-label={validation.message}
                />
              ) : (
                <XCircle
                  className="h-4 w-4 text-destructive"
                  aria-label={validation.message}
                />
              )}
            </span>
          )}
        </div>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                onClick={handleTestConnection}
                disabled={!value || validating || saving}
                aria-label="Test connection"
              >
                {validating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <PlugZap className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Test connection</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <Button
          onClick={handleSave}
          disabled={!validation?.ok || validating || saving}
        >
          {saving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
          Save Changes
        </Button>
      </div>
      <p className="text-xs text-destructive min-h-[1rem]">
        {validation && !validation.ok ? validation.message : ""}
      </p>
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

  if (!config)
    return <p className="text-sm text-muted-foreground">Loading...</p>;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Infrastructure</CardTitle>
        <CardDescription>ES and Qdrant connection settings</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ValidatedConnectionField
          label="Elasticsearch URL"
          defaultValue={config.elasticsearch_url}
          onSave={async (value) => {
            await updateMutation.mutateAsync({ elasticsearch_url: value });
          }}
        />
        <ValidatedConnectionField
          label="Qdrant Host"
          defaultValue={config.qdrant_host}
          onSave={async (value) => {
            await updateMutation.mutateAsync({ qdrant_host: value });
          }}
        />
      </CardContent>
    </Card>
  );
}

const HOST_TYPE_LABELS: Record<"ollama" | "vllm", string> = {
  ollama: "Ollama",
  vllm: "vLLM",
};

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
  const [savedUrl, setSavedUrl] = useState("");
  const [savedHostType, setSavedHostType] = useState<"ollama" | "vllm">(
    "ollama",
  );
  const [connectionValidation, setConnectionValidation] =
    useState<ValidationResult | null>(null);
  const [validatingConnection, setValidatingConnection] = useState(false);

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
    setSavedUrl("");
    setSavedHostType("ollama");
    setConnectionValidation(null);
  };

  const connectionUnchanged = url === savedUrl && hostType === savedHostType;

  const handleTestConnection = async () => {
    setValidatingConnection(true);
    setConnectionValidation(null);
    try {
      const result = await setupApi.validate(
        hostType === "vllm" ? { vllm_host: url } : { ollama_host: url },
      );
      setConnectionValidation(
        (hostType === "vllm" ? result.vllm : result.ollama) ?? null,
      );
    } finally {
      setValidatingConnection(false);
    }
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
    setSavedUrl(host.url);
    setSavedHostType(host.host_type);
    setConnectionValidation(null);
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
          <div className="overflow-x-auto">
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
                      <Badge variant="outline" className="text-[10px]">
                        {HOST_TYPE_LABELS[host.host_type]}
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
                                Force delete host? — {deleteBlockedCount}{" "}
                                model(s) using this host will be deleted along
                                with it. This cannot be undone.
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
          </div>
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
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Input
                    value={url}
                    onChange={(e) => {
                      setUrl(e.target.value);
                      setConnectionValidation(null);
                    }}
                    placeholder="http://127.0.0.1:11434"
                    className={connectionValidation ? "pr-8" : ""}
                  />
                  {connectionValidation && (
                    <span className="absolute right-2.5 top-1/2 -translate-y-1/2">
                      {connectionValidation.ok ? (
                        <CheckCircle2
                          className="h-4 w-4 text-green-500"
                          aria-label={connectionValidation.message}
                        />
                      ) : (
                        <XCircle
                          className="h-4 w-4 text-destructive"
                          aria-label={connectionValidation.message}
                        />
                      )}
                    </span>
                  )}
                </div>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={handleTestConnection}
                        disabled={!url || validatingConnection}
                        aria-label="Test connection"
                      >
                        {validatingConnection ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <PlugZap className="h-4 w-4" />
                        )}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Test connection</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <p className="text-xs text-destructive min-h-[1rem]">
                {connectionValidation && !connectionValidation.ok
                  ? connectionValidation.message
                  : ""}
              </p>
            </div>
            <div className="space-y-1">
              <Label>Type</Label>
              <Combobox
                options={["Ollama", "vLLM"]}
                value={HOST_TYPE_LABELS[hostType]}
                onChange={(v) => {
                  setHostType(v === "vLLM" ? "vllm" : "ollama");
                  setConnectionValidation(null);
                }}
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
                (!connectionUnchanged && !connectionValidation?.ok) ||
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
          <div className="overflow-x-auto">
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
          </div>
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

export function Services() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Services</h2>
        <p className="text-muted-foreground">
          Infrastructure connections, model hosts, and API keys
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <InfrastructureCard />
        <ModelHostsCard />
        <ApiKeysCard />
      </div>
    </div>
  );
}
