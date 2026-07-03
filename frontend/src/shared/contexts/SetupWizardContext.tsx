import { createContext, useContext, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { setupApi } from "@/shared/api/setup";
import { saveOidcSettings } from "@/shared/api/auth";
import { api } from "@/shared/api/client";
import {
  useModelStepState,
  type ModelStepProvider,
} from "@/shared/hooks/useModelStepState";
import type { FieldValidation } from "@/shared/components/ValidatedHostInput";

export const STEPS = [
  { id: 1, label: "Infrastructure" },
  { id: 2, label: "Embedding Model" },
  { id: 3, label: "Reranker Model" },
  { id: 4, label: "LLM Model" },
  { id: 5, label: "Single Sign-On" },
] as const;

export const TOTAL_STEPS = STEPS.length;

interface SetupWizardContextValue {
  step: number;
  setStep: (step: number) => void;
  error: string | null;
  submitting: boolean;

  elasticsearchUrl: string;
  setElasticsearchUrl: (v: string) => void;
  esValidation: FieldValidation | null;
  redisUrl: string;
  setRedisUrl: (v: string) => void;
  redisValidation: FieldValidation | null;
  qdrantHostInput: string;
  setQdrantHostInput: (v: string) => void;
  qdrantValidation: FieldValidation | null;
  qdrantFromEnv: boolean;
  qdrantHostStatusValue?: string;
  validating: boolean;
  handleValidate: () => Promise<void>;

  ollamaAvailable: boolean;
  vllmAvailable: boolean;

  modelStepState: Record<2 | 3 | 4, ReturnType<typeof useModelStepState>>;
  modelStepHint: Record<"embedding" | "reranker" | "llm", string | undefined>;

  oidcEnabled: boolean;
  setOidcEnabled: (v: boolean) => void;
  oidcIssuerUrl: string;
  setOidcIssuerUrl: (v: string) => void;
  oidcClientId: string;
  setOidcClientId: (v: string) => void;
  oidcClientSecret: string;
  setOidcClientSecret: (v: string) => void;
  oidcScopes: string;
  setOidcScopes: (v: string) => void;

  handleComplete: () => Promise<void>;
  handleOidcSave: () => Promise<void>;
}

const SetupWizardContext = createContext<SetupWizardContextValue | null>(null);

export function SetupWizardProvider({
  children,
  initialError = null,
}: {
  children: ReactNode;
  initialError?: string | null;
}) {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);

  const [elasticsearchUrl, setElasticsearchUrl] = useState(
    "http://elasticsearch:9200",
  );
  const [redisUrl, setRedisUrl] = useState("redis://redis:6379/0");
  const [qdrantHostInput, setQdrantHostInput] = useState("");
  const [validating, setValidating] = useState(false);
  const [esValidation, setEsValidation] = useState<FieldValidation | null>(
    null,
  );
  const [redisValidation, setRedisValidation] =
    useState<FieldValidation | null>(null);
  const [qdrantValidation, setQdrantValidation] =
    useState<FieldValidation | null>(null);

  const { data: qdrantHostStatus } = useQuery({
    queryKey: ["qdrantHostStatus"],
    queryFn: setupApi.getQdrantHost,
  });

  const { data: setupDefaults } = useQuery({
    queryKey: ["setupDefaults"],
    queryFn: setupApi.getDefaults,
  });

  const { data: modelHosts } = useQuery({
    queryKey: ["modelHosts"],
    queryFn: api.listModelHosts,
  });
  const ollamaAvailable = (modelHosts ?? []).some(
    (h) => h.host_type === "ollama",
  );
  const vllmAvailable = (modelHosts ?? []).some((h) => h.host_type === "vllm");

  const qdrantFromEnv = qdrantHostStatus?.from_env ?? false;

  const [prevQdrantHostStatus, setPrevQdrantHostStatus] =
    useState(qdrantHostStatus);
  if (qdrantHostStatus !== prevQdrantHostStatus) {
    setPrevQdrantHostStatus(qdrantHostStatus);
    if (
      qdrantHostStatus &&
      !qdrantHostStatus.from_env &&
      qdrantHostStatus.value
    ) {
      setQdrantHostInput(qdrantHostStatus.value);
    }
  }

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

  const [oidcEnabled, setOidcEnabled] = useState(false);
  const [oidcIssuerUrl, setOidcIssuerUrl] = useState("");
  const [oidcClientId, setOidcClientId] = useState("");
  const [oidcClientSecret, setOidcClientSecret] = useState("");
  const [oidcScopes, setOidcScopes] = useState("openid profile email");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(initialError);

  const handleValidate = async () => {
    setValidating(true);
    setEsValidation(null);
    setRedisValidation(null);
    setQdrantValidation(null);
    setError(null);

    try {
      const result = await setupApi.validate({
        elasticsearch_url: elasticsearchUrl,
        redis_url: redisUrl,
        qdrant_host:
          (qdrantFromEnv ? qdrantHostStatus?.value : qdrantHostInput) ||
          undefined,
      });
      if (result.elasticsearch) setEsValidation(result.elasticsearch);
      if (result.redis) setRedisValidation(result.redis);
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
        qdrant_host: qdrantFromEnv ? undefined : qdrantHostInput || undefined,
        embedding_provider: embeddingStep.provider,
        embedding_model: embeddingStep.model,
        embedding_model_host_id: embeddingStep.hostKeyIds.model_host_id,
        embedding_api_key_id: embeddingStep.hostKeyIds.api_key_id,
        reranker_provider: rerankerStep.provider,
        reranker_model: rerankerStep.model,
        reranker_model_host_id: rerankerStep.hostKeyIds.model_host_id,
        reranker_api_key_id: rerankerStep.hostKeyIds.api_key_id,
        llm_provider: llmStep.provider,
        llm_model: llmStep.model,
        llm_model_host_id: llmStep.hostKeyIds.model_host_id,
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

  const value: SetupWizardContextValue = {
    step,
    setStep,
    error,
    submitting,

    elasticsearchUrl,
    setElasticsearchUrl: (v) => {
      setElasticsearchUrl(v);
      setEsValidation(null);
    },
    esValidation,
    redisUrl,
    setRedisUrl: (v) => {
      setRedisUrl(v);
      setRedisValidation(null);
    },
    redisValidation,
    qdrantHostInput,
    setQdrantHostInput: (v) => {
      setQdrantHostInput(v);
      setQdrantValidation(null);
    },
    qdrantValidation,
    qdrantFromEnv,
    qdrantHostStatusValue: qdrantHostStatus?.value,
    validating,
    handleValidate,

    ollamaAvailable,
    vllmAvailable,

    modelStepState,
    modelStepHint,

    oidcEnabled,
    setOidcEnabled,
    oidcIssuerUrl,
    setOidcIssuerUrl,
    oidcClientId,
    setOidcClientId,
    oidcClientSecret,
    setOidcClientSecret,
    oidcScopes,
    setOidcScopes,

    handleComplete,
    handleOidcSave,
  };

  return (
    <SetupWizardContext.Provider value={value}>
      {children}
    </SetupWizardContext.Provider>
  );
}

export function useSetupWizard(): SetupWizardContextValue {
  const ctx = useContext(SetupWizardContext);
  if (!ctx) {
    throw new Error("useSetupWizard must be used within SetupWizardProvider");
  }
  return ctx;
}

export type { ModelStepProvider };
