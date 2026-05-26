import { useState, useEffect } from "react";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { useChatStore } from "@/stores/chatStore";
import { useConversationStore } from "@/stores/chatStore";
import { useChat } from "@/hooks/useChat";

export function ChatPane() {
  const { toggleSidebar, messages, addMessage } = useChatStore();
  const { currentConversationId, setCurrentConversation } =
    useConversationStore();
  const {
    content,
    steps,
    isStreaming,
    error,
    startStreaming,
    stopStreaming,
    conversationId,
  } = useChat();

  useEffect(() => {
    if (conversationId) {
      setCurrentConversation(conversationId);
    }
  }, [conversationId, setCurrentConversation]);

  const [lastPayload, setLastPayload] = useState<{
    endpoint: "/ai-search" | "/agentic-search";
    payload: { query: string; conversation_id?: string; model?: string };
  } | null>(null);

  function handleSend(
    query: string,
    endpoint: "/ai-search" | "/agentic-search",
    model: string | null,
  ) {
    const payload: { query: string; conversation_id?: string; model?: string } =
      { query };
    if (currentConversationId) payload.conversation_id = currentConversationId;
    if (model) payload.model = model;

    addMessage({ id: Date.now(), role: "user", content: query });
    setLastPayload({ endpoint, payload });
    startStreaming(endpoint, payload);
  }

  function handleRetry() {
    if (!lastPayload) return;
    stopStreaming();
    startStreaming(lastPayload.endpoint, lastPayload.payload);
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="md:hidden flex items-center p-3 border-b border-border">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open sidebar"
          onClick={toggleSidebar}
        >
          <Menu className="h-5 w-5" />
        </Button>
      </div>
      {error && (
        <div className="max-w-3xl mx-auto w-full px-4 pt-2">
          <div className="text-destructive bg-destructive/10 rounded p-2 flex items-center justify-between gap-2 text-sm">
            <span>{error}</span>
            <div className="flex gap-2">
              {error === "Connection lost. Click to retry." && (
                <Button size="sm" variant="ghost" onClick={handleRetry}>
                  Retry
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => stopStreaming()}>
                Try again
              </Button>
            </div>
          </div>
        </div>
      )}
      <MessageList
        messages={messages}
        streamingContent={isStreaming ? content : undefined}
        streamingSteps={isStreaming ? steps : undefined}
        isStreaming={isStreaming}
      />
      <ChatInput onSend={handleSend} disabled={isStreaming} />
    </div>
  );
}
