import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { SourceCard } from "./SourceCard";

interface Source {
  title: string;
  url: string;
  snippet: string;
}

interface Props {
  content: string;
  sources: Source[];
}

export function CitationList({ content, sources }: Props) {
  const [open, setOpen] = useState(false);

  const citedIndices = new Set<number>();
  const regex = /\[(\d+(?:,\d+)*)\]/g;
  let match;
  while ((match = regex.exec(content)) !== null) {
    for (const group of match[1].split(",")) {
      const oneBasedIndex = parseInt(group, 10);
      const zeroBasedIndex = oneBasedIndex - 1;
      if (zeroBasedIndex >= 0 && zeroBasedIndex < sources.length) {
        citedIndices.add(zeroBasedIndex);
      }
    }
  }

  if (citedIndices.size === 0 && sources.length === 0) return null;

  const visible =
    citedIndices.size > 0
      ? sources
          .map((source, i) => ({ source, index: i }))
          .filter(({ index }) => citedIndices.has(index))
      : sources.map((source, index) => ({ source, index }));

  return (
    <div className="text-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors text-xs"
      >
        <span>
          {visible.length} source{visible.length !== 1 ? "s" : ""}
        </span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 shrink-0 transition-transform",
            open && "rotate-180",
          )}
        />
      </button>
      {open && (
        <div className="mt-2 flex flex-col gap-2">
          {visible.map(({ source, index }) => (
            <SourceCard key={index} source={source} index={index} />
          ))}
        </div>
      )}
    </div>
  );
}
