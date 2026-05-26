import { useState, useRef } from "react";
import { Send, Loader2 } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { useConversationStore } from "@/stores/chatStore";
import { ModeSelector } from "./ModeSelector";
import { ModelSelector } from "./ModelSelector";
import { DataConnectorsButton } from "./DataConnectorsButton";

type Mode = "search" | "deep_research" | "chat";

interface ChatInputProps {
  onSend: (
    query: string,
    endpoint: "/ai-search" | "/agentic-search",
    model: string | null,
  ) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<Mode>("search");
  const { currentModel, setCurrentModel } = useConversationStore();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    if (text.trim().length === 0 || disabled) return;
    const endpoint: "/ai-search" | "/agentic-search" =
      mode === "deep_research" ? "/agentic-search" : "/ai-search";
    onSend(text.trim(), endpoint, currentModel || null);
    setText("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="sticky bottom-0 bg-background border-t border-border">
      <div className="max-w-3xl mx-auto px-4 pb-4 pt-2">
        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            className="min-h-[44px] max-h-[160px] resize-none overflow-y-auto pr-12 py-3"
            disabled={disabled}
          />
          <Button
            size="icon"
            aria-label="Send message"
            className="absolute right-2 bottom-2 min-h-[44px] min-w-[44px]"
            disabled={text.trim().length === 0 || disabled}
            onClick={handleSend}
          >
            {disabled ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
        <div className="flex items-center gap-2 mt-1.5">
          <ModeSelector value={mode} onChange={setMode} />
          <ModelSelector
            value={currentModel}
            onChange={(m) => setCurrentModel(m)}
          />
          <DataConnectorsButton />
        </div>
      </div>
    </div>
  );
}
