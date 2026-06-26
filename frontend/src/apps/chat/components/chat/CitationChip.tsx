import { useState } from "react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/shared/components/ui/popover";
import { SourceCard } from "./SourceCard";
import type { SourceItem } from "@/shared/hooks/useChat";

interface Props {
  indices: number[];
  sources: SourceItem[];
}

export function CitationChip({ indices, sources }: Props) {
  const [open, setOpen] = useState(false);

  const zeroBasedIndices = indices
    .map((i) => i - 1)
    .filter((i) => i >= 0 && i < sources.length);

  if (zeroBasedIndices.length === 0) {
    return <>[{indices.join(",")}]</>;
  }

  const first = sources[zeroBasedIndices[0]];
  const extraCount = zeroBasedIndices.length - 1;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-0.5 rounded bg-muted px-1 align-super text-[0.65rem] font-medium text-muted-foreground hover:text-foreground hover:bg-muted-foreground/20 transition-colors"
          aria-label={`Sources: ${first.title}${extraCount > 0 ? ` and ${extraCount} more` : ""}`}
        >
          {zeroBasedIndices[0] + 1}
          {extraCount > 0 && <span>+{extraCount}</span>}
        </button>
      </PopoverTrigger>
      <PopoverContent className="flex flex-col gap-2 w-auto p-2">
        {zeroBasedIndices.map((index) => (
          <SourceCard key={index} source={sources[index]} index={index} />
        ))}
      </PopoverContent>
    </Popover>
  );
}
