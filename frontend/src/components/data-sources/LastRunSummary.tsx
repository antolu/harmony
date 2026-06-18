import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface LastRunSummaryProps {
  status: string | null;
  docCount: number | null;
  lastRunAt: string | null;
}

function statusBadgeClass(status: string | null): string {
  if (status === "success" || status === "completed") {
    return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
  }
  if (status === "failed" || status === "error") {
    return "bg-destructive/15 text-destructive";
  }
  return "bg-muted text-muted-foreground";
}

function statusLabel(status: string | null): string {
  if (status === "success" || status === "completed") return "Success";
  if (status === "failed" || status === "error") return "Failed";
  return "Idle";
}

export function LastRunSummary({
  status,
  docCount,
  lastRunAt,
}: LastRunSummaryProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Last Run Summary</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Status</p>
            <Badge className={statusBadgeClass(status)}>
              {statusLabel(status)}
            </Badge>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Documents indexed</p>
            <p className="text-sm font-medium">{docCount ?? "—"}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Last run timestamp</p>
            <p className="text-sm font-medium">
              {lastRunAt ? new Date(lastRunAt).toLocaleString() : "—"}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
