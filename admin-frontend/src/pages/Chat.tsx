import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
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
  const { conversationId } = useChat();

  const prevConversationIdRef = useRef<string | null>(null);

  const { data: conversationData } = useQuery({
    queryKey: ["conversation", conversationIdParam],
    queryFn: () => api.getConversation(conversationIdParam!),
    enabled: !!conversationIdParam,
  });

  useEffect(() => {
    if (conversationData) {
      setMessages(
        conversationData.messages as Parameters<typeof setMessages>[0],
      );
    }
  }, [conversationData, setMessages]);

  useEffect(() => {
    if (conversationId && conversationId !== prevConversationIdRef.current) {
      prevConversationIdRef.current = conversationId;
      queryClient.invalidateQueries({ queryKey: ["conversations"] });

      if (!conversationIdParam) {
        navigate(`/c/${conversationId}`);
      }
    }
  }, [conversationId, conversationIdParam, navigate, queryClient]);

  return <ChatPane />;
}
