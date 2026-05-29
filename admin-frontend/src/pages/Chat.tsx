import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { ChatPane } from "@/components/chat/ChatPane";
import { useChatStore, useConversationStore } from "@/stores/chatStore";
import { api } from "@/api/client";

export function Chat() {
  const { conversationId: conversationIdParam } = useParams<{
    conversationId?: string;
  }>();
  const { setMessages } = useChatStore();
  const { setCurrentConversation } = useConversationStore();

  const { data: conversationData } = useQuery({
    queryKey: ["conversation", conversationIdParam],
    queryFn: () => api.getConversation(conversationIdParam!),
    enabled: !!conversationIdParam,
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
      const displayable = (
        conversationData.messages as Array<{
          role: string;
          content: string | null;
          id?: number;
        }>
      ).filter(
        (m) =>
          (m.role === "user" || m.role === "assistant") &&
          m.content != null &&
          m.content !== "",
      ) as Parameters<typeof setMessages>[0];
      setMessages(displayable);
    }
  }, [conversationData, setMessages]);

  return <ChatPane key={conversationIdParam ?? "new"} />;
}
