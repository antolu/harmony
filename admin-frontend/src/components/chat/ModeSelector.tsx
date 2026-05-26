import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type Mode = "search" | "deep_research" | "chat";

interface ModeSelectorProps {
  value: Mode;
  onChange: (mode: Mode) => void;
}

export function ModeSelector({ value, onChange }: ModeSelectorProps) {
  return (
    <div className="flex items-center gap-1">
      <Button
        variant={value === "search" ? "default" : "ghost"}
        size="sm"
        className="h-7 text-xs px-2"
        onClick={() => onChange("search")}
      >
        AI Search
      </Button>
      <Button
        variant={value === "deep_research" ? "default" : "ghost"}
        size="sm"
        className="h-7 text-xs px-2"
        onClick={() => onChange("deep_research")}
      >
        Deep Research
      </Button>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span>
              <Button
                variant={value === "chat" ? "default" : "ghost"}
                size="sm"
                className={cn("h-7 text-xs px-2 gap-1.5")}
                disabled
              >
                Chat
                <Badge variant="secondary" className="text-xs px-1 py-0 h-4">
                  Coming soon
                </Badge>
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            Coming soon — conversational mode without mandatory retrieval
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}
