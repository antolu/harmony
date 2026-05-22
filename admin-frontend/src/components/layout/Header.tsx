import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { api } from "@/api/client";

export function Header() {
  const { data: health, isError } = useQuery({
    queryKey: ["readiness"],
    queryFn: api.getHealth,
    refetchInterval: 30000,
    retry: 1,
  });

  const deps = health?.dependencies;
  const services = deps
    ? [
        { name: "ES", ok: deps.elasticsearch },
        { name: "Redis", ok: deps.redis },
        {
          name: "Qdrant",
          ok: deps.qdrant === true || deps.qdrant === "disabled",
        },
      ]
    : null;

  return (
    <header className="flex h-14 items-center justify-between border-b px-6">
      <div className="text-sm text-muted-foreground">
        Web-based admin interface for Harmony crawling
      </div>

      <div className="flex items-center gap-3">
        <Activity className="h-4 w-4 text-muted-foreground" />
        {isError ? (
          <Badge variant="destructive">unreachable</Badge>
        ) : !services ? (
          <Badge variant="secondary">connecting…</Badge>
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
