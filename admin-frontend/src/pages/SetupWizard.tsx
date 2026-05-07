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

export function SetupWizard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(1);

  // Step 1–2: infrastructure
  const [elasticsearchUrl, setElasticsearchUrl] = useState(
    "http://elasticsearch:9200",
  );
  const [redisUrl, setRedisUrl] = useState("redis://redis:6379/0");
  const [validating, setValidating] = useState(false);
  const [esValidation, setEsValidation] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [redisValidation, setRedisValidation] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  // Step 3: embedding model
  const [embeddingProvider, setEmbeddingProvider] = useState<
    "ollama" | "litellm"
  >("ollama");
  const [embeddingModel, setEmbeddingModel] = useState(
    "ollama/qwen3-embedding:0.6b",
  );
  const [embeddingValidated, setEmbeddingValidated] = useState(true);

  // Step 4: reranker model
  const [rerankerProvider, setRerankerProvider] = useState<
    "ollama" | "litellm"
  >("ollama");
  const [rerankerModel, setRerankerModel] = useState(
    "ollama/bge-reranker-v2-m3",
  );
  const [rerankerValidated, setRerankerValidated] = useState(true);

  // Step 5: LLM model
  const [llmProvider, setLlmProvider] = useState<"ollama" | "litellm">(
    "litellm",
  );
  const [llmModel, setLlmModel] = useState("gemini/gemini-3-flash-preview");
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
    setError(null);

    try {
      const result = await setupApi.validate({
        elasticsearch_url: elasticsearchUrl,
        redis_url: redisUrl,
      });
      if (result.elasticsearch) setEsValidation(result.elasticsearch);
      if (result.redis) setRedisValidation(result.redis);
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
                <Input
                  id="elasticsearch-url"
                  value={elasticsearchUrl}
                  onChange={(e) => setElasticsearchUrl(e.target.value)}
                  placeholder="http://elasticsearch:9200"
                  disabled={validating || submitting}
                />
                {esValidation && (
                  <div className="flex items-center gap-2 text-sm">
                    {esValidation.ok ? (
                      <>
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        <span className="text-green-600">
                          {esValidation.message}
                        </span>
                      </>
                    ) : (
                      <>
                        <XCircle className="h-4 w-4 text-red-500" />
                        <span className="text-red-600">
                          {esValidation.message}
                        </span>
                      </>
                    )}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="redis-url">Redis URL</Label>
                <Input
                  id="redis-url"
                  value={redisUrl}
                  onChange={(e) => setRedisUrl(e.target.value)}
                  placeholder="redis://redis:6379/0"
                  disabled={validating || submitting}
                />
                {redisValidation && (
                  <div className="flex items-center gap-2 text-sm">
                    {redisValidation.ok ? (
                      <>
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        <span className="text-green-600">
                          {redisValidation.message}
                        </span>
                      </>
                    ) : (
                      <>
                        <XCircle className="h-4 w-4 text-red-500" />
                        <span className="text-red-600">
                          {redisValidation.message}
                        </span>
                      </>
                    )}
                  </div>
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

            <Alert>
              <AlertDescription className="text-sm text-muted-foreground">
                <strong>Note:</strong> These values can be overridden with
                environment variables (ES_HOST, REDIS_URL). Configuration is
                stored in PostgreSQL for persistence.
              </AlertDescription>
            </Alert>
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
