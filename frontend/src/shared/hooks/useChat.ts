import { useState, useRef, useEffect } from "react";
import { createSSEPostConnection } from "@/shared/api/client";
import { useConversationStore } from "@/shared/stores/chatStore";

export interface StepEntry {
  id: string;
  kind: "search" | "thinking" | "tool_call";
  text: string;
  stepId?: string;
  status?: "running" | "done";
  sources?: SourceItem[];
}

export interface SourceItem {
  title: string;
  url: string;
  snippet: string;
}

const MAX_RETRIES = 3;
const RETRY_DELAYS = [1000, 2000, 4000];

const SSE_EVENT_TYPES = ["status", "answer_chunk", "done", "error", "title"];

export function useChat(
  onConversationCreated?: (id: string) => void,
  onTitleGenerated?: (id: string, title: string) => void,
) {
  const updateConversationTitle = useConversationStore(
    (s) => s.updateConversationTitle,
  );
  const [content, setContent] = useState("");
  const [steps, setSteps] = useState<StepEntry[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const cleanupRef = useRef<(() => void) | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      cleanupRef.current?.();
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
    };
  }, []);

  function startStreaming(
    endpoint: "/ai-search" | "/agentic-search",
    payload: { query: string; conversation_id?: string; model?: string },
  ): void {
    cleanupRef.current?.();

    setContent("");
    setSteps([]);
    setError(null);
    setSources([]);
    setIsStreaming(true);
    setRetryCount(0);

    const onMessage = (event: string, data: unknown) => {
      const d = data as Record<string, unknown>;

      switch (event) {
        case "status": {
          const kind = d.kind as StepEntry["kind"];
          const stepId = d.step_id as string | undefined;
          const status = d.status as StepEntry["status"];

          setSteps((prev) => {
            const existingIndex =
              stepId !== undefined
                ? prev.findIndex((s) => s.stepId === stepId)
                : -1;

            const entry: StepEntry = {
              id:
                existingIndex >= 0
                  ? prev[existingIndex].id
                  : crypto.randomUUID(),
              kind,
              stepId,
              status,
              text: String(d.message ?? ""),
              sources:
                kind === "search" ? (d.sources as SourceItem[]) : undefined,
            };

            if (existingIndex >= 0) {
              const next = [...prev];
              next[existingIndex] = entry;
              return next;
            }
            return [...prev, entry];
          });
          break;
        }

        case "answer_chunk":
          setContent((prev) => prev + String(d.content ?? ""));
          break;

        case "done": {
          setSources((d.sources as SourceItem[]) ?? []);
          const newConvId = (d.conversation_id as string) ?? null;
          setConversationId(newConvId);
          setIsStreaming(false);
          if (newConvId) onConversationCreated?.(newConvId);
          break;
        }

        case "error":
          setError((d.message as string) ?? "Unknown error");
          setIsStreaming(false);
          break;

        case "title": {
          const titleConvId = d.conversation_id as string;
          const title = d.title as string;
          if (titleConvId && title) {
            updateConversationTitle(titleConvId, title);
            onTitleGenerated?.(titleConvId, title);
          }
          break;
        }
      }
    };

    const onError = (err: Error) => {
      void err;
      setRetryCount((prev) => {
        if (prev < MAX_RETRIES) {
          const delay = RETRY_DELAYS[prev];
          if (isMountedRef.current) {
            retryTimerRef.current = setTimeout(() => {
              if (isMountedRef.current) startStreaming(endpoint, payload);
            }, delay);
          }
          return prev + 1;
        } else {
          setError("Connection lost. Click to retry.");
          setIsStreaming(false);
          return prev;
        }
      });
    };

    const cleanup = createSSEPostConnection(
      endpoint,
      payload as Record<string, unknown>,
      SSE_EVENT_TYPES,
      onMessage,
      onError,
    );

    cleanupRef.current = cleanup;
  }

  function stopStreaming(): void {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setIsStreaming(false);
  }

  function reset(): void {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setContent("");
    setSteps([]);
    setError(null);
    setSources([]);
    setIsStreaming(false);
    setConversationId(null);
    setRetryCount(0);
  }

  return {
    content,
    steps,
    isStreaming,
    error,
    sources,
    conversationId,
    retryCount,
    maxRetries: MAX_RETRIES,
    startStreaming,
    stopStreaming,
    reset,
  };
}
