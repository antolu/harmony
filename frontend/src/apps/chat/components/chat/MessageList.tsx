import { useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { StepList } from "./StepList";
import { MessageActions } from "./MessageActions";
import { api } from "@/shared/api/client";
import type { SourceItem, StepEntry } from "@/shared/hooks/useChat";

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources?: SourceItem[];
  steps?: StepEntry[];
}

interface Props {
  messages: Message[];
  streamingContent?: string;
  streamingSteps?: StepEntry[];
  isStreaming?: boolean;
  conversationId?: string | null;
  feedbackEnabled?: boolean;
}

export function MessageList({
  messages,
  streamingContent,
  streamingSteps,
  isStreaming,
  conversationId,
  feedbackEnabled = true,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: user } = useQuery({
    queryKey: ["current-user"],
    queryFn: () => api.getCurrentUser(),
    retry: false,
    staleTime: 60_000,
  });

  const firstName =
    user && user.id !== "anonymous"
      ? (user.display_name || user.email || "").split(/[\s@]/)[0]
      : "";

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streamingContent]);

  return (
    <div
      className="flex-1 overflow-y-auto min-h-0"
      aria-live="polite"
      aria-label="Conversation messages"
    >
      <div className="flex flex-col gap-5 px-4 py-6 max-w-3xl mx-auto">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center flex-1 min-h-[55vh] text-center">
            <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Sparkles className="h-7 w-7" />
            </div>
            <h1 className="font-serif text-4xl font-medium tracking-tight text-foreground">
              {firstName
                ? `What are you looking for, ${firstName}?`
                : "What are you looking for?"}
            </h1>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className="flex flex-col gap-2">
            {msg.role === "assistant" ? (
              <div className="flex flex-col gap-2">
                {msg.steps && msg.steps.length > 0 && (
                  <StepList steps={msg.steps} isStreaming={false} />
                )}
                <MessageBubble
                  content={msg.content}
                  isUser={false}
                  sources={msg.sources}
                />
                <MessageActions
                  conversationId={conversationId}
                  messageId={msg.id}
                  content={msg.content}
                  sources={msg.sources}
                  feedbackEnabled={feedbackEnabled}
                />
              </div>
            ) : (
              <MessageBubble
                content={msg.content}
                isUser={true}
                sources={msg.sources}
              />
            )}
          </div>
        ))}
        {isStreaming && (
          <div className="flex flex-col gap-2">
            <StepList
              steps={streamingSteps ?? []}
              isStreaming={isStreaming ?? false}
            />
            <MessageBubble
              content={streamingContent ?? ""}
              isStreaming={true}
            />
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
