import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { ChatPane } from "@/components/chat/ChatPane";
import { useChatStore } from "@/stores/chatStore";
import { useChat } from "@/hooks/useChat";
import { api } from "@/api/client";

export function Chat() {
  const { conversationId: conversationIdParam } = useParams<{
    conversationId?: string;
  }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { setMessages } = useChatStore();
  const { error, startStreaming, isStreaming, conversationId } = useChat();

  const lastPayloadRef = useRef<{
    query: string;
    conversation_id?: string;
    model?: string;
  } | null>(null);
  const prevConversationIdRef = useRef<string | null>(null);

  useQuery({
    queryKey: ["conversation", conversationIdParam],
    queryFn: () => api.getConversation(conversationIdParam!),
    enabled: !!conversationIdParam,
    onSuccess: (data: {
      id: string;
      messages: Array<{
        id: number;
        role: "user" | "assistant";
        content: string;
        sources?: Array<{ title: string; url: string; snippet: string }>;
      }>;
    }) => {
      setMessages(data.messages);
    },
  } as Parameters<typeof useQuery>[0]);

  useEffect(() => {
    if (conversationId && conversationId !== prevConversationIdRef.current) {
      prevConversationIdRef.current = conversationId;
      queryClient.invalidateQueries({ queryKey: ["conversations"] });

      if (!conversationIdParam) {
        navigate(`/c/${conversationId}`);
      }
    }
  }, [conversationId, conversationIdParam, navigate, queryClient]);

  const hasMessages = !!conversationIdParam;

  return (
    <div className="flex flex-col h-full">
      {!hasMessages && !isStreaming && (
        <div className="flex flex-col items-center justify-center py-16 flex-1 px-4">
          <div className="w-full max-w-3xl mx-auto">
            <h1 className="text-xl font-semibold">
              What do you want to search?
            </h1>
            <p className="text-base text-muted-foreground mt-2">
              Ask anything about your organization&apos;s documents. Harmony
              searches your data and shows you sources.
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              Your conversations will appear in the sidebar.
            </p>
          </div>
        </div>
      )}
      {error === "Connection lost. Click to retry." &&
        lastPayloadRef.current && (
          <div className="flex justify-center py-2">
            <Button
              variant="outline"
              onClick={() => {
                if (lastPayloadRef.current) {
                  startStreaming("/ai-search", lastPayloadRef.current);
                }
              }}
            >
              Retry
            </Button>
          </div>
        )}
      <div className="flex-1 overflow-hidden">
        <ChatPane />
      </div>
    </div>
  );
}
