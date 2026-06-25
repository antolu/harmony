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
import type { StepEntry, SourceItem } from "@/shared/hooks/useChat";

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
}

const TOOL_NAME_LABELS: Record<string, string> = {
  search_documents: "Searching documents",
  get_document_details: "Reading a source",
};

function reconstructMessages(messages: PersistedMessage[]): ChatMessage[] {
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
          const parsed = JSON.parse(m.content) as { results?: SourceItem[] };
          if (parsed.results) {
            pendingSources.push(...parsed.results);
          }
        } catch {
          // not JSON-shaped tool response, skip
        }
      }
      continue;
    }

    if ((m.role === "user" || m.role === "assistant") && m.content) {
      result.push({
        id: m.id ?? Date.now() + result.length,
        role: m.role as "user" | "assistant",
        content: m.content,
        sources: pendingSources?.length ? pendingSources : undefined,
        steps: pendingSteps?.length ? pendingSteps : undefined,
      });
      pendingSteps = undefined;
      pendingSources = undefined;
    }
  }

  return result;
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
    if (conversationData) {
      const reconstructed = reconstructMessages(
        conversationData.messages as PersistedMessage[],
      );
      setMessages(reconstructed);
    }
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
