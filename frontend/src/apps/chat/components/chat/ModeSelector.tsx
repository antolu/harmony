import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";

type Mode = "search" | "deep_research" | "chat";

interface ModeSelectorProps {
  value: Mode;
  onChange: (mode: Mode) => void;
}

export function ModeSelector({ value, onChange }: ModeSelectorProps) {
  return (
    <TooltipProvider>
      <Select value={value} onValueChange={(v) => onChange(v as Mode)}>
        <SelectTrigger className="h-7 text-xs w-auto min-w-[110px] border-0 bg-transparent px-2 focus:ring-0 focus:ring-offset-0">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="search">Search</SelectItem>
          <Tooltip>
            <TooltipTrigger asChild>
              <SelectItem value="deep_research">Deep Research</SelectItem>
            </TooltipTrigger>
            <TooltipContent side="right">
              Multi-step agentic search — researches multiple angles before
              synthesising an answer
            </TooltipContent>
          </Tooltip>
          <SelectItem value="chat" disabled>
            Chat (coming soon)
          </SelectItem>
        </SelectContent>
      </Select>
    </TooltipProvider>
  );
}
