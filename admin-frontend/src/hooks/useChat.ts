import { useState, useRef, useEffect } from "react";
import { createSSEPostConnection } from "@/api/client";

export interface StepEntry {
  id: string;
  type: "search" | "reading" | "refining" | "tool_call";
  text: string;
  completed: boolean;
}

export interface SourceItem {
  title: string;
  url: string;
  snippet: string;
}

const MAX_RETRIES = 3;
const RETRY_DELAYS = [1000, 2000, 4000];

const SSE_EVENT_TYPES = [
  "query_variant",
  "reading_page",
  "refinement_round",
  "tool_call",
  "answer_chunk",
  "done",
  "error",
];

export function useChat() {
  const [content, setContent] = useState("");
  const [steps, setSteps] = useState<StepEntry[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const cleanupRef = useRef<(() => void) | null>(null);
  const seenUrlsRef = useRef<Set<string>>(new Set());
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
    seenUrlsRef.current = new Set();

    const onMessage = (event: string, data: unknown) => {
      const d = data as Record<string, unknown>;

      switch (event) {
        case "query_variant":
          setSteps((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              type: "search",
              text: `Searching: ${d.variant ?? ""}`,
              completed: false,
            },
          ]);
          break;

        case "reading_page": {
          const url = String(d.url ?? "");
          if (!seenUrlsRef.current.has(url)) {
            seenUrlsRef.current.add(url);
            setSteps((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                type: "reading",
                text: `Reading: ${d.title ?? url}`,
                completed: false,
              },
            ]);
          }
          break;
        }

        case "refinement_round":
          setSteps((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              type: "refining",
              text: `Refining answer (round ${d.round ?? ""})`,
              completed: false,
            },
          ]);
          break;

        case "tool_call":
          setSteps((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              type: "tool_call",
              text: `Using: ${d.function ?? ""}`,
              completed: false,
            },
          ]);
          break;

        case "answer_chunk":
          setContent((prev) => prev + String(d.content ?? ""));
          break;

        case "done":
          setSources((d.sources as SourceItem[]) ?? []);
          setConversationId((d.conversation_id as string) ?? null);
          setIsStreaming(false);
          setSteps((prev) => prev.map((s) => ({ ...s, completed: true })));
          break;

        case "error":
          setError((d.message as string) ?? "Unknown error");
          setIsStreaming(false);
          break;
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
  };
}
