import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { api } from "@/api/client";

export function Header() {
  const { data: health, isError } = useQuery({
    queryKey: ["health"],
    queryFn: api.getHealth,
    refetchInterval: 30000,
    retry: 1,
  });

  const services = health
    ? [
        { name: "ES", ok: health.elasticsearch },
        { name: "Qdrant", ok: health.qdrant },
      ]
    : [];

  return (
    <header className="flex h-14 items-center justify-between border-b px-6">
      <div className="text-sm text-muted-foreground">
        Web-based admin interface for Harmony crawling
      </div>

      <div className="flex items-center gap-3">
        <Activity className="h-4 w-4 text-muted-foreground" />
        {isError || (!health && !isError) ? (
          <Badge variant="destructive">
            {isError ? "unreachable" : "connecting…"}
          </Badge>
        ) : (
          services.map(({ name, ok }) => (
            <div key={name} className="flex items-center gap-1.5">
              <span className="text-xs text-muted-foreground">{name}</span>
              <Badge variant={ok ? "success" : "destructive"}>
                {ok ? "ok" : "down"}
              </Badge>
            </div>
          ))
        )}
      </div>
    </header>
  );
}
