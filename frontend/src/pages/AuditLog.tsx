import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
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

const ACTION_COLORS: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  document_deleted: "destructive",
  model_created: "default",
  model_deleted: "destructive",
  schedule_created: "default",
  schedule_deleted: "destructive",
  blacklist_pattern_added: "secondary",
  blacklist_pattern_deleted: "destructive",
  job_started: "default",
  job_cancelled: "secondary",
};

const PAGE_SIZE = 50;

export function AuditLog() {
  const [userId, setUserId] = useState("");
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [daysBack, setDaysBack] = useState("30");
  const [offset, setOffset] = useState(0);
  const accumulatedEvents = useRef<import("@/api/client").AuditEvent[]>([]);

  const baseFilters = {
    user_id: userId || undefined,
    action: action || undefined,
    days_back: Number(daysBack),
    limit: PAGE_SIZE,
  };

  const filters = { ...baseFilters, offset };

  const { data, isLoading } = useQuery({
    queryKey: ["auditLog", filters],
    queryFn: () => api.queryAuditLog(filters),
  });

  useEffect(() => {
    if (data?.events) {
      if (offset === 0) {
        accumulatedEvents.current = data.events;
      } else {
        accumulatedEvents.current = [
          ...accumulatedEvents.current,
          ...data.events,
        ];
      }
    }
  }, [data, offset]);

  const allEvents = accumulatedEvents.current;
  const total = data?.total ?? 0;

  const distinctActions = useMemo(
    () => [...new Set(allEvents.map((e) => e.action))].sort(),
    [allEvents],
  );

  const distinctEntityTypes = useMemo(
    () => [...new Set(allEvents.map((e) => e.entity_type))].sort(),
    [allEvents],
  );

  const events = entityType
    ? allEvents.filter((e) => e.entity_type === entityType)
    : allEvents;

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
          <label className="text-xs text-muted-foreground">Actor (email)</label>
          <Input
            value={userId}
            onChange={(e) => {
              setUserId(e.target.value);
              setOffset(0);
            }}
            placeholder="Filter by email"
            className="w-48"
          />
        </div>
        <div className="flex flex-col gap-1 w-52">
          <label className="text-xs text-muted-foreground">Action</label>
          <Combobox
            options={distinctActions}
            value={action}
            onChange={(v) => {
              setAction(v);
              setOffset(0);
            }}
            placeholder="Filter by action"
            searchPlaceholder="Search actions..."
            emptyText="No actions found."
          />
        </div>
        <div className="flex flex-col gap-1 w-48">
          <label className="text-xs text-muted-foreground">Entity type</label>
          <Combobox
            options={distinctEntityTypes}
            value={entityType}
            onChange={(v) => {
              setEntityType(v);
              setOffset(0);
            }}
            placeholder="Filter by type"
            searchPlaceholder="Search types..."
            emptyText="No types found."
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
                    <TableCell className="text-xs">
                      {event.user_email}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={ACTION_COLORS[event.action] ?? "outline"}
                        className="text-xs font-mono cursor-pointer"
                        onClick={() => {
                          setAction((prev) =>
                            prev === event.action ? "" : event.action,
                          );
                          setOffset(0);
                        }}
                      >
                        {event.action}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="secondary"
                        className="text-xs font-mono cursor-pointer"
                        onClick={() => {
                          setEntityType((prev) =>
                            prev === event.entity_type ? "" : event.entity_type,
                          );
                          setOffset(0);
                        }}
                      >
                        {event.entity_type}
                      </Badge>
                    </TableCell>
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

          {total > allEvents.length && (
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
