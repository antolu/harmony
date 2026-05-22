import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { api } from "@/api/client";

const PAGE_SIZE = 50;

export function TokenUsage() {
  const [model, setModel] = useState<string>("all");
  const [dateRange, setDateRange] = useState<string>("all");
  const [page, setPage] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["tokenUsage", model, dateRange, refreshKey],
    queryFn: () =>
      api.getTokenUsage({
        model: model === "all" ? undefined : model,
        date_range: dateRange === "all" ? undefined : dateRange,
      }),
  });

  const sorted = data
    ? [...data].sort(
        (a, b) =>
          new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime(),
      )
    : [];

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const paginated = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const uniqueModels = data
    ? Array.from(new Set(data.map((r) => r.model))).sort()
    : [];

  function handleModelChange(value: string) {
    setModel(value);
    setPage(0);
  }

  function handleDateRangeChange(value: string) {
    setDateRange(value);
    setPage(0);
  }

  function handleRefresh() {
    setRefreshKey((k) => k + 1);
    setPage(0);
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Token Usage</h2>
        <p className="text-muted-foreground">
          Read-only usage log per model, user, and date.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <Select value={model} onValueChange={handleModelChange}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All models" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All models</SelectItem>
            {uniqueModels.map((m) => (
              <SelectItem key={m} value={m}>
                {m}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={dateRange} onValueChange={handleDateRangeChange}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All time" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All time</SelectItem>
            <SelectItem value="today">Today</SelectItem>
            <SelectItem value="7d">Last 7 days</SelectItem>
            <SelectItem value="30d">Last 30 days</SelectItem>
          </SelectContent>
        </Select>

        <Button variant="outline" onClick={handleRefresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {isError && (
        <Alert variant="destructive">
          <AlertDescription>
            Failed to load token usage. Check that the API is reachable.
          </AlertDescription>
        </Alert>
      )}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>User</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead>Agent Step</TableHead>
              <TableHead className="text-right">Input tokens</TableHead>
              <TableHead className="text-right">Output tokens</TableHead>
              <TableHead className="text-right">Total tokens</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="h-24 text-center">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : paginated.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={8}
                  className="h-24 text-center text-muted-foreground"
                >
                  No token usage recorded yet.
                </TableCell>
              </TableRow>
            ) : (
              paginated.map((row) => (
                <TableRow key={row.trace_id}>
                  <TableCell className="text-sm">
                    {new Date(row.recorded_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-sm">{row.user_id}</TableCell>
                  <TableCell className="text-sm">{row.model}</TableCell>
                  <TableCell className="text-sm">{row.provider}</TableCell>
                  <TableCell className="text-sm">{row.agent_step}</TableCell>
                  <TableCell className="text-right text-sm">
                    {row.input_tokens.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right text-sm">
                    {row.output_tokens.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right text-sm">
                    {row.total_tokens.toLocaleString()}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page + 1} of {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
