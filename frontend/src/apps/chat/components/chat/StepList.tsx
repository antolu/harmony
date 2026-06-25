import { useState, useEffect } from "react";
import { Search, RefreshCw, Wrench, ChevronDown } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/shared/components/ui/collapsible";
import { Button } from "@/shared/components/ui/button";
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
    case "refining":
      return <RefreshCw className="h-3.5 w-3.5 shrink-0" />;
    case "tool_call":
      return <Wrench className="h-3.5 w-3.5 shrink-0" />;
  }
}

function StepRow({ step, live }: { step: StepEntry; live: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const expandable = step.kind === "search" && !!step.sources?.length;
  const sources = step.sources ?? [];
  const visible = showAll ? sources : sources.slice(0, 3);
  const hiddenCount = sources.length - 3;

  const row = (
    <div
      className={cn(
        "flex items-start gap-1.5 text-xs",
        live ? "text-muted-foreground" : "text-foreground",
      )}
    >
      <StepIcon kind={step.kind} />
      <span className="flex-1">{step.text}</span>
      {expandable && (
        <ChevronDown
          className={cn(
            "h-3 w-3 shrink-0 transition-transform",
            expanded && "rotate-180",
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
            <Button
              variant="ghost"
              size="sm"
              className="h-5 px-1.5 text-xs"
              onClick={() => setShowAll(true)}
            >
              +{hiddenCount} more
            </Button>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export function StepList({ steps, isStreaming }: StepListProps) {
  const [open, setOpen] = useState(isStreaming);

  useEffect(() => {
    if (!isStreaming) {
      setOpen(false);
    } else {
      setOpen(true);
    }
  }, [isStreaming]);

  if (steps.length === 0 && !isStreaming) {
    return null;
  }

  const summaryText = isStreaming
    ? steps.length > 0
      ? steps[steps.length - 1].text
      : "Thinking..."
    : `Completed ${steps.length} step${steps.length !== 1 ? "s" : ""}`;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="bg-muted/50 rounded-md p-2 text-sm">
        <CollapsibleTrigger className="flex w-full items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors">
          <span className="flex-1 text-left text-xs">{summaryText}</span>
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 shrink-0 transition-transform",
              open && "rotate-180",
            )}
          />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="mt-2 flex flex-col gap-1">
            {steps.map((step, index) => (
              <StepRow
                key={step.id}
                step={step}
                live={isStreaming && index === steps.length - 1}
              />
            ))}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
