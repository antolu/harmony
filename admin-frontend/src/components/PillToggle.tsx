import { cn } from "@/lib/utils";

interface PillToggleProps {
  value: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  labelOn?: string;
  labelOff?: string;
  className?: string;
}

export function PillToggle({
  value,
  onChange,
  disabled = false,
  labelOn = "ON",
  labelOff = "OFF",
  className,
}: PillToggleProps) {
  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!value)}
      disabled={disabled}
      className={cn(
        "inline-flex items-center rounded-full px-4 py-1 text-sm font-medium transition-colors",
        value
          ? "bg-primary text-primary-foreground"
          : "border border-input bg-background text-muted-foreground",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      {value ? labelOn : labelOff}
    </button>
  );
}
