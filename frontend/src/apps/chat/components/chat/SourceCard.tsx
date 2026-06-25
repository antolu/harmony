import { useState } from "react";
import { Globe } from "lucide-react";
import { Card } from "@/shared/components/ui/card";

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

function hasRealTitle(title: string): boolean {
  return !!title && title !== "Untitled" && title !== "undefined";
}

export function SourceCard({ source, index }: Props) {
  const [imgError, setImgError] = useState(false);
  const hostname = getSafeHostname(source.url);
  const showTitle = hasRealTitle(source.title);

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block no-underline"
      aria-label={showTitle ? source.title : hostname}
    >
      <Card className="cursor-pointer border border-border hover:border-foreground/20 hover:bg-muted/50 transition-all duration-150 p-3 w-56">
        <div className="flex items-center gap-2 min-w-0">
          {!imgError ? (
            <img
              src={`https://${hostname}/favicon.ico`}
              width={14}
              height={14}
              alt=""
              className="shrink-0 rounded-sm"
              onError={() => setImgError(true)}
            />
          ) : (
            <Globe className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          )}
          <span className="text-xs text-muted-foreground truncate flex-1">
            {hostname}
          </span>
          <span className="text-[0.65rem] bg-muted rounded px-1 shrink-0 text-muted-foreground">
            {index + 1}
          </span>
        </div>
        {showTitle ? (
          <div className="mt-1.5 text-sm font-medium leading-snug line-clamp-2 text-foreground">
            {source.title}
          </div>
        ) : source.snippet ? (
          <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed line-clamp-3">
            {source.snippet}
          </p>
        ) : null}
        {showTitle && source.snippet && (
          <p className="mt-1 text-xs text-muted-foreground leading-relaxed line-clamp-2">
            {source.snippet}
          </p>
        )}
      </Card>
    </a>
  );
}
