import { Button } from "@/shared/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import { Alert, AlertDescription } from "@/shared/components/ui/alert";
import { ValidatedHostInput } from "@/shared/components/ValidatedHostInput";
import { AlertCircle, Loader2 } from "lucide-react";
import {
  STEPS,
  TOTAL_STEPS,
  useSetupWizard,
  type ModelStepProvider,
} from "@/shared/contexts/SetupWizardContext";

export function InfrastructureStep() {
  const {
    step,
    error,
    elasticsearchUrl,
    setElasticsearchUrl,
    esValidation,
    redisUrl,
    setRedisUrl,
    redisValidation,
    qdrantHostInput,
    setQdrantHostInput,
    qdrantValidation,
    qdrantFromEnv,
    qdrantHostStatusValue,
    validating,
    submitting,
    handleValidate,
    ollamaAvailable,
    vllmAvailable,
    modelStepState,
    setStep,
  } = useSetupWizard();

  return (
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
          <ValidatedHostInput
            id="elasticsearch-url"
            label="Elasticsearch URL"
            value={elasticsearchUrl}
            onChange={setElasticsearchUrl}
            placeholder="http://elasticsearch:9200"
            disabled={validating || submitting}
            validation={esValidation}
            helperText="Used for full-text search indexing."
          />

          <ValidatedHostInput
            id="redis-url"
            label="Redis URL"
            value={redisUrl}
            onChange={setRedisUrl}
            placeholder="redis://redis:6379/0"
            disabled={validating || submitting}
            validation={redisValidation}
            helperText="Used for crawler session storage and API key caching."
          />

          <ValidatedHostInput
            id="qdrant-host"
            label="Qdrant Host"
            optional
            fromEnvNote={
              qdrantFromEnv
                ? "Set via QDRANT_HOST environment variable — edit the variable to change this value."
                : undefined
            }
            value={
              qdrantFromEnv ? (qdrantHostStatusValue ?? "") : qdrantHostInput
            }
            onChange={setQdrantHostInput}
            placeholder="http://qdrant:6333"
            disabled={qdrantFromEnv || validating || submitting}
            validation={qdrantValidation}
            helperText={
              qdrantFromEnv
                ? "Set via QDRANT_HOST environment variable."
                : "Leave empty to use the default Qdrant connection."
            }
          />
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
              modelStepState[2].setProvider(p);
              modelStepState[3].setProvider(p);
              modelStepState[4].setProvider(p);
              setStep(2);
            }}
            disabled={
              !esValidation?.ok || !redisValidation?.ok || !qdrantValidation?.ok
            }
            className="flex-1"
          >
            Next
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
