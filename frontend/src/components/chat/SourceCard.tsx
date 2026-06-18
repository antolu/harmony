import { useState } from "react";
import { Globe } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Source {
  title: string;
  url: string;
  snippet: string;
}

interface Props {
  source: Source;
  index: number;
}

function getSafeHostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

export function SourceCard({ source, index }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [imgError, setImgError] = useState(false);

  const hostname = getSafeHostname(source.url);

  return (
    <Card
      role="article"
      aria-label={source.title}
      className={`cursor-pointer border border-border transition-all duration-150 p-3 ${expanded ? "w-72" : "w-48"}`}
      onClick={() => setExpanded((v) => !v)}
    >
      <div className="flex items-center gap-2 min-w-0">
        {!imgError ? (
          <img
            src={`https://${hostname}/favicon.ico`}
            width={16}
            height={16}
            alt=""
            onError={() => setImgError(true)}
          />
        ) : (
          <Globe className="h-4 w-4 text-muted-foreground shrink-0" />
        )}
        <span className="text-sm font-semibold truncate max-w-[200px]">
          {source.title}
        </span>
        <span className="text-xs bg-muted rounded px-1 shrink-0">
          [{index + 1}]
        </span>
      </div>
      <div className="text-xs text-muted-foreground mt-1">{hostname}</div>
      {expanded && (
        <div className="mt-2">
          <p className="text-sm text-muted-foreground leading-relaxed">
            {source.snippet.length > 300
              ? source.snippet.slice(0, 300)
              : source.snippet}
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-2"
            aria-label={`Open ${source.title}`}
            onClick={(e) => {
              e.stopPropagation();
              window.open(source.url, "_blank", "noopener,noreferrer");
            }}
          >
            Open source
          </Button>
        </div>
      )}
    </Card>
  );
}
