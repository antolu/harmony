import { useState } from "react";
import { Button } from "@/components/ui/button";
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
  const [showAll, setShowAll] = useState(false);

  const citedIndices = new Set<number>();
  const regex = /\[(\d+)\]/g;
  let match;
  while ((match = regex.exec(content)) !== null) {
    const oneBasedIndex = parseInt(match[1], 10);
    const zeroBasedIndex = oneBasedIndex - 1;
    if (zeroBasedIndex >= 0 && zeroBasedIndex < sources.length) {
      citedIndices.add(zeroBasedIndex);
    }
  }

  if (citedIndices.size === 0 && sources.length === 0) return null;

  if (citedIndices.size > 0) {
    const citedSources = sources
      .map((source, i) => ({ source, index: i }))
      .filter(({ index }) => citedIndices.has(index));

    const visible = showAll ? citedSources : citedSources.slice(0, 3);
    const hiddenCount = citedSources.length - 3;

    return (
      <div className="flex flex-wrap gap-2">
        {visible.map(({ source, index }) => (
          <SourceCard key={index} source={source} index={index} />
        ))}
        {!showAll && hiddenCount > 0 && (
          <Button variant="ghost" size="sm" onClick={() => setShowAll(true)}>
            Show {hiddenCount} more
          </Button>
        )}
      </div>
    );
  }

  const visible = showAll ? sources : sources.slice(0, 3);
  const hiddenCount = sources.length - 3;

  return (
    <div className="flex flex-wrap gap-2">
      {visible.map((source, index) => (
        <SourceCard key={index} source={source} index={index} />
      ))}
      {!showAll && hiddenCount > 0 && (
        <Button variant="ghost" size="sm" onClick={() => setShowAll(true)}>
          Show {hiddenCount} more
        </Button>
      )}
    </div>
  );
}
