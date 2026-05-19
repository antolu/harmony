import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { setupApi } from "@/api/setup";
import { ModelStepForm } from "@/components/ModelStepForm";
import { CheckCircle2, XCircle, Loader2, AlertCircle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

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
  const [validating, setValidating] = useState(false);
  type FieldValidation = { ok: boolean; message: string } | null;
  const [esValidation, setEsValidation] = useState<FieldValidation>(null);
  const [redisValidation, setRedisValidation] = useState<FieldValidation>(null);
  const [ollamaValidation, setOllamaValidation] =
    useState<FieldValidation>(null);

  const { data: ollamaHostStatus } = useQuery({
    queryKey: ["ollamaHostStatus"],
    queryFn: setupApi.getOllamaHost,
  });

  const { data: setupDefaults } = useQuery({
    queryKey: ["setupDefaults", ollamaHostInput, ollamaHostStatus?.from_env],
    queryFn: setupApi.getDefaults,
  });

  const ollamaFromEnv = ollamaHostStatus?.from_env ?? false;
  const ollamaAvailable = Boolean(
    ollamaFromEnv ? ollamaHostStatus?.value : ollamaHostInput,
  );

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

  // Step 3: embedding model — default based on ollama availability
  const [embeddingProvider, setEmbeddingProvider] = useState<
    "ollama" | "litellm"
  >("litellm");
  const [embeddingModel, setEmbeddingModel] = useState("");
  const [embeddingValidated, setEmbeddingValidated] = useState(true);

  // Step 4: reranker model
  const [rerankerProvider, setRerankerProvider] = useState<
    "ollama" | "litellm"
  >("litellm");
  const [rerankerModel, setRerankerModel] = useState("");
  const [rerankerValidated, setRerankerValidated] = useState(true);

  // Step 5: LLM model
  const [llmProvider, setLlmProvider] = useState<"ollama" | "litellm">(
    "litellm",
  );
  const [llmModel, setLlmModel] = useState("");
  const [llmValidated, setLlmValidated] = useState(true);

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
    setError(null);

    try {
      const result = await setupApi.validate({
        elasticsearch_url: elasticsearchUrl,
        redis_url: redisUrl,
        ollama_host: ollamaHostInput || undefined,
      });
      if (result.elasticsearch) setEsValidation(result.elasticsearch);
      if (result.redis) setRedisValidation(result.redis);
      if (result.ollama) setOllamaValidation(result.ollama);
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
        embedding_provider: embeddingProvider,
        embedding_model: embeddingModel,
        reranker_provider: rerankerProvider,
        reranker_model: rerankerModel,
        llm_provider: llmProvider,
        llm_model: llmModel,
      });
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup completion failed");
    } finally {
      setSubmitting(false);
    }
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
      {step <= 2 && (
        <Card className="w-full max-w-2xl">
          <CardHeader>
            <CardTitle className="text-3xl">Welcome to Harmony</CardTitle>
            <CardDescription>
              Step {step} of 5 — Configure your Elasticsearch and Redis
              connections
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
                          title={esValidation.message}
                        />
                      ) : (
                        <XCircle
                          className="h-4 w-4 text-destructive"
                          title={esValidation.message}
                        />
                      )}
                    </span>
                  )}
                </div>
                {esValidation && !esValidation.ok && (
                  <p className="text-xs text-destructive">
                    {esValidation.message}
                  </p>
                )}
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
                          title={redisValidation.message}
                        />
                      ) : (
                        <XCircle
                          className="h-4 w-4 text-destructive"
                          title={redisValidation.message}
                        />
                      )}
                    </span>
                  )}
                </div>
                {redisValidation && !redisValidation.ok && (
                  <p className="text-xs text-destructive">
                    {redisValidation.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="ollama-host">
                  Ollama Host{" "}
                  <span className="font-normal text-muted-foreground">
                    (optional)
                  </span>
                </Label>
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
                          title={ollamaValidation.message}
                        />
                      ) : (
                        <XCircle
                          className="h-4 w-4 text-destructive"
                          title={ollamaValidation.message}
                        />
                      )}
                    </span>
                  )}
                </div>
                {ollamaFromEnv && (
                  <p className="text-xs text-muted-foreground">
                    Set via OLLAMA_HOST environment variable.
                  </p>
                )}
                {ollamaValidation && !ollamaValidation.ok && (
                  <p className="text-xs text-destructive">
                    {ollamaValidation.message}
                  </p>
                )}
                {!ollamaFromEnv && !ollamaValidation && (
                  <p className="text-xs text-muted-foreground">
                    Leave empty to skip Ollama — you can use cloud providers
                    instead.
                  </p>
                )}
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
                onClick={() => setStep(3)}
                disabled={!esValidation?.ok || !redisValidation?.ok}
                className="flex-1"
              >
                Next
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

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
              ollamaAvailable={ollamaAvailable}
              defaultHint={setupDefaults?.embedding_model}
              onProviderChange={setEmbeddingProvider}
              onModelChange={setEmbeddingModel}
              onValidated={setEmbeddingValidated}
            />
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)}>
                Back
              </Button>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setEmbeddingModel("");
                    setEmbeddingProvider("litellm");
                    setEmbeddingValidated(true);
                    setStep(4);
                  }}
                >
                  Skip (disable vector search)
                </Button>
                <Button
                  onClick={() => setStep(4)}
                  disabled={
                    !embeddingModel ||
                    (embeddingProvider === "litellm" && !embeddingValidated)
                  }
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
              ollamaAvailable={ollamaAvailable}
              defaultHint={setupDefaults?.reranker_model}
              onProviderChange={setRerankerProvider}
              onModelChange={setRerankerModel}
              onValidated={setRerankerValidated}
            />
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(3)}>
                Back
              </Button>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setRerankerModel("");
                    setRerankerProvider("litellm");
                    setRerankerValidated(true);
                    setStep(5);
                  }}
                >
                  Skip (disable reranking)
                </Button>
                <Button
                  onClick={() => setStep(5)}
                  disabled={
                    !rerankerModel ||
                    (rerankerProvider === "litellm" && !rerankerValidated)
                  }
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
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <ModelStepForm
              label="LLM Model"
              provider={llmProvider}
              model={llmModel}
              modelType="llm"
              ollamaAvailable={ollamaAvailable}
              defaultHint={setupDefaults?.llm_model}
              onProviderChange={setLlmProvider}
              onModelChange={setLlmModel}
              onValidated={setLlmValidated}
            />
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(4)}>
                Back
              </Button>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setLlmModel("");
                    setLlmProvider("litellm");
                    setLlmValidated(true);
                    handleComplete();
                  }}
                >
                  Skip (disable AI search)
                </Button>
                <Button
                  onClick={handleComplete}
                  disabled={
                    submitting ||
                    !llmModel ||
                    (llmProvider === "litellm" && !llmValidated)
                  }
                >
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
