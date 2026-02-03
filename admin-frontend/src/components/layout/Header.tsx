import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { api } from "@/api/client";

export function Header() {
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: api.getHealth,
    refetchInterval: 30000,
  });

  return (
    <header className="flex h-14 items-center justify-between border-b px-6">
      <div className="text-sm text-muted-foreground">
        Web-based admin interface for Harmony crawling
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4" />
          <span className="text-sm">API:</span>
          <Badge
            variant={health?.status === "healthy" ? "success" : "destructive"}
          >
            {health?.status || "unknown"}
          </Badge>
        </div>
      </div>
    </header>
  );
}
