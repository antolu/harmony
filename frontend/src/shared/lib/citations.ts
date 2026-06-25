import type { SourceItem } from "@/shared/hooks/useChat";

export interface CitationProcessResult {
  processedContent: string;
  usedSources: SourceItem[];
}

/**
 * Parses markdown text for citations like [3] or [1, 4], renumbers them sequentially starting from 1,
 * and filters the `sources` array so that the remaining sources match the new sequential numbering.
 */
export function processCitations(
  content: string,
  sources: SourceItem[],
): CitationProcessResult {
  if (!sources || sources.length === 0 || !content) {
    return { processedContent: content, usedSources: [] };
  }

  const mapping = new Map<number, number>();
  const usedSources: SourceItem[] = [];

  // Match citation blocks like [1] or [1, 2] or [1, 2, 3]
  const citationRegex = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

  const processedContent = content.replace(citationRegex, (match, group) => {
    const rawNumbers = group
      .split(",")
      .map((n: string) => parseInt(n.trim(), 10))
      .filter((n: number) => !isNaN(n) && n >= 1 && n <= sources.length);

    if (rawNumbers.length === 0) return match; // If none of the numbers are valid, leave it alone (could be hallucinated or not a citation)

    const newNumbers = rawNumbers.map((raw: number) => {
      if (!mapping.has(raw)) {
        const nextIndex = mapping.size + 1;
        mapping.set(raw, nextIndex);
        usedSources.push(sources[raw - 1]);
      }
      return mapping.get(raw)!;
    });

    // Sort to keep [1, 2] instead of [2, 1] if they appeared in strange order
    newNumbers.sort((a: number, b: number) => a - b);
    return `[${newNumbers.join(", ")}]`;
  });

  return { processedContent, usedSources };
}
