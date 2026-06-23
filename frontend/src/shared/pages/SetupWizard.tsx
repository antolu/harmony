import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import { Alert, AlertDescription } from "@/shared/components/ui/alert";
import { Switch } from "@/shared/components/ui/switch";
import { setupApi } from "@/shared/api/setup";
import { saveOidcSettings } from "@/shared/api/auth";
import { ModelStepForm } from "@/shared/components/ModelStepForm";
import {
  useModelStepState,
  type ModelStepProvider,
} from "@/shared/hooks/useModelStepState";
import { CheckCircle2, XCircle, Loader2, AlertCircle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/shared/api/client";

const STEPS = [
  { id: 1, label: "Infrastructure" },
  { id: 2, label: "Embedding Model" },
  { id: 3, label: "Reranker Model" },
  { id: 4, label: "LLM Model" },
  { id: 5, label: "Single Sign-On" },
] as const;

const TOTAL_STEPS = STEPS.length;

interface ModelStepConfig {
  stepId: 2 | 3 | 4;
  formLabel: string;
  description: string;
  modelType: "embedding" | "reranker" | "llm";
  skipLabel: string;
  showError?: boolean;
}

const MODEL_STEPS: ModelStepConfig[] = [
  {
    stepId: 2,
    formLabel: "Embedding Model",
    description: "Model used to embed documents for vector search.",
    modelType: "embedding",
    skipLabel: "Skip (disable vector search)",
  },
  {
    stepId: 3,
    formLabel: "Reranker Model",
    description:
      "Cross-encoder model for re-ranking search results (optional).",
    modelType: "reranker",
    skipLabel: "Skip (disable reranking)",
  },
  {
    stepId: 4,
    formLabel: "LLM Model",
    description: "Language model for AI search and agentic search.",
    modelType: "llm",
    skipLabel: "Skip (disable AI search)",
    showError: true,
  },
];

export function SetupWizard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(1);

  // Step 1–2: infrastructure
  const [elasticsearchUrl, setElasticsearchUrl] = useState(
    "http://elasticsearch:9200",
  );
  const [redisUrl, setRedisUrl] = useState("redis://redis:6379/0");
  const [ollamaHostInput, setOllamaHostInput] = useState("");
  const [qdrantHostInput, setQdrantHostInput] = useState("");
  const [validating, setValidating] = useState(false);
  type FieldValidation = { ok: boolean; message: string } | null;
  const [esValidation, setEsValidation] = useState<FieldValidation>(null);
  const [redisValidation, setRedisValidation] = useState<FieldValidation>(null);
  const [ollamaValidation, setOllamaValidation] =
    useState<FieldValidation>(null);
  const [qdrantValidation, setQdrantValidation] =
    useState<FieldValidation>(null);

  const { data: ollamaHostStatus } = useQuery({
    queryKey: ["ollamaHostStatus"],
    queryFn: setupApi.getOllamaHost,
  });

  const { data: qdrantHostStatus } = useQuery({
    queryKey: ["qdrantHostStatus"],
    queryFn: setupApi.getQdrantHost,
  });

  const { data: setupDefaults } = useQuery({
    queryKey: ["setupDefaults", ollamaHostInput, ollamaHostStatus?.from_env],
    queryFn: setupApi.getDefaults,
  });

  const ollamaFromEnv = ollamaHostStatus?.from_env ?? false;
  const ollamaAvailable = Boolean(
    ollamaFromEnv ? ollamaHostStatus?.value : ollamaHostInput,
  );

  const { data: ollamaHosts } = useQuery({
    queryKey: ["ollamaHosts"],
    queryFn: api.listOllamaHosts,
  });
  const vllmAvailable = (ollamaHosts ?? []).some((h) => h.host_type === "vllm");

  const qdrantFromEnv = qdrantHostStatus?.from_env ?? false;

  // pre-fill from last saved value (when not from env)
  useEffect(() => {
    if (
      ollamaHostStatus &&
      !ollamaHostStatus.from_env &&
      ollamaHostStatus.value
    ) {
      setOllamaHostInput(ollamaHostStatus.value);
    }
  }, [ollamaHostStatus]);

  useEffect(() => {
    if (
      qdrantHostStatus &&
      !qdrantHostStatus.from_env &&
      qdrantHostStatus.value
    ) {
      setQdrantHostInput(qdrantHostStatus.value);
    }
  }, [qdrantHostStatus]);

  // Steps 2–4: embedding / reranker / LLM models
  const embeddingStep = useModelStepState("litellm");
  const rerankerStep = useModelStepState("litellm");
  const llmStep = useModelStepState("litellm");

  const modelStepState: Record<
    2 | 3 | 4,
    ReturnType<typeof useModelStepState>
  > = {
    2: embeddingStep,
    3: rerankerStep,
    4: llmStep,
  };

  const modelStepHint: Record<
    "embedding" | "reranker" | "llm",
    string | undefined
  > = {
    embedding: setupDefaults?.embedding_model,
    reranker: setupDefaults?.reranker_model,
    llm: setupDefaults?.llm_model,
  };

  // Step 5: OIDC
  const [oidcEnabled, setOidcEnabled] = useState(false);
  const [oidcIssuerUrl, setOidcIssuerUrl] = useState("");
  const [oidcClientId, setOidcClientId] = useState("");
  const [oidcClientSecret, setOidcClientSecret] = useState("");
  const [oidcScopes, setOidcScopes] = useState("openid profile email");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    checkSetupStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const checkSetupStatus = async () => {
    try {
      const status = await setupApi.getStatus();
      if (status.is_configured) {
        navigate("/");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to check setup status",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async () => {
    setValidating(true);
    setEsValidation(null);
    setRedisValidation(null);
    setOllamaValidation(null);
    setQdrantValidation(null);
    setError(null);

    try {
      const result = await setupApi.validate({
        elasticsearch_url: elasticsearchUrl,
        redis_url: redisUrl,
        ollama_host:
          (ollamaFromEnv ? ollamaHostStatus?.value : ollamaHostInput) ||
          undefined,
        qdrant_host:
          (qdrantFromEnv ? qdrantHostStatus?.value : qdrantHostInput) ||
          undefined,
      });
      if (result.elasticsearch) setEsValidation(result.elasticsearch);
      if (result.redis) setRedisValidation(result.redis);
      if (result.ollama) setOllamaValidation(result.ollama);
      if (result.qdrant) setQdrantValidation(result.qdrant);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setValidating(false);
    }
  };

  const handleComplete = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await setupApi.complete({
        elasticsearch_url: elasticsearchUrl,
        redis_url: redisUrl,
        ollama_host: ollamaFromEnv ? undefined : ollamaHostInput || undefined,
        qdrant_host: qdrantFromEnv ? undefined : qdrantHostInput || undefined,
        embedding_provider: embeddingStep.provider,
        embedding_model: embeddingStep.model,
        embedding_ollama_host_id: embeddingStep.hostKeyIds.ollama_host_id,
        embedding_api_key_id: embeddingStep.hostKeyIds.api_key_id,
        reranker_provider: rerankerStep.provider,
        reranker_model: rerankerStep.model,
        reranker_ollama_host_id: rerankerStep.hostKeyIds.ollama_host_id,
        reranker_api_key_id: rerankerStep.hostKeyIds.api_key_id,
        llm_provider: llmStep.provider,
        llm_model: llmStep.model,
        llm_ollama_host_id: llmStep.hostKeyIds.ollama_host_id,
        llm_api_key_id: llmStep.hostKeyIds.api_key_id,
      });
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup completion failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleOidcSave = async () => {
    if (oidcEnabled) {
      await saveOidcSettings({
        oidcEnabled,
        issuerUrl: oidcIssuerUrl,
        clientId: oidcClientId,
        clientSecret: oidcClientSecret,
        scopes: oidcScopes,
      });
    }
    await handleComplete();
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-background to-muted/20 p-4">
      {step === 1 && (
        <Card className="w-full max-w-2xl">
          <CardHeader>
            <CardTitle className="text-3xl">Welcome to Harmony</CardTitle>
            <CardDescription>
              Step {step} of {TOTAL_STEPS} — {STEPS[step - 1].label}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="elasticsearch-url">Elasticsearch URL</Label>
                <div className="relative">
                  <Input
                    id="elasticsearch-url"
                    value={elasticsearchUrl}
                    onChange={(e) => {
                      setElasticsearchUrl(e.target.value);
                      setEsValidation(null);
                    }}
                    placeholder="http://elasticsearch:9200"
                    disabled={validating || submitting}
                    className={esValidation ? "pr-8" : ""}
                  />
                  {esValidation && (
                    <span className="absolute right-2.5 top-1/2 -translate-y-1/2">
                      {esValidation.ok ? (
                        <CheckCircle2
                          className="h-4 w-4 text-green-500"
                          aria-label={esValidation.message}
                        />
                      ) : (
                        <XCircle
                          className="h-4 w-4 text-destructive"
                          aria-label={esValidation.message}
                        />
                      )}
                    </span>
                  )}
                </div>
                <p className="text-xs text-destructive min-h-[1rem]">
                  {esValidation && !esValidation.ok ? esValidation.message : ""}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="redis-url">Redis URL</Label>
                <div className="relative">
                  <Input
                    id="redis-url"
                    value={redisUrl}
                    onChange={(e) => {
                      setRedisUrl(e.target.value);
                      setRedisValidation(null);
                    }}
                    placeholder="redis://redis:6379/0"
                    disabled={validating || submitting}
                    className={redisValidation ? "pr-8" : ""}
                  />
                  {redisValidation && (
                    <span className="absolute right-2.5 top-1/2 -translate-y-1/2">
                      {redisValidation.ok ? (
                        <CheckCircle2
                          className="h-4 w-4 text-green-500"
                          aria-label={redisValidation.message}
                        />
                      ) : (
                        <XCircle
                          className="h-4 w-4 text-destructive"
                          aria-label={redisValidation.message}
                        />
                      )}
                    </span>
                  )}
                </div>
                <p className="text-xs text-destructive min-h-[1rem]">
                  {redisValidation && !redisValidation.ok
                    ? redisValidation.message
                    : ""}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="ollama-host">
                  Ollama Host{" "}
                  <span className="font-normal text-muted-foreground">
                    (optional)
                  </span>
                </Label>
                {ollamaFromEnv && (
                  <p className="text-xs text-muted-foreground">
                    Set via <code>OLLAMA_HOST</code> environment variable — edit
                    the variable to change this value.
                  </p>
                )}
                <div className="relative">
                  <Input
                    id="ollama-host"
                    value={
                      ollamaFromEnv
                        ? (ollamaHostStatus?.value ?? "")
                        : ollamaHostInput
                    }
                    onChange={(e) => {
                      setOllamaHostInput(e.target.value);
                      setOllamaValidation(null);
                    }}
                    placeholder="http://host.docker.internal:11434"
                    disabled={ollamaFromEnv || validating || submitting}
                    className={ollamaValidation ? "pr-8" : ""}
                  />
                  {ollamaValidation && (
                    <span className="absolute right-2.5 top-1/2 -translate-y-1/2">
                      {ollamaValidation.ok ? (
                        <CheckCircle2
                          className="h-4 w-4 text-green-500"
                          aria-label={ollamaValidation.message}
                        />
                      ) : (
                        <XCircle
                          className="h-4 w-4 text-destructive"
                          aria-label={ollamaValidation.message}
                        />
                      )}
                    </span>
                  )}
                </div>
                <p
                  className={`text-xs min-h-[1rem] ${ollamaValidation && !ollamaValidation.ok ? "text-destructive" : "text-muted-foreground"}`}
                >
                  {ollamaFromEnv
                    ? "Set via OLLAMA_HOST environment variable."
                    : ollamaValidation && !ollamaValidation.ok
                      ? ollamaValidation.message
                      : "Leave empty to skip Ollama — you can use cloud providers instead."}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="qdrant-host">
                  Qdrant Host{" "}
                  <span className="font-normal text-muted-foreground">
                    (optional)
                  </span>
                </Label>
                {qdrantFromEnv && (
                  <p className="text-xs text-muted-foreground">
                    Set via <code>QDRANT_HOST</code> environment variable — edit
                    the variable to change this value.
                  </p>
                )}
                <div className="relative">
                  <Input
                    id="qdrant-host"
                    value={
                      qdrantFromEnv
                        ? (qdrantHostStatus?.value ?? "")
                        : qdrantHostInput
                    }
                    onChange={(e) => {
                      setQdrantHostInput(e.target.value);
                      setQdrantValidation(null);
                    }}
                    placeholder="http://qdrant:6333"
                    disabled={qdrantFromEnv || validating || submitting}
                    className={qdrantValidation ? "pr-8" : ""}
                  />
                  {qdrantValidation && (
                    <span className="absolute right-2.5 top-1/2 -translate-y-1/2">
                      {qdrantValidation.ok ? (
                        <CheckCircle2
                          className="h-4 w-4 text-green-500"
                          aria-label={qdrantValidation.message}
                        />
                      ) : (
                        <XCircle
                          className="h-4 w-4 text-destructive"
                          aria-label={qdrantValidation.message}
                        />
                      )}
                    </span>
                  )}
                </div>
                <p
                  className={`text-xs min-h-[1rem] ${qdrantValidation && !qdrantValidation.ok ? "text-destructive" : "text-muted-foreground"}`}
                >
                  {qdrantFromEnv
                    ? "Set via QDRANT_HOST environment variable."
                    : qdrantValidation && !qdrantValidation.ok
                      ? qdrantValidation.message
                      : "Leave empty to use the default Qdrant connection."}
                </p>
              </div>
            </div>

            <div className="flex gap-3 pt-4">
              <Button
                onClick={handleValidate}
                disabled={
                  validating || submitting || !elasticsearchUrl || !redisUrl
                }
                variant="outline"
                className="flex-1"
              >
                {validating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Validating...
                  </>
                ) : (
                  "Test Connections"
                )}
              </Button>

              <Button
                onClick={() => {
                  const p: ModelStepProvider = ollamaAvailable
                    ? "ollama"
                    : vllmAvailable
                      ? "hosted_vllm"
                      : "litellm";
                  embeddingStep.setProvider(p);
                  rerankerStep.setProvider(p);
                  llmStep.setProvider(p);
                  setStep(2);
                }}
                disabled={
                  !esValidation?.ok ||
                  !redisValidation?.ok ||
                  !qdrantValidation?.ok
                }
                className="flex-1"
              >
                Next
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {MODEL_STEPS.map((config) => {
        if (step !== config.stepId) return null;
        const state = modelStepState[config.stepId];
        const nextStepId = config.stepId + 1;
        return (
          <Card key={config.stepId} className="w-full max-w-lg">
            <CardHeader>
              <CardTitle>
                Step {step} of {TOTAL_STEPS} — {STEPS[step - 1].label}
              </CardTitle>
              <CardDescription>{config.description}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {config.showError && error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <ModelStepForm
                label={config.formLabel}
                provider={state.provider}
                model={state.model}
                modelType={config.modelType}
                ollamaAvailable={ollamaAvailable}
                vllmAvailable={vllmAvailable}
                ollamaHost={
                  ollamaFromEnv ? ollamaHostStatus?.value : ollamaHostInput
                }
                defaultHint={modelStepHint[config.modelType]}
                ollamaConfigStep={STEPS[0].id}
                ollamaHostId={state.hostKeyIds.ollama_host_id}
                apiKeyId={state.hostKeyIds.api_key_id}
                onProviderChange={state.setProvider}
                onModelChange={state.setModel}
                onHostKeyChange={state.onHostKeyChange}
                onValidated={state.setValidated}
              />
              <div className="flex justify-between">
                <Button
                  variant="outline"
                  onClick={() => setStep(config.stepId - 1)}
                >
                  Back
                </Button>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      state.reset();
                      setStep(nextStepId);
                    }}
                  >
                    {config.skipLabel}
                  </Button>
                  <Button
                    onClick={() => setStep(nextStepId)}
                    disabled={
                      !state.model ||
                      (state.provider === "litellm" && !state.validated)
                    }
                  >
                    Next
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
      {step === 5 && (
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle>
              Step {step} of {TOTAL_STEPS} — Single Sign-On
            </CardTitle>
            <CardDescription>
              Optional. Enable OIDC login for admin access.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <Switch
                  id="wizard-oidc-enabled"
                  checked={oidcEnabled}
                  onCheckedChange={setOidcEnabled}
                />
                <Label htmlFor="wizard-oidc-enabled">Enable OIDC Login</Label>
              </div>

              <div className="space-y-1">
                <Label>Issuer URL</Label>
                <Input
                  placeholder="https://your-idp.example.com/realms/harmony"
                  value={oidcIssuerUrl}
                  onChange={(e) => setOidcIssuerUrl(e.target.value)}
                  disabled={!oidcEnabled}
                />
              </div>

              <div className="space-y-1">
                <Label>Client ID</Label>
                <Input
                  placeholder="harmony-admin"
                  value={oidcClientId}
                  onChange={(e) => setOidcClientId(e.target.value)}
                  disabled={!oidcEnabled}
                />
              </div>

              <div className="space-y-1">
                <Label>Client Secret</Label>
                <Input
                  type="password"
                  placeholder="••••••••"
                  value={oidcClientSecret}
                  onChange={(e) => setOidcClientSecret(e.target.value)}
                  disabled={!oidcEnabled}
                />
              </div>

              <div className="space-y-1">
                <Label>Scopes</Label>
                <Input
                  value={oidcScopes}
                  onChange={(e) => setOidcScopes(e.target.value)}
                  disabled={!oidcEnabled}
                />
                <p className="text-xs text-muted-foreground">
                  Space-separated. Must include openid.
                </p>
              </div>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(4)}>
                Back
              </Button>
              <div className="flex gap-2">
                <Button variant="ghost" onClick={handleComplete}>
                  Skip (configure later)
                </Button>
                <Button onClick={handleOidcSave} disabled={submitting}>
                  {submitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Completing...
                    </>
                  ) : (
                    "Complete Setup"
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
