import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Globe,
  Database,
  Square,
  Pause,
  PlayCircle,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/api/client";
import type { Job } from "@/api/client";
import { useState } from "react";

function getStatusBadge(status: Job["status"]) {
  switch (status) {
    case "running":
      return (
        <Badge variant="default">
          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          Running
        </Badge>
      );
    case "completed":
      return (
        <Badge variant="success">
          <CheckCircle className="mr-1 h-3 w-3" />
          Completed
        </Badge>
      );
    case "failed":
      return (
        <Badge variant="destructive">
          <XCircle className="mr-1 h-3 w-3" />
          Failed
        </Badge>
      );
    case "paused":
      return (
        <Badge variant="warning">
          <Pause className="mr-1 h-3 w-3" />
          Paused
        </Badge>
      );
    case "stopped":
      return (
        <Badge variant="secondary">
          <Square className="mr-1 h-3 w-3" />
          Stopped
        </Badge>
      );
    case "pending":
      return (
        <Badge variant="outline">
          <Clock className="mr-1 h-3 w-3" />
          Pending
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function formatDuration(start?: string, end?: string): string {
  if (!start) return "-";

  const startDate = new Date(start);
  const endDate = end ? new Date(end) : new Date();
  const diff = endDate.getTime() - startDate.getTime();

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

export function Jobs() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const { data: jobs } = useQuery({
    queryKey: ["jobs", typeFilter, statusFilter],
    queryFn: () =>
      api.listJobs(
        typeFilter !== "all" ? typeFilter : undefined,
        statusFilter !== "all" ? statusFilter : undefined,
      ),
    refetchInterval: 3000,
  });

  const stopMutation = useMutation({
    mutationFn: (jobId: string) => api.stopJob(jobId),
    onSuccess: () => {
      toast({ title: "Job stopped" });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error) => {
      toast({
        title: "Stop failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const pauseMutation = useMutation({
    mutationFn: (jobId: string) => api.pauseJob(jobId),
    onSuccess: () => {
      toast({ title: "Job paused" });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error) => {
      toast({
        title: "Pause failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const resumeMutation = useMutation({
    mutationFn: (jobId: string) => api.resumeJob(jobId),
    onSuccess: () => {
      toast({ title: "Job resumed" });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error) => {
      toast({
        title: "Resume failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Jobs</h2>
        <p className="text-muted-foreground">
          View and manage crawl and index jobs
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-4">
          <div className="w-48">
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Job Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="crawl">Crawl</SelectItem>
                <SelectItem value="index">Index</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="w-48">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="running">Running</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
                <SelectItem value="stopped">Stopped</SelectItem>
                <SelectItem value="paused">Paused</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Jobs List */}
      <div className="space-y-4">
        {jobs?.length === 0 && (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No jobs found. Start a crawl or index job from the configuration
              pages.
            </CardContent>
          </Card>
        )}

        {jobs?.map((job) => (
          <Card key={job.id}>
            <CardContent className="pt-6">
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    {job.type === "crawl" ? (
                      <Globe className="h-5 w-5 text-muted-foreground" />
                    ) : (
                      <Database className="h-5 w-5 text-muted-foreground" />
                    )}
                    <span className="text-lg font-semibold">
                      {job.config_name}
                    </span>
                    {getStatusBadge(job.status)}
                    <Badge variant="outline">{job.type}</Badge>
                  </div>

                  <div className="flex gap-6 text-sm text-muted-foreground">
                    <span>ID: {job.id}</span>
                    <span>
                      Started:{" "}
                      {job.started_at
                        ? new Date(job.started_at).toLocaleString()
                        : "-"}
                    </span>
                    <span>
                      Duration:{" "}
                      {formatDuration(job.started_at, job.finished_at)}
                    </span>
                  </div>

                  {job.status === "running" && job.progress && (
                    <>
                      {job.type === "crawl" ? (
                        <div className="flex gap-6 text-sm">
                          <span>Pages: {job.progress.pages_crawled}</span>
                          <span>Pending: {job.progress.pages_pending}</span>
                          <span>Requests: {job.progress.requests_made}</span>
                          <span>
                            {job.progress.pages_per_min.toFixed(1)} pages/min
                          </span>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <div className="flex gap-6 text-sm">
                            <span>
                              Indexed: {job.progress.documents_indexed}
                              {job.progress.total_documents > 0 &&
                                ` / ${job.progress.total_documents}`}
                            </span>
                            {job.progress.current_phase && (
                              <span>Phase: {job.progress.current_phase}</span>
                            )}
                          </div>
                          {job.progress.total_documents > 0 && (
                            <Progress
                              value={
                                (job.progress.documents_indexed /
                                  job.progress.total_documents) *
                                100
                              }
                              className="h-1"
                            />
                          )}
                        </div>
                      )}
                    </>
                  )}

                  {job.error && (
                    <p className="text-sm text-destructive">{job.error}</p>
                  )}
                </div>

                <div className="flex gap-2">
                  {job.status === "running" && (
                    <>
                      {job.type === "crawl" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => pauseMutation.mutate(job.id)}
                          disabled={pauseMutation.isPending}
                        >
                          <Pause className="mr-1 h-4 w-4" />
                          Pause
                        </Button>
                      )}
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => stopMutation.mutate(job.id)}
                        disabled={stopMutation.isPending}
                      >
                        <Square className="mr-1 h-4 w-4" />
                        Stop
                      </Button>
                    </>
                  )}

                  {job.status === "paused" && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => resumeMutation.mutate(job.id)}
                      disabled={resumeMutation.isPending}
                    >
                      <PlayCircle className="mr-1 h-4 w-4" />
                      Resume
                    </Button>
                  )}

                  <Button variant="ghost" size="sm" asChild>
                    <Link to={`/jobs/${job.id}`}>View Details</Link>
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
