import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
import { api, type DataSourceRecord } from "@/api/client";

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

export function DataSources() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data, isError } = useQuery({
    queryKey: ["dataSources"],
    queryFn: () => api.listDataSources(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteDataSource(id),
    onSuccess: () => {
      toast({ title: "Data source deleted" });
      queryClient.invalidateQueries({ queryKey: ["dataSources"] });
    },
    onError: () => {
      toast({
        title: "Delete failed. The data source may be in use by a running job.",
        variant: "destructive",
      });
      queryClient.invalidateQueries({ queryKey: ["dataSources"] });
    },
  });

  const sources = data?.sources ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Data Sources</h1>
        <Button onClick={() => navigate("/admin/data-sources/new")}>
          Add Data Source
        </Button>
      </div>

      {isError && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Could not load data sources. Check your network connection and try
            again.
          </CardContent>
        </Card>
      )}

      {!isError && sources.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center space-y-3">
            <h2 className="text-lg font-semibold">No data sources yet</h2>
            <p className="text-sm text-muted-foreground">
              Add your first data source to start indexing content. Choose a
              provider type to get started.
            </p>
            <Button onClick={() => navigate("/admin/data-sources/new")}>
              Add Data Source
            </Button>
          </CardContent>
        </Card>
      )}

      {!isError && sources.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Last run</TableHead>
              <TableHead>Document count</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sources.map((source: DataSourceRecord) => (
              <TableRow key={source.id}>
                <TableCell>{source.name}</TableCell>
                <TableCell>
                  <Badge variant="outline">{source.provider_type}</Badge>
                </TableCell>
                <TableCell>
                  <Badge className={statusBadgeClass(source.last_run_status)}>
                    {statusLabel(source.last_run_status)}
                  </Badge>
                </TableCell>
                <TableCell>
                  {source.last_run_at
                    ? new Date(source.last_run_at).toLocaleString()
                    : "—"}
                </TableCell>
                <TableCell>{source.last_run_doc_count ?? "—"}</TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Edit ${source.name}`}
                      onClick={() =>
                        navigate(`/admin/data-sources/${source.id}`)
                      }
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={`Delete ${source.name}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>
                            Delete data source?
                          </AlertDialogTitle>
                          <AlertDialogDescription>
                            This will permanently remove &quot;{source.name}
                            &quot; and its configuration. Indexed documents are
                            not deleted — use the URLs page to remove them.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            onClick={() => deleteMutation.mutate(source.id)}
                          >
                            Delete Source
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
