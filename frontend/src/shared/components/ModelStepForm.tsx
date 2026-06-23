import { useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Download, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Progress } from "@/shared/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
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
import { modelsApi, pullOllamaModelStream } from "@/shared/api/models";
import { cn } from "@/shared/lib/utils";
import { api } from "@/shared/api/client";
import { Combobox } from "@/shared/components/ui/combobox";

interface ModelStepFormProps {
  label: string;
  provider: "ollama" | "litellm";
  model: string;
  modelType: "embedding" | "reranker" | "llm";
  ollamaAvailable: boolean;
  ollamaHost?: string;
  defaultHint?: string;
  ollamaConfigStep?: number | string;
  ollamaHostId?: string;
  apiKeyId?: string;
  onProviderChange: (p: "ollama" | "litellm") => void;
  onHostKeyChange: (ids: {
    ollama_host_id?: string;
    api_key_id?: string;
  }) => void;
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
  ollamaConfigStep,
  ollamaHostId = "",
  apiKeyId = "",
  onProviderChange,
  onHostKeyChange,
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
  const [pullSpeed, setPullSpeed] = useState<string | null>(null);
  const [pullEta, setPullEta] = useState<string | null>(null);
  const pullLastRef = useRef<{ completed: number; ts: number } | null>(null);
  const [pullError, setPullError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState<{
    ok: boolean;
    error?: string;
  } | null>(null);

  const [newApiKeyValue, setNewApiKeyValue] = useState("");
  const [newApiKeyName, setNewApiKeyName] = useState("");
  const [newHostName, setNewHostName] = useState("");
  const [newHostUrl, setNewHostUrl] = useState(
    "http://host.docker.internal:11434",
  );
  const [newHostCreating, setNewHostCreating] = useState(false);
  const [newKeyCreating, setNewKeyCreating] = useState(false);

  const { data: ollamaHosts } = useQuery({
    queryKey: ["ollamaHosts"],
    queryFn: api.listOllamaHosts,
  });

  const { data: llmApiKeys } = useQuery({
    queryKey: ["llmApiKeys"],
    queryFn: api.listLlmApiKeys,
  });

  const selectedHost = ollamaHosts?.find((h) => h.id === ollamaHostId);
  const effectiveOllamaHost = selectedHost?.url || ollamaHost;

  const handleCreateHost = async () => {
    if (!newHostName || !newHostUrl) return;
    setNewHostCreating(true);
    try {
      const host = await api.createOllamaHost(
        newHostName,
        newHostUrl,
        "ollama",
      );
      await queryClient.invalidateQueries({ queryKey: ["ollamaHosts"] });
      onHostKeyChange({ ollama_host_id: host.id });
    } finally {
      setNewHostCreating(false);
    }
  };

  const handleCreateKey = async () => {
    if (!newApiKeyValue || !newApiKeyName) return;
    setNewKeyCreating(true);
    try {
      const key = await api.createLlmApiKey(newApiKeyName, newApiKeyValue);
      await queryClient.invalidateQueries({ queryKey: ["llmApiKeys"] });
      setNewApiKeyValue("");
      setNewApiKeyName("");
      onHostKeyChange({ api_key_id: key.id });
    } finally {
      setNewKeyCreating(false);
    }
  };

  const {
    data: ollamaData,
    isLoading: ollamaLoading,
    isError: ollamaError,
  } = useQuery({
    queryKey: ["ollamaModels", effectiveOllamaHost],
    queryFn: () => modelsApi.listOllamaModels(effectiveOllamaHost),
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
    setPullSpeed(null);
    setPullEta(null);
    setPullProgress({ status: "Starting..." });
    pullLastRef.current = null;

    try {
      for await (const event of pullOllamaModelStream(
        pullInput.trim(),
        effectiveOllamaHost,
      )) {
        if (event.error) {
          setPullError(event.error);
          setPulling(false);
          return;
        }
        setPullProgress(event);

        if (event.completed && event.total) {
          const now = Date.now();
          const last = pullLastRef.current;
          if (last && now - last.ts > 500) {
            const bytesDelta = event.completed - last.completed;
            const secsDelta = (now - last.ts) / 1000;
            const bytesPerSec = bytesDelta / secsDelta;
            const remaining = event.total - event.completed;
            const etaSecs = bytesPerSec > 0 ? remaining / bytesPerSec : null;
            setPullSpeed(formatBytes(bytesPerSec) + "/s");
            setPullEta(etaSecs !== null ? formatEta(etaSecs) : null);
          }
          if (!last || now - last.ts > 500) {
            pullLastRef.current = { completed: event.completed, ts: now };
          }
        }
      }
      await queryClient.invalidateQueries({ queryKey: ["ollamaModels"] });
      onModelChange(`ollama/${pullInput.trim()}`);
      setPullProgress({ status: "Done." });
      setPullSpeed(null);
      setPullEta(null);
      setPullInput("");
    } catch (e) {
      setPullError(e instanceof Error ? e.message : "Pull failed");
    } finally {
      setPulling(false);
    }
  };

  function formatBytes(bytes: number): string {
    if (bytes >= 1e9) return (bytes / 1e9).toFixed(1) + " GB";
    if (bytes >= 1e6) return (bytes / 1e6).toFixed(1) + " MB";
    if (bytes >= 1e3) return (bytes / 1e3).toFixed(1) + " KB";
    return bytes.toFixed(0) + " B";
  }

  function formatEta(secs: number): string {
    if (secs >= 3600) return Math.round(secs / 3600) + "h";
    if (secs >= 60) return Math.round(secs / 60) + "m";
    return Math.round(secs) + "s";
  }

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
      const result = await modelsApi.validateModel(model, provider, modelType, {
        api_key_id: apiKeyId || undefined,
      });
      setValidation(result);
      onValidated?.(result.ok);
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
          <p className="mt-2 pl-1 text-xs text-muted-foreground">
            {ollamaConfigStep !== undefined
              ? `Configure an Ollama host in step ${ollamaConfigStep} to enable local models.`
              : "Configure an Ollama host to enable local models."}
          </p>
        )}
      </div>

      {provider === "ollama" ? (
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Ollama Host</Label>
            {ollamaHosts && ollamaHosts.length === 0 ? (
              // D-06 assumes pre-created hosts, but this exception handles first-run where none exist
              <div className="space-y-2 rounded-md border p-3">
                <p className="text-xs text-muted-foreground">
                  No hosts found. Create one to continue.
                </p>
                <div className="space-y-2">
                  <Input
                    placeholder="Host Name (e.g. Local Mac)"
                    value={newHostName}
                    onChange={(e) => setNewHostName(e.target.value)}
                  />
                  <Input
                    placeholder="URL (e.g. http://host.docker.internal:11434)"
                    value={newHostUrl}
                    onChange={(e) => setNewHostUrl(e.target.value)}
                  />
                  <Button
                    size="sm"
                    onClick={handleCreateHost}
                    disabled={newHostCreating || !newHostName || !newHostUrl}
                  >
                    {newHostCreating ? (
                      <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                    ) : null}
                    Create Host
                  </Button>
                </div>
              </div>
            ) : (
              <Combobox
                options={(ollamaHosts ?? []).map((h) => h.name)}
                value={selectedHost?.name ?? ""}
                onChange={(v) => {
                  const id = ollamaHosts?.find((h) => h.name === v)?.id ?? "";
                  onHostKeyChange({ ollama_host_id: id });
                }}
                placeholder="Select host..."
                searchPlaceholder="Search hosts..."
              />
            )}
          </div>
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
                  setPullSpeed(null);
                  setPullEta(null);
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
                  <div className="flex justify-between">
                    <p
                      className={`text-xs ${pullError ? "text-destructive" : "text-muted-foreground"}`}
                    >
                      {pullError ?? pullProgress?.status}
                    </p>
                    {(pullSpeed || pullEta) && (
                      <p className="text-xs text-muted-foreground tabular-nums">
                        {[pullSpeed, pullEta ? `ETA ${pullEta}` : null]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    )}
                  </div>
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
              {validation.ok ? (
                <CheckCircle2 className="h-4 w-4 text-green-600" />
              ) : (
                <XCircle className="h-4 w-4 text-destructive" />
              )}
              <span
                className={
                  validation.ok ? "text-green-600" : "text-destructive"
                }
              >
                {validation.ok
                  ? "Model is valid"
                  : (validation.error ?? "Invalid model")}
              </span>
            </div>
          )}

          <div className="space-y-3 pt-4 border-t mt-4">
            <div className="space-y-1">
              <Label>API Key</Label>
              <Combobox
                options={(llmApiKeys ?? []).map((k) => k.name)}
                value={llmApiKeys?.find((k) => k.id === apiKeyId)?.name ?? ""}
                onChange={(v) => {
                  const id = llmApiKeys?.find((k) => k.name === v)?.id ?? "";
                  onHostKeyChange({ api_key_id: id });
                  setNewApiKeyValue("");
                  setNewApiKeyName("");
                }}
                placeholder="Select existing key..."
                searchPlaceholder="Search keys..."
              />
            </div>
            <Input
              type="password"
              value={newApiKeyValue}
              onChange={(e) => {
                setNewApiKeyValue(e.target.value);
                onHostKeyChange({ api_key_id: "" });
              }}
              placeholder="...or paste a new key"
            />
            {newApiKeyValue.length > 0 && (
              <div className="space-y-2">
                <Label>Name this key</Label>
                <div className="flex gap-2">
                  <Input
                    value={newApiKeyName}
                    onChange={(e) => setNewApiKeyName(e.target.value)}
                    placeholder="e.g. Production OpenAI key"
                  />
                  <Button
                    onClick={handleCreateKey}
                    disabled={newKeyCreating || !newApiKeyName}
                  >
                    {newKeyCreating ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : null}
                    Save Key
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
