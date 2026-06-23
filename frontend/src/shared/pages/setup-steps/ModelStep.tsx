import { Button } from "@/shared/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import { Alert, AlertDescription } from "@/shared/components/ui/alert";
import { ModelStepForm } from "@/shared/components/ModelStepForm";
import { AlertCircle } from "lucide-react";
import {
  STEPS,
  TOTAL_STEPS,
  useSetupWizard,
} from "@/shared/contexts/SetupWizardContext";

interface ModelStepConfig {
  stepId: 2 | 3 | 4;
  formLabel: string;
  description: string;
  modelType: "embedding" | "reranker" | "llm";
  skipLabel: string;
  showError?: boolean;
}

export const MODEL_STEPS: ModelStepConfig[] = [
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

export function ModelStep({ config }: { config: ModelStepConfig }) {
  const {
    step,
    error,
    modelStepState,
    modelStepHint,
    ollamaAvailable,
    vllmAvailable,
    setStep,
  } = useSetupWizard();

  const state = modelStepState[config.stepId];
  const nextStepId = config.stepId + 1;

  return (
    <Card className="w-full max-w-lg">
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
          defaultHint={modelStepHint[config.modelType]}
          ollamaConfigStep={STEPS[0].id}
          modelHostId={state.hostKeyIds.model_host_id}
          apiKeyId={state.hostKeyIds.api_key_id}
          onProviderChange={state.setProvider}
          onModelChange={state.setModel}
          onHostKeyChange={state.onHostKeyChange}
          onValidated={state.setValidated}
        />
        <div className="flex justify-between">
          <Button variant="outline" onClick={() => setStep(config.stepId - 1)}>
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
}
