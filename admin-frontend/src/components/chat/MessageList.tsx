import { useRef, useEffect } from "react";
import { MessageBubble } from "./MessageBubble";
import { StepList } from "./StepList";
import { CitationList } from "./CitationList";
import { MessageFeedback } from "./MessageFeedback";
import type { SourceItem, StepEntry } from "@/hooks/useChat";

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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streamingContent]);

  return (
    <div
      className="flex-1 overflow-y-auto"
      aria-live="polite"
      aria-label="Conversation messages"
    >
      <div className="flex flex-col gap-4 p-4 max-w-3xl mx-auto">
        {messages.map((msg) => (
          <div key={msg.id} className="flex flex-col gap-2">
            {msg.role === "assistant" ? (
              <div className="group relative flex flex-col gap-2">
                <MessageBubble
                  content={msg.content}
                  isUser={false}
                  sources={msg.sources}
                />
                {msg.steps && msg.steps.length > 0 && (
                  <StepList steps={msg.steps} isStreaming={false} />
                )}
                <CitationList
                  content={msg.content}
                  sources={msg.sources ?? []}
                />
                {conversationId && (
                  <MessageFeedback
                    conversationId={conversationId}
                    messageId={msg.id}
                    content={msg.content}
                    feedbackEnabled={feedbackEnabled}
                  />
                )}
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
            <MessageBubble
              content={streamingContent ?? ""}
              isStreaming={true}
            />
            {((streamingSteps && streamingSteps.length > 0) || isStreaming) && (
              <StepList
                steps={streamingSteps ?? []}
                isStreaming={isStreaming ?? false}
              />
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
