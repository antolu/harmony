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
  Plus,
  RotateCcw,
  X,
  Calendar,
  Trash2,
} from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import { Progress } from "@/shared/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/shared/components/ui/dialog";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/shared/components/ui/tabs";
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
} from "@/shared/components/ui/alert-dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Checkbox } from "@/shared/components/ui/checkbox";
import { useToast } from "@/shared/hooks/use-toast";
import { api } from "@/shared/api/client";
import type { Job, CrawlerConfigDetail } from "@/shared/api/client";
import { useState, useEffect } from "react";
import { cn } from "@/shared/lib/utils";

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

function formatDuration(start?: string, end?: string, now?: Date): string {
  if (!start) return "-";

  const startDate = new Date(start);
  const endDate = end ? new Date(end) : (now ?? new Date());
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

interface NewJobModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function NewJobModal({ open, onOpenChange }: NewJobModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"crawl" | "index">("crawl");
  const [selectedCrawlerConfig, setSelectedCrawlerConfig] =
    useState<CrawlerConfigDetail | null>(null);

  const { data: crawlerConfigs, isLoading: crawlerLoading } = useQuery({
    queryKey: ["crawlerConfigsDetailed"],
    queryFn: () => api.listCrawlerConfigsDetailed(),
    enabled: open,
  });

  const startMutation = useMutation({
    mutationFn: (jobType: "crawl" | "index" | "re-embed") => {
      const configName =
        tab === "crawl" ? selectedCrawlerConfig!.name : "default";
      return api.startJob({ config_name: configName, job_type: jobType });
    },
    onSuccess: () => {
      toast({ title: "Job started" });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      handleClose();
    },
    onError: (error) => {
      toast({
        title: "Failed to start job",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleClose = () => {
    onOpenChange(false);
    setSelectedCrawlerConfig(null);
    setTab("crawl");
  };

  const canStart = tab === "crawl" ? !!selectedCrawlerConfig : true;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New Job</DialogTitle>
        </DialogHeader>

        <Tabs value={tab} onValueChange={(v) => setTab(v as "crawl" | "index")}>
          <TabsList className="w-full">
            <TabsTrigger value="crawl" className="flex-1">
              Crawl
            </TabsTrigger>
            <TabsTrigger value="index" className="flex-1">
              Index
            </TabsTrigger>
          </TabsList>

          <TabsContent value="crawl" className="mt-4">
            <div className="space-y-2">
              <Label>Crawler config</Label>
              {crawlerLoading ? (
                <div className="text-sm text-muted-foreground">
                  Loading configs...
                </div>
              ) : (
                <div className="border rounded-md divide-y max-h-52 overflow-y-auto">
                  {(crawlerConfigs?.configs.length ?? 0) === 0 && (
                    <div className="p-3 text-sm text-muted-foreground">
                      No configurations found
                    </div>
                  )}
                  {crawlerConfigs?.configs.map((cfg) => {
                    const urls = cfg.config_json.start_urls?.slice(0, 3) ?? [];
                    return (
                      <button
                        key={cfg.name}
                        type="button"
                        onClick={() => setSelectedCrawlerConfig(cfg)}
                        className={cn(
                          "w-full text-left p-3 transition-colors hover:bg-muted/50",
                          selectedCrawlerConfig?.name === cfg.name &&
                            "bg-muted",
                        )}
                      >
                        <div className="font-medium text-sm">{cfg.name}</div>
                        {urls.length > 0 && (
                          <div className="text-xs text-muted-foreground truncate">
                            {urls.join(", ")}
                            {(cfg.config_json.start_urls?.length ?? 0) > 3 &&
                              ` +${(cfg.config_json.start_urls?.length ?? 0) - 3} more`}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="index" className="mt-4">
            <div className="border rounded-md p-3 text-sm text-muted-foreground">
              Will use the current indexer configuration. To change settings,
              visit the{" "}
              <a href="/admin/indexer" className="underline">
                Indexer Config
              </a>{" "}
              page.
            </div>
          </TabsContent>
        </Tabs>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          {tab === "index" && (
            <Button
              variant="outline"
              onClick={() => startMutation.mutate("re-embed")}
              disabled={startMutation.isPending}
            >
              {startMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Re-embed
            </Button>
          )}
          <Button
            onClick={() => startMutation.mutate(tab)}
            disabled={!canStart || startMutation.isPending}
          >
            {startMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            Start
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface AddScheduleModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function AddScheduleModal({ open, onOpenChange }: AddScheduleModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedConfig, setSelectedConfig] =
    useState<CrawlerConfigDetail | null>(null);
  const [cron, setCron] = useState("");

  const { data: configsData, isLoading: configsLoading } = useQuery({
    queryKey: ["crawlerConfigsDetailed"],
    queryFn: () => api.listCrawlerConfigsDetailed(),
    enabled: open,
  });

  const createMutation = useMutation({
    mutationFn: () => api.createSchedule(selectedConfig!.name, cron.trim()),
    onSuccess: () => {
      toast({ title: "Schedule created" });
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      onOpenChange(false);
      setSelectedConfig(null);
      setCron("");
    },
    onError: (error) => {
      toast({
        title: "Failed to create schedule",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleClose = () => {
    onOpenChange(false);
    setSelectedConfig(null);
    setCron("");
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Schedule</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Configuration</Label>
            {configsLoading ? (
              <div className="text-sm text-muted-foreground">
                Loading configs...
              </div>
            ) : (
              <div className="border rounded-md divide-y max-h-40 overflow-y-auto">
                {configsData?.configs.map((cfg) => (
                  <button
                    key={cfg.name}
                    type="button"
                    onClick={() => setSelectedConfig(cfg)}
                    className={cn(
                      "w-full text-left p-3 transition-colors hover:bg-muted/50",
                      selectedConfig?.name === cfg.name && "bg-muted",
                    )}
                  >
                    <div className="font-medium text-sm">{cfg.name}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label>Cron Expression</Label>
            <Input
              value={cron}
              onChange={(e) => setCron(e.target.value)}
              placeholder="0 2 * * *"
            />
            <p className="text-xs text-muted-foreground">
              Example: <code>0 2 * * *</code> runs daily at 2am
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            onClick={() => createMutation.mutate()}
            disabled={
              !selectedConfig || !cron.trim() || createMutation.isPending
            }
          >
            {createMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            Create Schedule
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function Jobs() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [newJobOpen, setNewJobOpen] = useState(false);
  const [forceStop, setForceStop] = useState(false);
  const [addScheduleOpen, setAddScheduleOpen] = useState(false);

  const { data: jobs } = useQuery({
    queryKey: ["jobs", typeFilter, statusFilter],
    queryFn: () =>
      api.listJobs(
        typeFilter !== "all" ? typeFilter : undefined,
        statusFilter !== "all" ? statusFilter : undefined,
      ),
    refetchInterval: 3000,
  });

  const { data: schedules } = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api.listSchedules(),
  });

  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const hasRunning = jobs?.some((j) => j.status === "running");
    if (!hasRunning) return;
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, [jobs]);

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

  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => api.cancelJob(jobId),
    onSuccess: () => {
      toast({ title: "Job cancelled" });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error) => {
      toast({
        title: "Cancel failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const rerunMutation = useMutation({
    mutationFn: (jobId: string) => api.retriggerJob(jobId),
    onSuccess: () => {
      toast({ title: "Job re-triggered" });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error) => {
      toast({
        title: "Re-run failed",
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

  const deleteScheduleMutation = useMutation({
    mutationFn: (configName: string) => api.deleteSchedule(configName),
    onSuccess: () => {
      toast({ title: "Schedule deleted" });
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
    onError: (error) => {
      toast({
        title: "Delete failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const isTerminal = (status: Job["status"]) =>
    ["completed", "failed", "stopped"].includes(status);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Jobs</h2>
          <p className="text-muted-foreground">
            View and manage crawl and index jobs
          </p>
        </div>
        <Button onClick={() => setNewJobOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Job
        </Button>
      </div>

      <NewJobModal open={newJobOpen} onOpenChange={setNewJobOpen} />
      <AddScheduleModal
        open={addScheduleOpen}
        onOpenChange={setAddScheduleOpen}
      />

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
              No jobs found. Use "New Job" to start a crawl or index job.
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
                        ? new Date(job.started_at).toLocaleString(undefined, {
                            dateStyle: "medium",
                            timeStyle: "short",
                          })
                        : "-"}
                    </span>
                    <span>
                      Duration:{" "}
                      {formatDuration(
                        job.started_at,
                        job.finished_at,
                        job.status === "running" ? now : undefined,
                      )}
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
                      <AlertDialog onOpenChange={() => setForceStop(false)}>
                        <AlertDialogTrigger asChild>
                          <Button variant="destructive" size="sm">
                            <X className="mr-1 h-4 w-4" />
                            Cancel
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Cancel job?</AlertDialogTitle>
                            <AlertDialogDescription>
                              The job will be stopped. Progress so far is saved
                              and can be resumed.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <div className="flex items-center gap-2 px-1 py-2">
                            <Checkbox
                              id="force-stop"
                              checked={forceStop}
                              onCheckedChange={(v) => setForceStop(!!v)}
                            />
                            <Label
                              htmlFor="force-stop"
                              className="text-sm font-normal"
                            >
                              Force quit (discard progress, cannot be resumed)
                            </Label>
                          </div>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Keep running</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() =>
                                forceStop
                                  ? stopMutation.mutate(job.id)
                                  : cancelMutation.mutate(job.id)
                              }
                            >
                              {forceStop ? "Force quit" : "Cancel job"}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
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

                  {isTerminal(job.status) && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => rerunMutation.mutate(job.id)}
                      disabled={rerunMutation.isPending}
                    >
                      <RotateCcw className="mr-1 h-4 w-4" />
                      Re-run
                    </Button>
                  )}

                  <Button variant="ghost" size="sm" asChild>
                    <Link to={`/admin/jobs/${job.id}`}>View Details</Link>
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Schedules */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Schedules
          </CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAddScheduleOpen(true)}
          >
            <Plus className="mr-2 h-4 w-4" />
            Add Schedule
          </Button>
        </CardHeader>
        <CardContent>
          {!schedules || schedules.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No schedules configured. Add a schedule to run jobs automatically.
            </p>
          ) : (
            <div className="rounded-md border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium">
                      Config Name
                    </th>
                    <th className="px-4 py-3 text-left font-medium">Cron</th>
                    <th className="px-4 py-3 text-left font-medium">
                      Next Run
                    </th>
                    <th className="px-4 py-3 text-right font-medium">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((schedule) => (
                    <tr key={schedule.id} className="border-b last:border-0">
                      <td className="px-4 py-3 font-medium">{schedule.name}</td>
                      <td className="px-4 py-3 font-mono text-xs">
                        {schedule.cron}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {schedule.next_run_time
                          ? new Date(schedule.next_run_time).toLocaleString(
                              undefined,
                              { dateStyle: "medium", timeStyle: "short" },
                            )
                          : "-"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="sm">
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>
                                Delete schedule?
                              </AlertDialogTitle>
                              <AlertDialogDescription>
                                The schedule for "{schedule.name}" will be
                                removed. This cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() =>
                                  deleteScheduleMutation.mutate(
                                    schedule.config_name,
                                  )
                                }
                              >
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
