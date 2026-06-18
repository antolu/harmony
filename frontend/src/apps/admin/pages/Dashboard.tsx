import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Globe,
  Database,
  Play,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  Activity,
} from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import { Badge } from "@/shared/components/ui/badge";
import { api } from "@/shared/api/client";
import type { Job, ReadinessStatus } from "@/shared/api/client";

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
      return <Badge variant="warning">Paused</Badge>;
    case "stopped":
      return <Badge variant="secondary">Stopped</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export function Dashboard() {
  const { data: jobs } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.listJobs(),
    refetchInterval: 5000,
  });

  const { data: indexStatus } = useQuery({
    queryKey: ["indexStatus"],
    queryFn: () => api.getIndexStatus(),
  });

  const { data: crawlerConfigs } = useQuery({
    queryKey: ["crawlerConfigs"],
    queryFn: () => api.listCrawlerConfigs(),
  });

  const { data: indexerConfigs } = useQuery({
    queryKey: ["indexerConfigs"],
    queryFn: () => api.listIndexerConfigs(),
  });

  const { data: readiness, isLoading: readinessLoading } =
    useQuery<ReadinessStatus>({
      queryKey: ["readiness"],
      queryFn: () => api.getReadiness(),
      refetchInterval: 30000,
    });

  const runningJobs = jobs?.filter((j) => j.status === "running") || [];

  const failingDeps = readiness
    ? Object.entries(readiness.dependencies)
        .filter(([, v]) => v !== true && v !== "disabled")
        .map(([k]) => k)
    : [];
  const recentJobs = jobs?.slice(0, 5) || [];

  const stateIndex = indexStatus?.indices.find((i) => i.type === "state");
  const searchIndices =
    indexStatus?.indices.filter((i) => i.type === "search") || [];
  const totalDocs = searchIndices.reduce((sum, i) => sum + i.doc_count, 0);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground">
          Overview of your Harmony crawling system
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Running Jobs</CardTitle>
            <Loader2
              className={`h-4 w-4 text-muted-foreground ${runningJobs.length > 0 ? "animate-spin" : ""}`}
            />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{runningJobs.length}</div>
            <p className="text-xs text-muted-foreground">
              {jobs?.length || 0} total jobs
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Crawl State</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stateIndex?.doc_count || 0}
            </div>
            <p className="text-xs text-muted-foreground">URLs tracked</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Search Index</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalDocs}</div>
            <p className="text-xs text-muted-foreground">
              {searchIndices.length} language(s)
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Configurations
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(crawlerConfigs?.configs?.length || 0) +
                (indexerConfigs?.configs?.length || 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              {crawlerConfigs?.configs?.length || 0} crawler,{" "}
              {indexerConfigs?.configs?.length || 0} indexer
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              System Readiness
            </CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {readinessLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : failingDeps.length === 0 ? (
              <Badge variant="success">All systems ready</Badge>
            ) : (
              <div className="flex flex-wrap gap-1">
                {failingDeps.map((dep) => (
                  <Badge key={dep} variant="destructive">
                    {dep} unavailable
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Common operations</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-4">
          <Button asChild>
            <Link to="/admin/crawler">
              <Globe className="mr-2 h-4 w-4" />
              Configure Crawl
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/admin/indexer">
              <Database className="mr-2 h-4 w-4" />
              Configure Index
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/admin/jobs">
              <Play className="mr-2 h-4 w-4" />
              View Jobs
            </Link>
          </Button>
        </CardContent>
      </Card>

      {/* Recent Jobs */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Jobs</CardTitle>
          <CardDescription>Last 5 jobs</CardDescription>
        </CardHeader>
        <CardContent>
          {recentJobs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No jobs yet</p>
          ) : (
            <div className="space-y-4">
              {recentJobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      {job.type === "crawl" ? (
                        <Globe className="h-4 w-4" />
                      ) : (
                        <Database className="h-4 w-4" />
                      )}
                      <span className="font-medium">{job.config_name}</span>
                      {getStatusBadge(job.status)}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {job.started_at
                        ? new Date(job.started_at).toLocaleString()
                        : "Not started"}
                    </p>
                  </div>
                  <Button asChild variant="ghost" size="sm">
                    <Link to={`/admin/jobs/${job.id}`}>View</Link>
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Index Details */}
      {searchIndices.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Search Indices</CardTitle>
            <CardDescription>Per-language document counts</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 md:grid-cols-3 lg:grid-cols-4">
              {searchIndices.map((index) => (
                <div key={index.name} className="rounded-lg border p-3">
                  <div className="text-sm font-medium">
                    {index.language?.toUpperCase() || "unknown"}
                  </div>
                  <div className="text-2xl font-bold">{index.doc_count}</div>
                  <div className="text-xs text-muted-foreground">
                    {index.name}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
