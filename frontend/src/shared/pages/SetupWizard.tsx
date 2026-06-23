import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { setupApi } from "@/shared/api/setup";
import {
  SetupWizardProvider,
  useSetupWizard,
} from "@/shared/contexts/SetupWizardContext";
import { InfrastructureStep } from "@/shared/pages/setup-steps/InfrastructureStep";
import { ModelStep, MODEL_STEPS } from "@/shared/pages/setup-steps/ModelStep";
import { OidcStep } from "@/shared/pages/setup-steps/OidcStep";

function SetupWizardSteps() {
  const { step } = useSetupWizard();

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-background to-muted/20 p-4">
      {step === 1 && <InfrastructureStep />}
      {MODEL_STEPS.map(
        (config) =>
          step === config.stepId && (
            <ModelStep key={config.stepId} config={config} />
          ),
      )}
      {step === 5 && <OidcStep />}
    </div>
  );
}

export function SetupWizard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);

  useEffect(() => {
    const checkSetupStatus = async () => {
      try {
        const status = await setupApi.getStatus();
        if (status.is_configured) {
          navigate("/");
        }
      } catch (err) {
        setStatusError(
          err instanceof Error ? err.message : "Failed to check setup status",
        );
      } finally {
        setLoading(false);
      }
    };
    checkSetupStatus();
  }, [navigate]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <SetupWizardProvider initialError={statusError}>
      <SetupWizardSteps />
    </SetupWizardProvider>
  );
}
