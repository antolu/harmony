# Model Management Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hybrid search pipeline tuning to the Settings page, a new `/models` page for Ollama/LiteLLM model management with re-embed trigger, and extend the setup wizard with model selection steps 3–5.

**Architecture:** A new `admin-frontend/src/api/models.ts` module owns all model/pipeline API calls. Two new reusable components (`PillToggle`, `ModelStepForm`) are shared between the setup wizard, settings page, and models page. React Query handles caching and invalidation. Ollama pull progress uses the fetch ReadableStream SSE pattern (same as job logs). The setup wizard gains steps 3–5 for embedding, reranker, and LLM model selection.

**Tech Stack:** React 18, TypeScript, React Query v5, Tailwind CSS, Radix UI, Lucide React — all existing dependencies, no new packages.

---

## Files

| Path | Action |
|------|--------|
| `admin-frontend/src/api/models.ts` | Create — API client for model settings + Ollama |
| `admin-frontend/src/api/setup.ts` | Modify — extend `CompleteSetupRequest` with model fields |
| `admin-frontend/src/api/client.ts` | Modify — add `Job` type `"embed"`, add `startEmbedJob()` |
| `admin-frontend/src/components/PillToggle.tsx` | Create — pill-shaped boolean toggle component |
| `admin-frontend/src/components/ModelStepForm.tsx` | Create — provider selector + model picker (shared) |
| `admin-frontend/src/pages/Models.tsx` | Create — `/models` page |
| `admin-frontend/src/pages/Settings.tsx` | Modify — add Search Pipeline card at top |
| `admin-frontend/src/pages/SetupWizard.tsx` | Modify — add steps 3–5 |
| `admin-frontend/src/components/layout/Sidebar.tsx` | Modify — add Models nav entry |
| `admin-frontend/src/App.tsx` | Modify — add `/models` route |

---

### Task 1: API Client Modules

**Files:**
- Create: `admin-frontend/src/api/models.ts`
- Modify: `admin-frontend/src/api/setup.ts`
- Modify: `admin-frontend/src/api/client.ts`

- [ ] **Step 1: Create models.ts**

```typescript
// admin-frontend/src/api/models.ts
import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: { "Content-Type": "application/json" },
});

export interface ModelSettings {
  embedding_provider: "ollama" | "litellm";
  embedding_model: string;
  reranker_provider: "ollama" | "litellm";
  reranker_model: string;
  llm_provider: "ollama" | "litellm";
  llm_model: string;
  embedding_model_changed_since_last_embed: "true" | "false";
}

export interface OllamaModel {
  name: string;
  size: number;
  modified_at: string;
}

export interface PipelineConfig {
  keyword_candidates_n: number;
  vector_top_k: number;
  search_top_k: number;
  vector_search_enabled: boolean;
  reranker_enabled: boolean;
}

export const modelsApi = {
  getSettings: async (): Promise<ModelSettings> => {
    const r = await apiClient.get<ModelSettings>("/settings/models");
    return r.data;
  },

  updateSettings: async (patch: Partial<ModelSettings>): Promise<ModelSettings> => {
    const r = await apiClient.patch<ModelSettings>("/settings/models", patch);
    return r.data;
  },

  validateModel: async (
    model: string,
    provider: string,
    model_type: string,
  ): Promise<{ valid: boolean; error?: string }> => {
    const r = await apiClient.post("/settings/models/validate", {
      model,
      provider,
      model_type,
    });
    return r.data;
  },

  listOllamaModels: async (): Promise<{ models: OllamaModel[] }> => {
    const r = await apiClient.get("/models/ollama");
    return r.data;
  },

  deleteOllamaModel: async (name: string): Promise<{ deleted: boolean }> => {
    const r = await apiClient.delete(
      `/models/ollama/${encodeURIComponent(name)}`,
    );
    return r.data;
  },

  getPipelineConfig: async (): Promise<PipelineConfig> => {
    const r = await apiClient.get<PipelineConfig>("/settings/pipeline");
    return r.data;
  },

  updatePipelineConfig: async (
    patch: Partial<PipelineConfig>,
  ): Promise<PipelineConfig> => {
    const r = await apiClient.patch<PipelineConfig>("/settings/pipeline", patch);
    return r.data;
  },
};

// Ollama pull uses POST+SSE — use fetch ReadableStream
export async function* pullOllamaModelStream(
  name: string,
): AsyncGenerator<{ status: string; completed?: number; total?: number; error?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/models/ollama/pull`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          yield JSON.parse(line.slice(6));
        } catch {
          // skip malformed line
        }
      }
    }
  }
}
```

- [ ] **Step 2: Extend setup.ts**

Add model fields to `CompleteSetupRequest` and update `complete()`:

```typescript
// In admin-frontend/src/api/setup.ts
// Replace CompleteSetupRequest interface:
export interface CompleteSetupRequest {
  elasticsearch_url: string;
  redis_url: string;
  embedding_provider?: string;
  embedding_model?: string;
  reranker_provider?: string;
  reranker_model?: string;
  llm_provider?: string;
  llm_model?: string;
}
// The complete() function signature stays the same — it already passes config through.
```

- [ ] **Step 3: Extend client.ts Job type and add startEmbedJob**

In `admin-frontend/src/api/client.ts`:

```typescript
// Change line 13 — extend type union:
type: "crawl" | "index" | "embed";

// Add startEmbedJob after existing job functions:
async startEmbedJob(): Promise<Job> {
  return fetchApi<Job>("/jobs/embed", { method: "POST" });
},
```

Find where `startCrawlJob` or `startIndexJob` is defined in client.ts to add `startEmbedJob` in the same `api` object.

- [ ] **Step 4: Commit**

```bash
git add admin-frontend/src/api/models.ts admin-frontend/src/api/setup.ts admin-frontend/src/api/client.ts
git commit -m "feat(frontend): add models API client and extend setup/job types"
```

---

### Task 2: PillToggle Component

**Files:**
- Create: `admin-frontend/src/components/PillToggle.tsx`

- [ ] **Step 1: Create PillToggle**

```typescript
// admin-frontend/src/components/PillToggle.tsx
import { cn } from "@/lib/utils";

interface PillToggleProps {
  value: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  labelOn?: string;
  labelOff?: string;
  className?: string;
}

export function PillToggle({
  value,
  onChange,
  disabled = false,
  labelOn = "ON",
  labelOff = "OFF",
  className,
}: PillToggleProps) {
  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!value)}
      disabled={disabled}
      className={cn(
        "inline-flex items-center rounded-full px-4 py-1 text-sm font-medium transition-colors",
        value
          ? "bg-primary text-primary-foreground"
          : "border border-input bg-background text-muted-foreground",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      {value ? labelOn : labelOff}
    </button>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-frontend/src/components/PillToggle.tsx
git commit -m "feat(frontend): add PillToggle component"
```

---

### Task 3: ModelStepForm Component

**Files:**
- Create: `admin-frontend/src/components/ModelStepForm.tsx`

This is the most complex component — shared between the setup wizard and the `/models` page. It handles provider selection, Ollama dropdown + pull UI, and LiteLLM freetext + validate.

- [ ] **Step 1: Create ModelStepForm**

```typescript
// admin-frontend/src/components/ModelStepForm.tsx
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Download, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
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
import { modelsApi, pullOllamaModelStream } from "@/api/models";
import { cn } from "@/lib/utils";

interface ModelStepFormProps {
  label: string;
  provider: "ollama" | "litellm";
  model: string;
  modelType: "embedding" | "reranker" | "llm";
  onProviderChange: (p: "ollama" | "litellm") => void;
  onModelChange: (m: string) => void;
  onValidated?: (valid: boolean) => void;
}

export function ModelStepForm({
  label,
  provider,
  model,
  modelType,
  onProviderChange,
  onModelChange,
  onValidated,
}: ModelStepFormProps) {
  const queryClient = useQueryClient();
  const [pullInput, setPullInput] = useState("");
  const [pulling, setPulling] = useState(false);
  const [pullProgress, setPullProgress] = useState<{
    status: string;
    completed?: number;
    total?: number;
  } | null>(null);
  const [pullError, setPullError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState<{
    valid: boolean;
    error?: string;
  } | null>(null);

  const { data: ollamaData } = useQuery({
    queryKey: ["ollamaModels"],
    queryFn: modelsApi.listOllamaModels,
    enabled: provider === "ollama",
  });

  const ollamaModels = ollamaData?.models ?? [];

  const handlePull = async () => {
    if (!pullInput.trim()) return;
    setPulling(true);
    setPullError(null);
    setPullProgress({ status: "Starting..." });

    try {
      for await (const event of pullOllamaModelStream(pullInput.trim())) {
        if (event.error) {
          setPullError(event.error);
          setPulling(false);
          return;
        }
        setPullProgress(event);
      }
      await queryClient.invalidateQueries({ queryKey: ["ollamaModels"] });
      onModelChange(`ollama/${pullInput.trim()}`);
      setPullInput("");
      setPullProgress(null);
    } catch (e) {
      setPullError(e instanceof Error ? e.message : "Pull failed");
    } finally {
      setPulling(false);
    }
  };

  const handleDelete = async (name: string) => {
    await modelsApi.deleteOllamaModel(name);
    await queryClient.invalidateQueries({ queryKey: ["ollamaModels"] });
    if (model === `ollama/${name}` || model === name) {
      onModelChange("");
    }
  };

  const handleValidate = async () => {
    setValidating(true);
    setValidation(null);
    try {
      const result = await modelsApi.validateModel(model, provider, modelType);
      setValidation(result);
      onValidated?.(result.valid);
    } finally {
      setValidating(false);
    }
  };

  const pullPercent =
    pullProgress?.total && pullProgress.completed
      ? Math.round((pullProgress.completed / pullProgress.total) * 100)
      : null;

  return (
    <div className="space-y-4">
      <div>
        <Label className="text-sm font-medium mb-2 block">{label}</Label>
        <div className="flex gap-2">
          {(["ollama", "litellm"] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => {
                onProviderChange(p);
                onModelChange("");
                setValidation(null);
              }}
              className={cn(
                "rounded-full px-4 py-1 text-sm font-medium transition-colors",
                provider === p
                  ? "bg-primary text-primary-foreground"
                  : "border border-input bg-background text-muted-foreground hover:bg-muted",
              )}
            >
              {p === "ollama" ? "Ollama (local)" : "LiteLLM"}
            </button>
          ))}
        </div>
      </div>

      {provider === "ollama" ? (
        <div className="space-y-3">
          <div className="flex gap-2 items-center">
            <Select
              value={model.replace("ollama/", "")}
              onValueChange={(v) => onModelChange(`ollama/${v}`)}
            >
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="Select a pulled model..." />
              </SelectTrigger>
              <SelectContent>
                {ollamaModels.map((m) => (
                  <SelectItem key={m.name} value={m.name}>
                    {m.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {model && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="ghost" size="icon">
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete model?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Delete {model.replace("ollama/", "")} from Ollama? This cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => handleDelete(model.replace("ollama/", ""))}
                      className="bg-destructive text-destructive-foreground"
                    >
                      Delete
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Pull new model</Label>
            <div className="flex gap-2">
              <Input
                value={pullInput}
                onChange={(e) => setPullInput(e.target.value)}
                placeholder="e.g. nomic-embed-text"
                disabled={pulling}
                onKeyDown={(e) => e.key === "Enter" && handlePull()}
              />
              <Button
                variant="outline"
                onClick={handlePull}
                disabled={pulling || !pullInput.trim()}
              >
                {pulling ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                {pulling ? "Pulling..." : "Pull"}
              </Button>
            </div>
            {pullProgress && !pullError && (
              <div className="space-y-1">
                {pullPercent !== null && <Progress value={pullPercent} />}
                <p className="text-xs text-muted-foreground">{pullProgress.status}</p>
              </div>
            )}
            {pullError && (
              <p className="text-xs text-destructive">{pullError}</p>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex gap-2 items-center">
            <Input
              value={model}
              onChange={(e) => {
                onModelChange(e.target.value);
                setValidation(null);
                onValidated?.(false);
              }}
              placeholder="e.g. openai/text-embedding-3-small"
            />
            <Button variant="outline" onClick={handleValidate} disabled={validating || !model}>
              {validating ? <Loader2 className="h-4 w-4 animate-spin" /> : "Validate"}
            </Button>
          </div>
          {validation && (
            <div className="flex items-center gap-2 text-sm">
              {validation.valid ? (
                <CheckCircle2 className="h-4 w-4 text-green-600" />
              ) : (
                <XCircle className="h-4 w-4 text-destructive" />
              )}
              <span className={validation.valid ? "text-green-600" : "text-destructive"}>
                {validation.valid ? "Model is valid" : (validation.error ?? "Invalid model")}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-frontend/src/components/ModelStepForm.tsx
git commit -m "feat(frontend): add ModelStepForm component"
```

---

### Task 4: Settings Page — Search Pipeline Card

**Files:**
- Modify: `admin-frontend/src/pages/Settings.tsx`

- [ ] **Step 1: Add pipeline card to Settings**

Add these imports at the top of `Settings.tsx`:

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";  // already imported — merge
import { PillToggle } from "@/components/PillToggle";
import { modelsApi, type PipelineConfig } from "@/api/models";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
```

Add the pipeline query and mutation after the existing `indexStatus` query:

```typescript
  const { data: pipelineConfig } = useQuery({
    queryKey: ["pipelineConfig"],
    queryFn: modelsApi.getPipelineConfig,
  });

  const [pipelineDraft, setPipelineDraft] = useState<Partial<PipelineConfig>>({});

  const updatePipelineMutation = useMutation({
    mutationFn: modelsApi.updatePipelineConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelineConfig"] });
    },
    onError: () => {
      toast({ title: "Failed to update pipeline config", variant: "destructive" });
    },
  });

  const handleToggle = (field: keyof PipelineConfig, value: boolean) => {
    updatePipelineMutation.mutate({ [field]: value });
  };

  const handleNumericBlur = (field: keyof PipelineConfig, value: number) => {
    updatePipelineMutation.mutate({ [field]: value });
  };
```

Add the Search Pipeline card **before** the existing `<div className="space-y-6">` content (before the Elasticsearch Indices section). Insert it as the first card inside the space-y-6 div:

```typescript
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
                  key={pipelineConfig?.[field]}
                  onBlur={(e) =>
                    handleNumericBlur(field, parseInt(e.target.value, 10))
                  }
                  className="w-full"
                />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
```

- [ ] **Step 2: Run pre-commit to check for TypeScript errors**

```bash
cd admin-frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add admin-frontend/src/pages/Settings.tsx
git commit -m "feat(frontend): add Search Pipeline card to Settings page"
```

---

### Task 5: Models Page

**Files:**
- Create: `admin-frontend/src/pages/Models.tsx`

- [ ] **Step 1: Create Models.tsx**

```typescript
// admin-frontend/src/pages/Models.tsx
import { useState } from "react";
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

  // Sync local state from fetched settings on first load
  useState(() => {
    if (settings && !embedding.model) {
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
  });

  const saveMutation = useMutation({
    mutationFn: (patch: Partial<ModelSettings>) => modelsApi.updateSettings(patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["modelSettings"] });
      toast({ title: "Model settings saved." });
    },
    onError: (e) => {
      toast({ title: "Save failed", description: (e as Error).message, variant: "destructive" });
    },
  });

  const embedJobMutation = useMutation({
    mutationFn: () => api.startEmbedJob(),
    onSuccess: (job) => {
      navigate(`/jobs/${job.id}`);
    },
    onError: (e) => {
      toast({ title: "Failed to start embed job", description: (e as Error).message, variant: "destructive" });
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Embedding Model */}
        <Card>
          <CardHeader>
            <CardTitle>Embedding Model</CardTitle>
            <CardDescription>
              Used to embed documents and queries for vector search.
              Changing this model requires re-embedding all documents.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ModelStepForm
              label="Model"
              provider={embedding.provider}
              model={embedding.model}
              modelType="embedding"
              onProviderChange={(p) =>
                setEmbedding((s) => ({ ...s, provider: p, model: "", validated: false }))
              }
              onModelChange={(m) =>
                setEmbedding((s) => ({ ...s, model: m, validated: false }))
              }
              onValidated={(v) =>
                setEmbedding((s) => ({ ...s, validated: v }))
              }
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
                <RefreshCw className="h-4 w-4 mr-2" />
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
                setReranker((s) => ({ ...s, provider: p, model: "", validated: false }))
              }
              onModelChange={(m) =>
                setReranker((s) => ({ ...s, model: m, validated: false }))
              }
              onValidated={(v) =>
                setReranker((s) => ({ ...s, validated: v }))
              }
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
              setLlm((s) => ({ ...s, provider: p, model: "", validated: false }))
            }
            onModelChange={(m) =>
              setLlm((s) => ({ ...s, model: m, validated: false }))
            }
            onValidated={(v) =>
              setLlm((s) => ({ ...s, validated: v }))
            }
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
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd admin-frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add admin-frontend/src/pages/Models.tsx
git commit -m "feat(frontend): add Models page"
```

---

### Task 6: Wire Routing and Sidebar

**Files:**
- Modify: `admin-frontend/src/components/layout/Sidebar.tsx`
- Modify: `admin-frontend/src/App.tsx`

- [ ] **Step 1: Add Models to Sidebar**

In `admin-frontend/src/components/layout/Sidebar.tsx`:

```typescript
// Add Cpu to imports:
import {
  LayoutDashboard,
  Globe,
  Database,
  ListTodo,
  Key,
  Settings,
  Cpu,
} from "lucide-react";

// Add to navItems array, after Dashboard entry:
const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/models", icon: Cpu, label: "Models" },
  { to: "/crawler", icon: Globe, label: "Crawler Config" },
  { to: "/indexer", icon: Database, label: "Indexer Config" },
  { to: "/jobs", icon: ListTodo, label: "Jobs" },
  { to: "/auth", icon: Key, label: "Auth Sessions" },
  { to: "/settings", icon: Settings, label: "Settings" },
];
```

- [ ] **Step 2: Add route to App.tsx**

In `admin-frontend/src/App.tsx`:

```typescript
// Add import:
import { Models } from "@/pages/Models";

// Add route inside the Layout route group:
<Route path="models" element={<Models />} />
```

- [ ] **Step 3: Commit**

```bash
git add admin-frontend/src/components/layout/Sidebar.tsx admin-frontend/src/App.tsx
git commit -m "feat(frontend): add Models route and sidebar entry"
```

---

### Task 7: Extend Setup Wizard

**Files:**
- Modify: `admin-frontend/src/pages/SetupWizard.tsx`

- [ ] **Step 1: Add model step state and step rendering**

The wizard currently has no step concept — it shows everything on one screen. Add a `step` state (1–5) and render each step conditionally.

Add to state at the top of `SetupWizard`:

```typescript
  const [step, setStep] = useState(1);

  const [embeddingProvider, setEmbeddingProvider] = useState<"ollama" | "litellm">("ollama");
  const [embeddingModel, setEmbeddingModel] = useState("ollama/qwen3-embedding:0.6b");
  const [embeddingValidated, setEmbeddingValidated] = useState(true);

  const [rerankerProvider, setRerankerProvider] = useState<"ollama" | "litellm">("ollama");
  const [rerankerModel, setRerankerModel] = useState("ollama/bge-reranker-v2-m3");
  const [rerankerValidated, setRerankerValidated] = useState(true);

  const [llmProvider, setLlmProvider] = useState<"ollama" | "litellm">("litellm");
  const [llmModel, setLlmModel] = useState("gemini/gemini-3-flash-preview");
  const [llmValidated, setLlmValidated] = useState(true);
```

Add import for `ModelStepForm`:

```typescript
import { ModelStepForm } from "@/components/ModelStepForm";
```

- [ ] **Step 2: Wrap existing ES+Redis form in step 1–2 condition**

Wrap the existing `handleValidate` / `handleSubmit` form content in a condition so it only shows when `step <= 2`. Add a progress indicator at the top.

Replace the existing single-form layout with a step-aware structure. The existing form becomes steps 1 and 2 — no logic changes, just wrap in `{step <= 2 && (...)}`.

Add after the existing submit to steps 1–2 a "Next" button that advances to step 3:

```typescript
// Change the existing "Complete Setup" button to:
{step <= 2 ? (
  <Button
    onClick={() => setStep(3)}
    disabled={!esValidation?.ok || !redisValidation?.ok}
  >
    Next
  </Button>
) : null}
```

- [ ] **Step 3: Add steps 3–5**

Below the existing form (after `{step <= 2 && (...)}`) add:

```typescript
      {step === 3 && (
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle>Step 3 of 5 — Embedding Model</CardTitle>
            <CardDescription>
              Model used to embed documents for vector search.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <ModelStepForm
              label="Embedding Model"
              provider={embeddingProvider}
              model={embeddingModel}
              modelType="embedding"
              onProviderChange={setEmbeddingProvider}
              onModelChange={setEmbeddingModel}
              onValidated={setEmbeddingValidated}
            />
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)}>Back</Button>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setEmbeddingModel("ollama/qwen3-embedding:0.6b");
                    setEmbeddingProvider("ollama");
                    setEmbeddingValidated(true);
                    setStep(4);
                  }}
                >
                  Skip — use default
                </Button>
                <Button
                  onClick={() => setStep(4)}
                  disabled={!embeddingModel || (embeddingProvider === "litellm" && !embeddingValidated)}
                >
                  Next
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {step === 4 && (
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle>Step 4 of 5 — Reranker Model</CardTitle>
            <CardDescription>
              Cross-encoder model for re-ranking search results (optional).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <ModelStepForm
              label="Reranker Model"
              provider={rerankerProvider}
              model={rerankerModel}
              modelType="reranker"
              onProviderChange={setRerankerProvider}
              onModelChange={setRerankerModel}
              onValidated={setRerankerValidated}
            />
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(3)}>Back</Button>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setRerankerModel("ollama/bge-reranker-v2-m3");
                    setRerankerProvider("ollama");
                    setRerankerValidated(true);
                    setStep(5);
                  }}
                >
                  Skip — use default
                </Button>
                <Button
                  onClick={() => setStep(5)}
                  disabled={!rerankerModel || (rerankerProvider === "litellm" && !rerankerValidated)}
                >
                  Next
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {step === 5 && (
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle>Step 5 of 5 — LLM Model</CardTitle>
            <CardDescription>
              Language model for AI search and agentic search.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <ModelStepForm
              label="LLM Model"
              provider={llmProvider}
              model={llmModel}
              modelType="llm"
              onProviderChange={setLlmProvider}
              onModelChange={setLlmModel}
              onValidated={setLlmValidated}
            />
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(4)}>Back</Button>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setLlmModel("gemini/gemini-3-flash-preview");
                    setLlmProvider("litellm");
                    setLlmValidated(true);
                    handleComplete();
                  }}
                >
                  Skip — use default
                </Button>
                <Button
                  onClick={handleComplete}
                  disabled={submitting || !llmModel || (llmProvider === "litellm" && !llmValidated)}
                >
                  {submitting ? "Completing..." : "Complete Setup"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
```

- [ ] **Step 4: Extend handleSubmit to pass model settings**

Rename/extend the existing `handleSubmit` to `handleComplete` and pass model fields to `setupApi.complete()`:

```typescript
  const handleComplete = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await setupApi.complete({
        elasticsearch_url: elasticsearchUrl,
        redis_url: redisUrl,
        embedding_provider: embeddingProvider,
        embedding_model: embeddingModel,
        reranker_provider: rerankerProvider,
        reranker_model: rerankerModel,
        llm_provider: llmProvider,
        llm_model: llmModel,
      });
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup failed");
    } finally {
      setSubmitting(false);
    }
  };
```

- [ ] **Step 5: Run TypeScript check**

```bash
cd admin-frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add admin-frontend/src/pages/SetupWizard.tsx
git commit -m "feat(frontend): extend setup wizard with model selection steps 3-5"
```

---

### Task 8: Final Check

- [ ] **Step 1: Run pre-commit**

```bash
pre-commit run --all-files
```

Expected: all checks PASS.

- [ ] **Step 2: TypeScript check**

```bash
cd admin-frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: ESLint check**

```bash
cd admin-frontend && npx eslint src/
```

Expected: no errors.

- [ ] **Step 4: Final commit if any formatting fixes applied**

```bash
git add -p
git commit -m "chore: fix linting after model management frontend"
```
