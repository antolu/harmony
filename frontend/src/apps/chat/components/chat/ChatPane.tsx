import { useState, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Menu } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { useChatStore } from "@/shared/stores/chatStore";
import { useConversationStore } from "@/shared/stores/chatStore";
import { useChat } from "@/shared/hooks/useChat";
import { useChatLayoutContext } from "@/apps/chat/components/layout/ChatLayout";
import { processCitations } from "@/shared/lib/citations";

export function ChatPane() {
  const { onMobileMenuOpen } = useChatLayoutContext();
  const { messages, addMessage } = useChatStore();
  const { currentConversationId, setCurrentConversation } =
    useConversationStore();
  const queryClient = useQueryClient();
  const {
    content,
    steps,
    sources,
    isStreaming,
    error,
    startStreaming,
    stopStreaming,
  } = useChat(
    (id) => {
      setCurrentConversation(id);
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    () => {
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  );

  const prevIsStreamingRef = useRef(false);

  useEffect(() => {
    if (
      prevIsStreamingRef.current &&
      !isStreaming &&
      (content || steps.length > 0)
    ) {
      let finalContent = content;
      let finalSources = sources;

      if (sources.length > 0 && content) {
        const res = processCitations(content, sources);
        finalContent = res.processedContent;
        finalSources = res.usedSources;
      }

      addMessage({
        id: Date.now(),
        role: "assistant",
        content: finalContent,
        sources: finalSources.length > 0 ? finalSources : undefined,
        steps: steps.length > 0 ? steps : undefined,
      });
    }
    prevIsStreamingRef.current = isStreaming;
  }, [isStreaming, content, sources, steps, addMessage]);

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
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border shrink-0">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open navigation"
          className="md:hidden h-8 w-8 shrink-0"
          onClick={onMobileMenuOpen}
        >
          <Menu className="h-5 w-5" />
        </Button>
        <span className="font-semibold text-base">Harmony</span>
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
        conversationId={currentConversationId}
      />
      <ChatInput onSend={handleSend} disabled={isStreaming} />
    </div>
  );
}
