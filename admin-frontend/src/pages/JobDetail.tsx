import { useEffect, useState, useRef } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Globe,
  Database,
  Square,
  Pause,
  PlayCircle,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Shield,
  RotateCcw,
  Eraser,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useToast } from "@/hooks/use-toast";
import { api, createSSEConnection } from "@/api/client";
import type { Job, JobProgress } from "@/api/client";

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

export function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [progress, setProgress] = useState<JobProgress | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [safetyPending, setSafetyPending] = useState<
    Array<{ url: string; reason: string; pattern: string }>
  >([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const { data: job, isLoading } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: 5000,
  });

  const isTerminal =
    job?.status === "completed" ||
    job?.status === "failed" ||
    job?.status === "stopped";

  const { data: initialLogs } = useQuery({
    queryKey: ["jobLogs", jobId],
    queryFn: () => api.getJobLogs(jobId!, 200),
    enabled: !!jobId && !isTerminal,
  });

  const { data: structuredLogs } = useQuery({
    queryKey: ["jobLogsStructured", jobId],
    queryFn: () => api.getJobLogsStructured(jobId!),
    enabled: !!jobId && !!isTerminal,
  });

  useEffect(() => {
    if (initialLogs?.lines) {
      setLogs(initialLogs.lines);
    }
  }, [initialLogs]);

  useEffect(() => {
    if (structuredLogs?.logs) {
      setLogs(
        structuredLogs.logs.map(
          (l) => `[${l.level.toUpperCase()}] ${l.message}`,
        ),
      );
    }
  }, [structuredLogs]);

  useEffect(() => {
    if (!jobId || !job || job.status !== "running") return;

    const closeProgress = createSSEConnection(
      `/jobs/${jobId}/progress/stream`,
      (event, data) => {
        if (event === "progress") {
          setProgress(data as JobProgress);
        }
        if (event === "safety_pending") {
          const item = data as { url: string; reason: string; pattern: string };
          setSafetyPending((prev) => {
            if (prev.some((p) => p.pattern === item.pattern)) return prev;
            return [...prev, item];
          });
        }
      },
    );

    const closeLogs = createSSEConnection(
      `/jobs/${jobId}/logs/stream`,
      (event, data) => {
        if (event === "log") {
          setLogs((prev) => [...prev, (data as { line: string }).line]);
        }
      },
    );

    return () => {
      closeProgress();
      closeLogs();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, job?.status]);

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const stopMutation = useMutation({
    mutationFn: () => api.stopJob(jobId!),
    onSuccess: () => {
      toast({ title: "Job stopped" });
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
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
    mutationFn: () => api.pauseJob(jobId!),
    onSuccess: () => {
      toast({ title: "Job paused" });
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
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
    mutationFn: () => api.resumeJob(jobId!),
    onSuccess: () => {
      toast({ title: "Job resumed" });
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
    },
    onError: (error) => {
      toast({
        title: "Resume failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const rerunMutation = useMutation({
    mutationFn: () => api.retriggerJob(jobId!),
    onSuccess: (newJob) => {
      toast({ title: "Job re-triggered" });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate(`/admin/jobs/${newJob.id}`);
    },
    onError: (error) => {
      toast({
        title: "Re-run failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const startFreshMutation = useMutation({
    mutationFn: () => api.startFreshJob(jobId!),
    onSuccess: (newJob) => {
      toast({ title: "Fresh job started" });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate(`/admin/jobs/${newJob.id}`);
    },
    onError: (error) => {
      toast({
        title: "Start fresh failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const refreshLogs = async () => {
    const result = await api.getJobLogs(jobId!, 500);
    setLogs(result.lines);
  };

  const handleSafetyDecision = async (pattern: string, decision: string) => {
    try {
      await api.publishSafetyDecision(job!.id, pattern, decision);
      setSafetyPending((prev) => prev.filter((p) => p.pattern !== pattern));
    } catch (error) {
      toast({
        title: "Decision failed",
        description: (error as Error).message,
        variant: "destructive",
      });
    }
  };

  if (isLoading || !job) {
    return <div>Loading...</div>;
  }

  const currentProgress = progress || job.progress;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/jobs">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <div className="flex items-center gap-3">
            {job.type === "crawl" ? (
              <Globe className="h-6 w-6" />
            ) : (
              <Database className="h-6 w-6" />
            )}
            <h2 className="text-3xl font-bold tracking-tight">
              {job.config_name}
            </h2>
            {getStatusBadge(job.status)}
          </div>
          <p className="text-muted-foreground">Job ID: {job.id}</p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          onClick={() => rerunMutation.mutate()}
          disabled={rerunMutation.isPending}
        >
          {rerunMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RotateCcw className="mr-2 h-4 w-4" />
          )}
          Re-run
        </Button>

        {isTerminal && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline">
                <Eraser className="mr-2 h-4 w-4" />
                Start fresh
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Start fresh?</AlertDialogTitle>
                <AlertDialogDescription>
                  This discards the resume checkpoint. The full crawl or index
                  will run from the beginning.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => startFreshMutation.mutate()}
                  disabled={startFreshMutation.isPending}
                >
                  Start fresh
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}

        {job.status === "running" && (
          <>
            {job.type === "crawl" && (
              <Button
                variant="outline"
                onClick={() => pauseMutation.mutate()}
                disabled={pauseMutation.isPending}
              >
                <Pause className="mr-2 h-4 w-4" />
                Pause
              </Button>
            )}
            <Button
              variant="destructive"
              onClick={() => stopMutation.mutate()}
              disabled={stopMutation.isPending}
            >
              <Square className="mr-2 h-4 w-4" />
              Stop
            </Button>
          </>
        )}

        {job.status === "paused" && (
          <Button
            onClick={() => resumeMutation.mutate()}
            disabled={resumeMutation.isPending}
          >
            <PlayCircle className="mr-2 h-4 w-4" />
            Resume
          </Button>
        )}
      </div>

      {/* Progress */}
      <Card>
        <CardHeader>
          <CardTitle>Progress</CardTitle>
          <CardDescription>
            {job.started_at && (
              <>
                Started:{" "}
                {new Date(job.started_at).toLocaleString(undefined, {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </>
            )}
            {job.finished_at && (
              <>
                {" "}
                | Finished:{" "}
                {new Date(job.finished_at).toLocaleString(undefined, {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {job.type === "crawl" ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Pages Crawled</p>
                <p className="text-2xl font-bold">
                  {currentProgress.pages_crawled}
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Pending</p>
                <p className="text-2xl font-bold">
                  {currentProgress.pages_pending}
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Requests Made</p>
                <p className="text-2xl font-bold">
                  {currentProgress.requests_made}
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Speed</p>
                <p className="text-2xl font-bold">
                  {currentProgress.pages_per_min.toFixed(1)} /min
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    {currentProgress.current_phase === "embedding"
                      ? "Documents Embedded"
                      : "Documents Indexed"}
                  </p>
                  <p className="text-sm font-medium">
                    {currentProgress.documents_indexed}
                    {currentProgress.total_documents > 0 &&
                      ` / ${currentProgress.total_documents}`}
                  </p>
                </div>
                {currentProgress.total_documents > 0 && (
                  <Progress
                    value={
                      (currentProgress.documents_indexed /
                        currentProgress.total_documents) *
                      100
                    }
                  />
                )}
              </div>
              {currentProgress.current_phase && (
                <div className="space-y-1">
                  <p className="text-sm text-muted-foreground">Current Phase</p>
                  <p className="text-sm font-medium capitalize">
                    {currentProgress.current_phase}
                  </p>
                </div>
              )}
            </div>
          )}

          {currentProgress.current_url && (
            <div className="mt-4">
              <p className="text-sm text-muted-foreground">Current URL</p>
              <p className="text-sm font-mono truncate">
                {currentProgress.current_url}
              </p>
            </div>
          )}

          {job.error && (
            <div className="mt-4 p-3 bg-destructive/10 rounded-md">
              <p className="text-sm font-medium text-destructive">Error</p>
              <p className="text-sm">{job.error}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Safety Pending */}
      {job.type === "crawl" && safetyPending.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
              Safety Decisions Pending
            </CardTitle>
            <CardDescription>
              {safetyPending.length} URL(s) awaiting approval
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {safetyPending.map((item) => (
              <div
                key={item.pattern}
                className="border rounded-md p-4 space-y-2"
              >
                <div>
                  <p className="text-sm font-mono truncate">{item.url}</p>
                  <p className="text-sm text-muted-foreground">{item.reason}</p>
                  <p className="text-xs text-muted-foreground font-mono">
                    Pattern: {item.pattern}
                  </p>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button
                    size="sm"
                    variant="default"
                    onClick={() => handleSafetyDecision(item.pattern, "allow")}
                  >
                    Allow
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleSafetyDecision(item.pattern, "deny")}
                  >
                    Deny
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleSafetyDecision(item.pattern, "always")}
                  >
                    Always
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleSafetyDecision(item.pattern, "never")}
                  >
                    Never
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Logs */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Logs</CardTitle>
            <CardDescription>{logs.length} lines</CardDescription>
          </div>
          {!isTerminal && (
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setAutoScroll(!autoScroll)}
              >
                {autoScroll ? "Auto-scroll ON" : "Auto-scroll OFF"}
              </Button>
              <Button variant="outline" size="sm" onClick={refreshLogs}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
            </div>
          )}
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[480px] rounded-md border bg-muted/50 p-4">
            <pre className="text-xs font-mono whitespace-pre-wrap">
              {logs.map((line, i) => (
                <div
                  key={i}
                  className={
                    line.includes("ERROR") || line.includes("error")
                      ? "text-destructive"
                      : line.includes("WARNING") || line.includes("warning")
                        ? "text-yellow-600 dark:text-yellow-400"
                        : ""
                  }
                >
                  {line}
                </div>
              ))}
              <div ref={logsEndRef} />
            </pre>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
