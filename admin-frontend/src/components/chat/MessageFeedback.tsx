import { useState } from "react";
import { ThumbsUp, ThumbsDown, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/api/client";

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
      await api.deleteFeedback(conversationId, messageId);
      setRating(null);
    } else {
      await api.postFeedback({
        conversation_id: conversationId,
        message_id: messageId,
        rating: "up",
      });
      setRating("up");
    }
  };

  const handleThumbsDown = async () => {
    if (rating === "down") {
      await api.deleteFeedback(conversationId, messageId);
      setRating(null);
    } else {
      await api.postFeedback({
        conversation_id: conversationId,
        message_id: messageId,
        rating: "down",
      });
      setRating("down");
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
            ? "text-green-500 fill-current"
            : "text-muted-foreground"
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
            ? "text-red-500 fill-current"
            : "text-muted-foreground"
        }
        onClick={handleThumbsDown}
      >
        <ThumbsDown className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Copy response"
        className="text-muted-foreground"
        onClick={handleCopy}
      >
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </Button>
    </div>
  );
}
