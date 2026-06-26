import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { ChatPane } from "@/apps/chat/components/chat/ChatPane";
import {
  useChatStore,
  useConversationStore,
  type ChatMessage,
} from "@/shared/stores/chatStore";
import { api } from "@/shared/api/client";
import type { HydratedSource } from "@/shared/api/client";
import type { StepEntry, SourceItem } from "@/shared/hooks/useChat";
import { processCitations } from "@/shared/lib/citations";

interface ToolCallDict {
  id: string;
  type: string;
  function: { name: string; arguments: string };
}

interface PersistedMessage {
  role: string;
  content: string | null;
  tool_calls?: ToolCallDict[];
  tool_call_id?: string;
  name?: string;
  id?: number;
  trace_id?: string;
}

const TOOL_NAME_LABELS: Record<string, string> = {
  search_documents: "Searching documents",
  get_document_details: "Reading a source",
};

const SOURCE_SNIPPET_CHARS = 300;

interface RawToolSource {
  title?: string;
  url?: string;
  snippet?: string;
  content?: string;
}

function toSourceItem(raw: RawToolSource): SourceItem {
  return {
    title: raw.title ?? "",
    url: raw.url ?? "",
    snippet: (raw.content ?? raw.snippet ?? "").slice(0, SOURCE_SNIPPET_CHARS),
  };
}

function reconstructMessages(
  messages: PersistedMessage[],
  traces?: { id: string; events: Record<string, unknown>[] }[],
): ChatMessage[] {
  const result: ChatMessage[] = [];
  let pendingSteps: StepEntry[] | undefined;
  let pendingSources: SourceItem[] | undefined;
  let stepId = 0;

  for (const m of messages) {
    if (m.role === "assistant" && m.content == null && m.tool_calls) {
      pendingSteps ??= [];
      pendingSources ??= [];
      for (const toolCall of m.tool_calls) {
        pendingSteps.push({
          id: `reconstructed-${stepId++}`,
          kind: "tool_call",
          text: TOOL_NAME_LABELS[toolCall.function.name] ?? "Using a tool",
        });
      }
      continue;
    }

    if (m.role === "tool") {
      if (pendingSources && m.content) {
        try {
          const parsed = JSON.parse(m.content) as { results?: RawToolSource[] };
          if (parsed.results) {
            pendingSources.push(...parsed.results.map(toSourceItem));
          }
        } catch {
          // not JSON-shaped tool response, skip
        }
      }
      continue;
    }

    if ((m.role === "user" || m.role === "assistant") && m.content) {
      let finalSteps = pendingSteps?.length ? pendingSteps : undefined;
      let finalSources = pendingSources?.length ? pendingSources : undefined;

      if (m.role === "assistant" && m.trace_id && traces) {
        const trace = traces.find((t) => t.id === m.trace_id);
        if (trace) {
          finalSteps ??= [];
          finalSources ??= [];

          let hasDoneEvent = false;
          for (const event of trace.events) {
            if (event.kind === "done") hasDoneEvent = true;
          }

          for (const event of trace.events) {
            if (event.kind === "done" && Array.isArray(event.sources)) {
              finalSources = [...(event.sources as SourceItem[])];
            } else if (event.kind === "search") {
              if (!hasDoneEvent && Array.isArray(event.sources)) {
                finalSources.push(...(event.sources as SourceItem[]));
              }
              finalSteps.push({
                id: `reconstructed-${stepId++}`,
                kind: "search",
                text:
                  typeof event.message === "string"
                    ? event.message
                    : "Searching the web",
                sources: Array.isArray(event.sources)
                  ? (event.sources as SourceItem[])
                  : undefined,
              });
            } else if (event.kind === "refining") {
              finalSteps.push({
                id: `reconstructed-${stepId++}`,
                kind: "refining",
                text:
                  typeof event.message === "string"
                    ? event.message
                    : typeof event.status === "string"
                      ? event.status
                      : "Refining answer...",
              });
            }
          }
        }
      }

      let finalContent = m.content;
      if (finalSources && finalSources.length > 0 && finalContent) {
        const res = processCitations(finalContent, finalSources);
        finalContent = res.processedContent;
        finalSources = res.usedSources.length > 0 ? res.usedSources : undefined;
      }

      result.push({
        id: m.id ?? Date.now() + result.length,
        role: m.role as "user" | "assistant",
        content: finalContent,
        sources: finalSources?.length ? finalSources : undefined,
        steps: finalSteps?.length ? finalSteps : undefined,
      });
      pendingSteps = undefined;
      pendingSources = undefined;
    }
  }

  return result;
}

function collectSourceUrls(messages: ChatMessage[]): string[] {
  const urls = new Set<string>();
  for (const m of messages) {
    for (const s of m.sources ?? []) if (s.url) urls.add(s.url);
    for (const step of m.steps ?? [])
      for (const s of step.sources ?? []) if (s.url) urls.add(s.url);
  }
  return [...urls];
}

function mergeSource(s: SourceItem, h: HydratedSource | undefined): SourceItem {
  if (!h) return s;
  return {
    ...s,
    title: h.title || s.title,
    snippet: h.snippet || s.snippet,
  };
}

function applyHydration(
  messages: ChatMessage[],
  byUrl: Map<string, HydratedSource>,
): ChatMessage[] {
  return messages.map((m) => ({
    ...m,
    sources: m.sources?.map((s) => mergeSource(s, byUrl.get(s.url))),
    steps: m.steps?.map((step) => ({
      ...step,
      sources: step.sources?.map((s) => mergeSource(s, byUrl.get(s.url))),
    })),
  }));
}

export function Chat() {
  const { conversationId: conversationIdParam } = useParams<{
    conversationId?: string;
  }>();
  const { setMessages } = useChatStore();
  const { setCurrentConversation } = useConversationStore();

  const { data: conversationData, isError: conversationError } = useQuery({
    queryKey: ["conversation", conversationIdParam],
    queryFn: () => api.getConversation(conversationIdParam!),
    enabled: !!conversationIdParam,
    retry: false,
  });

  useEffect(() => {
    if (!conversationIdParam) {
      setMessages([]);
      setCurrentConversation(null);
    } else {
      setCurrentConversation(conversationIdParam);
    }
  }, [conversationIdParam, setMessages, setCurrentConversation]);

  useEffect(() => {
    if (!conversationData) return;
    const reconstructed = reconstructMessages(
      conversationData.messages as PersistedMessage[],
      conversationData.traces,
    );
    setMessages(reconstructed);

    const urls = collectSourceUrls(reconstructed);
    if (urls.length === 0) return;
    let cancelled = false;
    void api
      .hydrateSources(urls)
      .then((res) => {
        if (cancelled) return;
        const byUrl = new Map(res.sources.map((s) => [s.url, s]));
        setMessages(applyHydration(reconstructed, byUrl));
      })
      .catch(() => {
        // hydration is best-effort; stored fallback already rendered
      });
    return () => {
      cancelled = true;
    };
  }, [conversationData, setMessages]);

  if (conversationIdParam && conversationError) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 min-h-[50vh] gap-2">
        <p className="text-sm text-muted-foreground">
          Conversation not found or not accessible.
        </p>
        <a href="/" className="text-sm underline text-primary">
          Start a new chat
        </a>
      </div>
    );
  }

  return <ChatPane key={conversationIdParam ?? "new"} />;
}
