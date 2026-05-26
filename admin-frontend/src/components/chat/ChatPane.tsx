import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MessageList } from "./MessageList";
import { useChatStore } from "@/stores/chatStore";
import { useChat } from "@/hooks/useChat";

export function ChatPane() {
  const { toggleSidebar, messages } = useChatStore();
  const { content, steps, isStreaming } = useChat();

  return (
    <div className="flex flex-col h-full">
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
      <div className="flex-1 overflow-hidden max-w-3xl mx-auto w-full px-4">
        <MessageList
          messages={messages}
          streamingContent={content}
          streamingSteps={steps}
          isStreaming={isStreaming}
        />
      </div>
      <div className="max-w-3xl mx-auto w-full px-4 py-4">
        <div className="text-muted-foreground text-sm text-center">
          Input placeholder — see plan 04-09
        </div>
      </div>
    </div>
  );
}
