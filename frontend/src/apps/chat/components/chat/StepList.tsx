import { useState } from "react";
import {
  Globe,
  Search,
  RefreshCw,
  Wrench,
  ChevronRight,
  Loader2,
} from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/shared/components/ui/collapsible";
import { cn } from "@/shared/lib/utils";
import type { StepEntry } from "@/shared/hooks/useChat";
import { StepSourceChip } from "./StepSourceChip";

interface StepListProps {
  steps: StepEntry[];
  isStreaming: boolean;
}

function StepIcon({ kind }: { kind: StepEntry["kind"] }) {
  switch (kind) {
    case "search":
      return <Search className="h-3.5 w-3.5 shrink-0" />;
    case "thinking":
      return <RefreshCw className="h-3.5 w-3.5 shrink-0" />;
    case "tool_call":
      return <Wrench className="h-3.5 w-3.5 shrink-0" />;
  }
}

function StepRow({ step }: { step: StepEntry }) {
  const [expanded, setExpanded] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const expandable = step.kind === "search" && !!step.sources?.length;
  const sources = step.sources ?? [];
  const visible = showAll ? sources : sources.slice(0, 4);
  const hiddenCount = sources.length - 4;

  const row = (
    <div className="flex items-start gap-1.5 text-xs text-muted-foreground">
      <StepIcon kind={step.kind} />
      <span className="flex-1">{step.text}</span>
      {expandable && (
        <ChevronRight
          className={cn(
            "h-3 w-3 shrink-0 transition-transform mt-0.5",
            expanded && "rotate-90",
          )}
        />
      )}
    </div>
  );

  if (!expandable) {
    return row;
  }

  return (
    <Collapsible open={expanded} onOpenChange={setExpanded}>
      <CollapsibleTrigger className="w-full text-left">
        {row}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-1 ml-5 flex flex-wrap gap-1">
          {visible.map((source) => (
            <StepSourceChip
              key={source.url}
              title={source.title}
              url={source.url}
            />
          ))}
          {!showAll && hiddenCount > 0 && (
            <button
              type="button"
              className="text-[0.65rem] text-muted-foreground hover:text-foreground transition-colors px-1"
              onClick={(e) => {
                e.stopPropagation();
                setShowAll(true);
              }}
            >
              +{hiddenCount} more
            </button>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function completedSummary(steps: StepEntry[]): string {
  const searchCount = steps.filter((s) => s.kind === "search").length;
  const totalSources = steps.reduce(
    (acc, s) => acc + (s.sources?.length ?? 0),
    0,
  );
  if (searchCount > 0 && totalSources > 0) {
    return `Searched ${totalSources} source${totalSources !== 1 ? "s" : ""}`;
  }
  if (searchCount > 0) {
    return `Ran ${searchCount} search${searchCount !== 1 ? "es" : ""}`;
  }
  return `Completed ${steps.length} step${steps.length !== 1 ? "s" : ""}`;
}

export function StepList({ steps, isStreaming }: StepListProps) {
  const [open, setOpen] = useState(false);
  const [prevIsStreaming, setPrevIsStreaming] = useState(isStreaming);
  if (isStreaming !== prevIsStreaming) {
    setPrevIsStreaming(isStreaming);
    if (!isStreaming) setOpen(false);
  }

  if (steps.length === 0 && !isStreaming) {
    return null;
  }

  const summaryText = isStreaming
    ? steps.length > 0
      ? steps[steps.length - 1].text
      : "Thinking…"
    : completedSummary(steps);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex w-full items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors group/step">
        {isStreaming ? (
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
        ) : (
          <Globe className="h-3.5 w-3.5 shrink-0" />
        )}
        <span className="flex-1 text-left text-xs">{summaryText}</span>
        <ChevronRight
          className={cn(
            "h-3 w-3 shrink-0 transition-transform opacity-0 group-hover/step:opacity-100",
            open && "rotate-90",
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-1.5 ml-5 flex flex-col gap-1">
          {steps.map((step) => (
            <StepRow key={step.id} step={step} />
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
