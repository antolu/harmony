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
  ollamaAvailable: boolean;
  ollamaHost?: string;
  defaultHint?: string;
  onProviderChange: (p: "ollama" | "litellm") => void;
  onModelChange: (m: string) => void;
  onValidated?: (valid: boolean) => void;
}

export function ModelStepForm({
  label,
  provider,
  model,
  modelType,
  ollamaAvailable,
  ollamaHost,
  defaultHint,
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

  const {
    data: ollamaData,
    isLoading: ollamaLoading,
    isError: ollamaError,
  } = useQuery({
    queryKey: ["ollamaModels", ollamaHost],
    queryFn: () => modelsApi.listOllamaModels(ollamaHost),
    enabled: provider === "ollama",
    retry: 1,
  });

  const allOllamaModels = ollamaData?.models ?? [];
  const expectedType =
    modelType === "embedding"
      ? "embedding"
      : modelType === "reranker"
        ? "reranker"
        : "chat";
  const ollamaModels = allOllamaModels.filter(
    (m) => m.model_type === expectedType,
  );
  const ollamaUnavailable =
    !ollamaLoading && (ollamaError || ollamaModels.length === 0);

  const handlePull = async () => {
    if (!pullInput.trim()) return;
    setPulling(true);
    setPullError(null);
    setPullProgress({ status: "Starting..." });

    try {
      for await (const event of pullOllamaModelStream(
        pullInput.trim(),
        ollamaHost,
      )) {
        if (event.error) {
          setPullError(event.error);
          setPulling(false);
          return;
        }
        setPullProgress(event);
      }
      await queryClient.invalidateQueries({ queryKey: ["ollamaModels"] });
      onModelChange(`ollama/${pullInput.trim()}`);
      setPullProgress({ status: "Done." });
      setPullInput("");
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
        <Label className="mb-2 block text-sm font-medium">{label}</Label>
        <div className="flex gap-2">
          {(["ollama", "litellm"] as const).map((p) => {
            const disabled = p === "ollama" && !ollamaAvailable;
            return (
              <button
                key={p}
                type="button"
                aria-pressed={provider === p}
                aria-label={
                  p === "ollama"
                    ? "Select Ollama provider"
                    : "Select LiteLLM provider"
                }
                disabled={disabled}
                onClick={() => {
                  if (disabled) return;
                  onProviderChange(p);
                  onModelChange("");
                  setValidation(null);
                }}
                className={cn(
                  "rounded-full px-4 py-1 text-sm font-medium transition-colors",
                  disabled
                    ? "cursor-not-allowed border border-input bg-background text-muted-foreground/40"
                    : provider === p
                      ? "bg-primary text-primary-foreground"
                      : "border border-input bg-background text-muted-foreground hover:bg-muted",
                )}
              >
                {p === "ollama" ? "Ollama (local)" : "LiteLLM"}
              </button>
            );
          })}
        </div>
        {!ollamaAvailable && (
          <p className="text-xs text-muted-foreground">
            Configure an Ollama host in step 1 to enable local models.
          </p>
        )}
      </div>

      {provider === "ollama" ? (
        <div className="space-y-3">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Select
                value={model.replace("ollama/", "")}
                onValueChange={(v) => onModelChange(`ollama/${v}`)}
                disabled={ollamaUnavailable || ollamaLoading}
              >
                <SelectTrigger className="flex-1">
                  <SelectValue
                    placeholder={
                      ollamaLoading
                        ? "Loading models…"
                        : ollamaError
                          ? "Ollama unreachable"
                          : ollamaModels.length === 0
                            ? `No ${expectedType} models pulled`
                            : "Select model"
                    }
                  />
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
                        Delete {model.replace("ollama/", "")} from Ollama? This
                        cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() =>
                          handleDelete(model.replace("ollama/", ""))
                        }
                        className="bg-destructive text-destructive-foreground"
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
            {ollamaError && (
              <p className="text-xs text-destructive">
                Ollama is unreachable. Check that it's running and the host is
                configured correctly.
              </p>
            )}
            {!ollamaError && !ollamaLoading && ollamaModels.length === 0 && (
              <p className="text-xs text-muted-foreground">
                {allOllamaModels.length === 0
                  ? "No models pulled yet. Pull a model below to get started."
                  : `No ${expectedType} models available. Pull one below.`}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">
              Pull new model
            </Label>
            <div className="flex gap-2">
              <Input
                value={pullInput}
                onChange={(e) => {
                  setPullInput(e.target.value);
                  setPullProgress(null);
                  setPullError(null);
                }}
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
            <div className="min-h-[2.5rem] space-y-1">
              {(pullProgress || pullError) && (
                <>
                  <Progress
                    value={pullPercent ?? (pullError ? 0 : undefined)}
                    className={pullError ? "opacity-30" : ""}
                  />
                  <p
                    className={`text-xs ${pullError ? "text-destructive" : "text-muted-foreground"}`}
                  >
                    {pullError ?? pullProgress?.status}
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Input
              value={model}
              onChange={(e) => {
                onModelChange(e.target.value);
                setValidation(null);
                onValidated?.(false);
              }}
              placeholder={
                defaultHint
                  ? `e.g. ${defaultHint}`
                  : "e.g. openai/text-embedding-3-small"
              }
            />
            <Button
              variant="outline"
              onClick={handleValidate}
              disabled={validating || !model}
            >
              {validating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Validate"
              )}
            </Button>
          </div>
          {validation && (
            <div className="flex items-center gap-2 text-sm">
              {validation.valid ? (
                <CheckCircle2 className="h-4 w-4 text-green-600" />
              ) : (
                <XCircle className="h-4 w-4 text-destructive" />
              )}
              <span
                className={
                  validation.valid ? "text-green-600" : "text-destructive"
                }
              >
                {validation.valid
                  ? "Model is valid"
                  : (validation.error ?? "Invalid model")}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
