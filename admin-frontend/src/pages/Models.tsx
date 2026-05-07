import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ModelStepForm } from "@/components/ModelStepForm";
import { modelsApi, type ModelSettings } from "@/api/models";
import { api } from "@/api/client";
import { useToast } from "@/hooks/use-toast";

type Provider = "ollama" | "litellm";

interface CardState {
  provider: Provider;
  model: string;
  validated: boolean;
}

export function Models() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: settings } = useQuery({
    queryKey: ["modelSettings"],
    queryFn: modelsApi.getSettings,
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

  const embedJobMutation = useMutation({
    mutationFn: () => api.startEmbedJob(),
    onSuccess: (job) => {
      navigate(`/jobs/${job.id}`);
    },
    onError: (e) => {
      toast({
        title: "Failed to start embed job",
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

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Models</h2>
        <p className="text-muted-foreground">
          Configure embedding, reranker, and LLM models.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
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
                  re-embed completes.
                </AlertDescription>
              </Alert>
            )}

            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={saveEmbedding}
                disabled={saveMutation.isPending || !embedding.model}
              >
                Save
              </Button>
              <Button
                variant="secondary"
                onClick={() => embedJobMutation.mutate()}
                disabled={embedJobMutation.isPending}
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Re-embed all documents
              </Button>
            </div>
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
      </div>

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
  );
}
