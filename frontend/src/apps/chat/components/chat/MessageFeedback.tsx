import { useState } from "react";
import { ThumbsUp, ThumbsDown, Copy, Check } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { api } from "@/shared/api/client";

interface Props {
  conversationId: string;
  messageId: number;
  content: string;
  feedbackEnabled: boolean;
}

export function MessageFeedback({
  conversationId,
  messageId,
  content,
  feedbackEnabled,
}: Props) {
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [copied, setCopied] = useState(false);

  if (!feedbackEnabled) return null;

  const handleThumbsUp = async () => {
    if (rating === "up") {
      try {
        await api.deleteFeedback(conversationId, messageId);
        setRating(null);
      } catch {
        // keep existing rating on failure
      }
    } else {
      try {
        await api.postFeedback({
          conversation_id: conversationId,
          message_id: messageId,
          rating: "up",
        });
        setRating("up");
      } catch {
        // do not update rating on failure
      }
    }
  };

  const handleThumbsDown = async () => {
    if (rating === "down") {
      try {
        await api.deleteFeedback(conversationId, messageId);
        setRating(null);
      } catch {
        // keep existing rating on failure
      }
    } else {
      try {
        await api.postFeedback({
          conversation_id: conversationId,
          message_id: messageId,
          rating: "down",
        });
        setRating("down");
      } catch {
        // do not update rating on failure
      }
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex items-center gap-1 h-8 opacity-0 group-hover:opacity-100 transition-opacity">
      <Button
        variant="ghost"
        size="icon"
        aria-label="Thumbs up"
        className={
          rating === "up"
            ? "text-green-500 fill-current min-h-[44px] min-w-[44px]"
            : "text-muted-foreground min-h-[44px] min-w-[44px]"
        }
        onClick={handleThumbsUp}
      >
        <ThumbsUp className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Thumbs down"
        className={
          rating === "down"
            ? "text-red-500 fill-current min-h-[44px] min-w-[44px]"
            : "text-muted-foreground min-h-[44px] min-w-[44px]"
        }
        onClick={handleThumbsDown}
      >
        <ThumbsDown className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Copy response"
        className="text-muted-foreground min-h-[44px] min-w-[44px]"
        onClick={handleCopy}
      >
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </Button>
    </div>
  );
}
