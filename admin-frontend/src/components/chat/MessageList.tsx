import { useRef, useEffect } from "react";
import { MessageBubble } from "./MessageBubble";
import { StepList } from "./StepList";
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
            <MessageBubble
              content={msg.content}
              isUser={msg.role === "user"}
              sources={msg.sources}
            />
            {msg.role === "assistant" && msg.steps && msg.steps.length > 0 && (
              <StepList steps={msg.steps} isStreaming={false} />
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
