import { useState, useEffect } from "react";
import { Search, BookOpen, RefreshCw, Wrench, ChevronDown } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import type { StepEntry } from "@/hooks/useChat";

interface StepListProps {
  steps: StepEntry[];
  isStreaming: boolean;
}

function StepIcon({ type }: { type: StepEntry["type"] }) {
  switch (type) {
    case "search":
      return <Search className="h-3.5 w-3.5 shrink-0" />;
    case "reading":
      return <BookOpen className="h-3.5 w-3.5 shrink-0" />;
    case "refining":
      return <RefreshCw className="h-3.5 w-3.5 shrink-0" />;
    case "tool_call":
      return <Wrench className="h-3.5 w-3.5 shrink-0" />;
  }
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

  const searchCount = steps.filter((s) => s.type === "search").length;
  const summaryText = isStreaming
    ? "Thinking..."
    : searchCount > 0
      ? `Searched ${searchCount} quer${searchCount !== 1 ? "ies" : "y"}`
      : "Tools used";

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
            {steps.map((step) => (
              <div
                key={step.id}
                className={cn(
                  "flex items-start gap-1.5 text-xs",
                  step.completed ? "text-foreground" : "text-muted-foreground",
                )}
              >
                <StepIcon type={step.type} />
                <span>{step.text}</span>
              </div>
            ))}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
