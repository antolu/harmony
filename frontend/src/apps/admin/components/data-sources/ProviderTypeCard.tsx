import { Globe, HardDrive, Package } from "lucide-react";
import { Card } from "@/shared/components/ui/card";
import { cn } from "@/shared/lib/utils";

interface ProviderTypeCardProps {
  type: string;
  displayName: string;
  description: string;
  selected?: boolean;
  onClick: () => void;
}

const PROVIDER_ICONS: Record<string, typeof Globe> = {
  "web-crawler": Globe,
  filesystem: HardDrive,
};

export function ProviderTypeCard({
  type,
  displayName,
  description,
  selected = false,
  onClick,
}: ProviderTypeCardProps) {
  const Icon = PROVIDER_ICONS[type] ?? Package;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      className={cn(
        "cursor-pointer p-6 hover:border-primary",
        selected && "border-primary ring-2 ring-primary/20",
      )}
    >
      <Icon className="h-8 w-8" />
      <p className="text-sm font-bold mt-3">{displayName}</p>
      <p className="text-sm text-muted-foreground">{description}</p>
    </Card>
  );
}
