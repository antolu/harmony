import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { ModelStepForm } from "@/components/ModelStepForm";
import { modelsApi, type ModelSettings } from "@/api/models";
import { setupApi } from "@/api/setup";
import { api } from "@/api/client";
import { useToast } from "@/hooks/use-toast";

type Provider = "ollama" | "litellm";

interface CardState {
  provider: Provider;
  model: string;
  validated: boolean;
}

const HARMONY_ROLES = ["admin", "operator", "read_only", "anonymous"] as const;

function ModelPolicyCard({
  modelId,
  policy,
  onAdd,
  onRemove,
  isAdding,
  isRemoving,
}: {
  modelId: string;
  policy: { model_id: string; allowed_roles: string[] } | undefined;
  onAdd: (modelId: string, role: string) => void;
  onRemove: (modelId: string, role: string) => void;
  isAdding: boolean;
  isRemoving: boolean;
}) {
  const [selectedRole, setSelectedRole] = useState<string>("");
  const allowedRoles = policy?.allowed_roles ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{modelId} Access</CardTitle>
        <CardDescription>Roles allowed to use this model.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {allowedRoles.length === 0 ? (
          <Alert>
            <AlertDescription>
              No roles assigned — this model is inaccessible to all users.
            </AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-2">
            {allowedRoles.map((role) => (
              <div
                key={role}
                className="flex items-center justify-between rounded border px-3 py-2"
              >
                <span className="text-sm">{role}</span>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      aria-label={`Remove ${role} from ${modelId}`}
                      disabled={isRemoving}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Remove role?</AlertDialogTitle>
                      <AlertDialogDescription>
                        Remove {role} from {modelId}? Users with only this role
                        will lose access to this model.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Keep Role</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => onRemove(modelId, role)}
                      >
                        Remove Role
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-2">
          <Select value={selectedRole} onValueChange={setSelectedRole}>
            <SelectTrigger className="flex-1">
              <SelectValue placeholder="Select role" />
            </SelectTrigger>
            <SelectContent>
              {HARMONY_ROLES.filter((r) => !allowedRoles.includes(r)).map(
                (role) => (
                  <SelectItem key={role} value={role}>
                    {role}
                  </SelectItem>
                ),
              )}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            onClick={() => {
              if (selectedRole) {
                onAdd(modelId, selectedRole);
                setSelectedRole("");
              }
            }}
            disabled={!selectedRole || isAdding}
          >
            {isAdding ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Add role
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function Models() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: settings } = useQuery({
    queryKey: ["modelSettings"],
    queryFn: modelsApi.getSettings,
  });

  const { data: ollamaHostStatus } = useQuery({
    queryKey: ["ollamaHostStatus"],
    queryFn: setupApi.getOllamaHost,
  });

  const { data: modelPolicy } = useQuery({
    queryKey: ["modelPolicy"],
    queryFn: api.getModelPolicy,
  });

  const ollamaAvailable = Boolean(ollamaHostStatus?.value);
  const [ollamaHostInput, setOllamaHostInput] = useState("");
  const ollamaHostInitialized = useRef(false);

  useEffect(() => {
    if (ollamaHostStatus && !ollamaHostInitialized.current) {
      setOllamaHostInput(ollamaHostStatus.value);
      ollamaHostInitialized.current = true;
    }
  }, [ollamaHostStatus]);

  const updateOllamaHostMutation = useMutation({
    mutationFn: (value: string) => setupApi.updateOllamaHost(value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ollamaHostStatus"] });
      toast({ title: "Ollama host saved." });
    },
    onError: (e) => {
      toast({
        title: "Save failed",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const [embedding, setEmbedding] = useState<CardState>({
    provider: "ollama",
    model: "",
    validated: false,
  });
  const [reranker, setReranker] = useState<CardState>({
    provider: "ollama",
    model: "",
    validated: false,
  });
  const [llm, setLlm] = useState<CardState>({
    provider: "litellm",
    model: "",
    validated: false,
  });

  useEffect(() => {
    if (settings) {
      setEmbedding({
        provider: settings.embedding_provider,
        model: settings.embedding_model,
        validated: true,
      });
      setReranker({
        provider: settings.reranker_provider,
        model: settings.reranker_model,
        validated: true,
      });
      setLlm({
        provider: settings.llm_provider,
        model: settings.llm_model,
        validated: true,
      });
    }
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: (patch: Partial<ModelSettings>) =>
      modelsApi.updateSettings(patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["modelSettings"] });
      toast({ title: "Model settings saved." });
    },
    onError: (e) => {
      toast({
        title: "Save failed",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const addRoleMutation = useMutation({
    mutationFn: ({
      model_id,
      harmony_role,
    }: {
      model_id: string;
      harmony_role: string;
    }) => api.addModelPolicyRole(model_id, harmony_role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["modelPolicy"] });
      toast({ title: "Role added." });
    },
    onError: (e) => {
      toast({
        title: "Failed to add role",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const removeRoleMutation = useMutation({
    mutationFn: ({
      model_id,
      harmony_role,
    }: {
      model_id: string;
      harmony_role: string;
    }) => api.removeModelPolicyRole(model_id, harmony_role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["modelPolicy"] });
      toast({ title: "Role removed." });
    },
    onError: (e) => {
      toast({
        title: "Failed to remove role",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const saveEmbedding = () => {
    saveMutation.mutate({
      embedding_provider: embedding.provider,
      embedding_model: embedding.model,
    });
  };

  const saveReranker = () => {
    saveMutation.mutate({
      reranker_provider: reranker.provider,
      reranker_model: reranker.model,
    });
  };

  const saveLlm = () => {
    saveMutation.mutate({
      llm_provider: llm.provider,
      llm_model: llm.model,
    });
  };

  const embeddingChanged =
    settings?.embedding_model_changed_since_last_embed === "true";

  const modelIds = [
    settings?.embedding_model,
    settings?.reranker_model,
    settings?.llm_model,
  ].filter(Boolean) as string[];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Models</h2>
        <p className="text-muted-foreground">
          Configure embedding, reranker, and LLM models.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Ollama Host</CardTitle>
          <CardDescription>
            URL of the Ollama server used for local models.
            {ollamaHostStatus?.from_env && (
              <span className="ml-1 text-yellow-600">
                Currently set via environment variable — DB value will be
                ignored while env var is present.
              </span>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              value={ollamaHostInput}
              onChange={(e) => setOllamaHostInput(e.target.value)}
              placeholder="http://host.docker.internal:11434"
              disabled={updateOllamaHostMutation.isPending}
            />
            <Button
              onClick={() => updateOllamaHostMutation.mutate(ollamaHostInput)}
              disabled={
                updateOllamaHostMutation.isPending ||
                ollamaHostInput === (ollamaHostStatus?.value ?? "")
              }
            >
              {updateOllamaHostMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Save"
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {/* Embedding Model */}
        <Card>
          <CardHeader>
            <CardTitle>Embedding Model</CardTitle>
            <CardDescription>
              Used to embed documents and queries for vector search. Changing
              this model requires re-embedding all documents.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ModelStepForm
              label="Model"
              provider={embedding.provider}
              model={embedding.model}
              modelType="embedding"
              ollamaAvailable={ollamaAvailable}
              ollamaHost={ollamaHostStatus?.value}
              onProviderChange={(p) =>
                setEmbedding((s) => ({
                  ...s,
                  provider: p,
                  model: "",
                  validated: false,
                }))
              }
              onModelChange={(m) =>
                setEmbedding((s) => ({ ...s, model: m, validated: false }))
              }
              onValidated={(v) => setEmbedding((s) => ({ ...s, validated: v }))}
            />

            {embeddingChanged && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Embedding model changed — vector search is disabled until
                  re-embed completes. Run re-embed from the Indexer page.
                </AlertDescription>
              </Alert>
            )}

            <Button
              variant="outline"
              onClick={saveEmbedding}
              disabled={saveMutation.isPending || !embedding.model}
            >
              Save
            </Button>
          </CardContent>
        </Card>

        {/* Reranker Model */}
        <Card>
          <CardHeader>
            <CardTitle>Reranker Model</CardTitle>
            <CardDescription>
              Cross-encoder model used to re-rank search candidates.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ModelStepForm
              label="Model"
              provider={reranker.provider}
              model={reranker.model}
              modelType="reranker"
              ollamaAvailable={ollamaAvailable}
              ollamaHost={ollamaHostStatus?.value}
              onProviderChange={(p) =>
                setReranker((s) => ({
                  ...s,
                  provider: p,
                  model: "",
                  validated: false,
                }))
              }
              onModelChange={(m) =>
                setReranker((s) => ({ ...s, model: m, validated: false }))
              }
              onValidated={(v) => setReranker((s) => ({ ...s, validated: v }))}
            />
            <Button
              variant="outline"
              onClick={saveReranker}
              disabled={saveMutation.isPending || !reranker.model}
            >
              Save
            </Button>
          </CardContent>
        </Card>
        {/* LLM Model */}
        <Card>
          <CardHeader>
            <CardTitle>LLM Model</CardTitle>
            <CardDescription>
              Language model used for AI search and agentic search.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ModelStepForm
              label="Model"
              provider={llm.provider}
              model={llm.model}
              modelType="llm"
              ollamaAvailable={ollamaAvailable}
              ollamaHost={ollamaHostStatus?.value}
              onProviderChange={(p) =>
                setLlm((s) => ({
                  ...s,
                  provider: p,
                  model: "",
                  validated: false,
                }))
              }
              onModelChange={(m) =>
                setLlm((s) => ({ ...s, model: m, validated: false }))
              }
              onValidated={(v) => setLlm((s) => ({ ...s, validated: v }))}
            />
            <Button
              variant="outline"
              onClick={saveLlm}
              disabled={saveMutation.isPending || !llm.model}
            >
              Save
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Model Access Policy */}
      <div>
        <h3 className="text-xl font-bold tracking-tight mb-4">
          Model Access Policy
        </h3>
        {modelIds.length === 0 ? (
          <Alert>
            <AlertDescription>
              No roles assigned — this model is inaccessible to all users.
            </AlertDescription>
          </Alert>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {modelIds.map((modelId) => (
              <ModelPolicyCard
                key={modelId}
                modelId={modelId}
                policy={modelPolicy?.find((p) => p.model_id === modelId)}
                onAdd={(mid, role) =>
                  addRoleMutation.mutate({
                    model_id: mid,
                    harmony_role: role,
                  })
                }
                onRemove={(mid, role) =>
                  removeRoleMutation.mutate({
                    model_id: mid,
                    harmony_role: role,
                  })
                }
                isAdding={addRoleMutation.isPending}
                isRemoving={removeRoleMutation.isPending}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
