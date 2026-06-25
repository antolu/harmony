import { useState } from "react";
import { ThumbsUp, ThumbsDown, Copy, Check, Globe } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/shared/components/ui/popover";
import { api } from "@/shared/api/client";
import { SourceCard } from "./SourceCard";
import type { SourceItem } from "@/shared/hooks/useChat";

interface Props {
  conversationId?: string | null;
  messageId: number;
  content: string;
  sources?: SourceItem[];
  feedbackEnabled?: boolean;
}

function SourceFavicon({ url }: { url: string }) {
  const [imgError, setImgError] = useState(false);
  let hostname: string;
  try {
    hostname = new URL(url).hostname;
  } catch {
    hostname = url;
  }

  if (imgError) {
    return <Globe className="h-3.5 w-3.5 text-muted-foreground shrink-0" />;
  }

  return (
    <img
      src={`https://${hostname}/favicon.ico`}
      width={14}
      height={14}
      alt=""
      className="shrink-0 rounded-sm"
      onError={() => setImgError(true)}
    />
  );
}

export function MessageActions({
  conversationId,
  messageId,
  content,
  sources,
  feedbackEnabled = true,
}: Props) {
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [copied, setCopied] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);

  const handleThumbsUp = async () => {
    if (!conversationId) return;
    if (rating === "up") {
      try {
        await api.deleteFeedback(conversationId, messageId);
        setRating(null);
      } catch {
        // keep existing rating
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
        // do not update rating
      }
    }
  };

  const handleThumbsDown = async () => {
    if (!conversationId) return;
    if (rating === "down") {
      try {
        await api.deleteFeedback(conversationId, messageId);
        setRating(null);
      } catch {
        // keep existing rating
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
        // do not update rating
      }
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const hasSources = sources && sources.length > 0;
  const previewSources = hasSources ? sources.slice(0, 4) : [];

  return (
    <div className="flex items-center gap-1 text-muted-foreground">
      {hasSources && (
        <Popover open={sourcesOpen} onOpenChange={setSourcesOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs hover:bg-muted transition-colors"
            >
              <span className="flex items-center -space-x-1">
                {previewSources.map((s, i) => (
                  <span
                    key={i}
                    className="inline-flex rounded-full bg-background border border-border p-0.5"
                  >
                    <SourceFavicon url={s.url} />
                  </span>
                ))}
              </span>
              <span className="ml-1 text-xs">
                {sources.length} source{sources.length !== 1 ? "s" : ""}
              </span>
            </button>
          </PopoverTrigger>
          <PopoverContent
            className="w-auto max-w-lg max-h-80 overflow-y-auto p-2"
            align="start"
          >
            <div className="flex flex-wrap gap-2">
              {sources.map((source, index) => (
                <SourceCard key={index} source={source} index={index} />
              ))}
            </div>
          </PopoverContent>
        </Popover>
      )}

      <div className="flex items-center gap-0.5 ml-auto">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Copy response"
          className="h-7 w-7 text-muted-foreground"
          onClick={handleCopy}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </Button>
        {feedbackEnabled && conversationId && (
          <>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Thumbs up"
              className={
                rating === "up"
                  ? "h-7 w-7 text-green-500"
                  : "h-7 w-7 text-muted-foreground"
              }
              onClick={handleThumbsUp}
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Thumbs down"
              className={
                rating === "down"
                  ? "h-7 w-7 text-red-500"
                  : "h-7 w-7 text-muted-foreground"
              }
              onClick={handleThumbsDown}
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
