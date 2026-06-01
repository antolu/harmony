import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const DAYS_OPTIONS = [
  { label: "7 days", value: "7" },
  { label: "30 days", value: "30" },
  { label: "90 days", value: "90" },
];

const PAGE_SIZE = 50;

export function AuditLog() {
  const [userId, setUserId] = useState("");
  const [action, setAction] = useState("");
  const [daysBack, setDaysBack] = useState("30");
  const [offset, setOffset] = useState(0);

  const filters = {
    user_id: userId || undefined,
    action: action || undefined,
    days_back: Number(daysBack),
    limit: PAGE_SIZE,
    offset,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["auditLog", filters],
    queryFn: () => api.queryAuditLog(filters),
  });

  const events = data?.events ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Audit Log</h2>
        <p className="text-muted-foreground">
          Track admin actions and system events.
        </p>
      </div>

      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">
            Actor (user ID)
          </label>
          <Input
            value={userId}
            onChange={(e) => {
              setUserId(e.target.value);
              setOffset(0);
            }}
            placeholder="Filter by user ID"
            className="w-48"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Action</label>
          <Input
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setOffset(0);
            }}
            placeholder="Filter by action"
            className="w-48"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Date range</label>
          <Select
            value={daysBack}
            onValueChange={(v) => {
              setDaysBack(v);
              setOffset(0);
            }}
          >
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DAYS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : events.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No audit events found for the selected filters.
        </p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Entity Type</TableHead>
                <TableHead>Entity ID</TableHead>
                <TableHead>Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((event) => {
                const detailsStr = JSON.stringify(event.details);
                const truncated =
                  detailsStr.length > 80
                    ? detailsStr.slice(0, 80) + "…"
                    : detailsStr;
                return (
                  <TableRow key={event.id}>
                    <TableCell className="whitespace-nowrap text-xs">
                      {new Date(event.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {event.user_id}
                    </TableCell>
                    <TableCell>{event.action}</TableCell>
                    <TableCell>{event.entity_type}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {event.entity_id ?? "—"}
                    </TableCell>
                    <TableCell>
                      <span
                        title={detailsStr}
                        className="font-mono text-xs cursor-help"
                      >
                        {truncated}
                      </span>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>

          {total > offset + events.length && (
            <Button
              variant="outline"
              onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
            >
              Load more
            </Button>
          )}
        </>
      )}
    </div>
  );
}
