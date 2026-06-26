import { useState, useRef } from "react";
import { Send, Loader2 } from "lucide-react";
import { Textarea } from "@/shared/components/ui/textarea";
import { Button } from "@/shared/components/ui/button";
import { useConversationStore } from "@/shared/stores/chatStore";
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
    <div className="bg-gradient-to-t from-background via-background to-transparent shrink-0">
      <div className="max-w-3xl mx-auto px-4 pb-5 pt-2">
        <div className="rounded-2xl border border-border bg-card shadow-lg shadow-black/[0.03] focus-within:border-primary/40 focus-within:shadow-xl transition-all px-2 pt-1">
          <Textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Ask anything…"
            className="min-h-[44px] max-h-[200px] resize-none overflow-y-auto border-0 bg-transparent px-2 pt-2.5 pb-1 text-base placeholder:text-base shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
            disabled={disabled}
          />
          <div className="flex items-center gap-1 pb-1.5">
            <ModeSelector value={mode} onChange={setMode} />
            <ModelSelector
              value={currentModel}
              onChange={(m) => setCurrentModel(m)}
            />
            <DataConnectorsButton />
            <div className="flex-1" />
            <Button
              size="icon"
              aria-label="Send message"
              className="h-9 w-9 rounded-xl shrink-0"
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
        </div>
      </div>
    </div>
  );
}
