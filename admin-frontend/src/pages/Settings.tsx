import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, AlertTriangle, Database, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { api } from "@/api/client";

export function Settings() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: indexStatus } = useQuery({
    queryKey: ["indexStatus"],
    queryFn: () => api.getIndexStatus(),
  });

  const resetStateMutation = useMutation({
    mutationFn: () => api.resetCrawlState(),
    onSuccess: (data) => {
      toast({
        title: "Crawl state reset",
        description: data.message,
      });
      queryClient.invalidateQueries({ queryKey: ["indexStatus"] });
    },
    onError: (error) => {
      toast({
        title: "Reset failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const resetSearchMutation = useMutation({
    mutationFn: () => api.resetSearchIndices(),
    onSuccess: (data) => {
      toast({
        title: "Search indices reset",
        description: data.message,
      });
      queryClient.invalidateQueries({ queryKey: ["indexStatus"] });
    },
    onError: (error) => {
      toast({
        title: "Reset failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const stateIndex = indexStatus?.indices.find((i) => i.type === "state");
  const searchIndices =
    indexStatus?.indices.filter((i) => i.type === "search") || [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground">
          System settings and reset operations
        </p>
      </div>

      {/* Index Status */}
      <Card>
        <CardHeader>
          <CardTitle>Elasticsearch Indices</CardTitle>
          <CardDescription>
            Current index status and document counts
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* State Index */}
            <div className="rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Globe className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="font-medium">Crawl State Index</p>
                    <p className="text-sm text-muted-foreground">
                      {stateIndex?.name || "Not created"}
                    </p>
                  </div>
                </div>
                <Badge variant="secondary">
                  {stateIndex?.doc_count || 0} URLs
                </Badge>
              </div>
            </div>

            {/* Search Indices */}
            <div className="rounded-lg border p-4">
              <div className="flex items-center gap-3 mb-4">
                <Database className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="font-medium">Search Indices</p>
                  <p className="text-sm text-muted-foreground">
                    Per-language document indices
                  </p>
                </div>
              </div>

              {searchIndices.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No search indices created
                </p>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {searchIndices.map((index) => (
                    <div key={index.name} className="rounded border p-2">
                      <p className="font-medium">
                        {index.language?.toUpperCase()}
                      </p>
                      <p className="text-lg font-bold">{index.doc_count}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {index.name}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Reset Operations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Danger Zone
          </CardTitle>
          <CardDescription>
            Irreversible actions that delete data
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Reset Crawl State */}
          <div className="flex items-center justify-between rounded-lg border border-destructive/50 p-4">
            <div>
              <p className="font-medium">Reset Crawl State</p>
              <p className="text-sm text-muted-foreground">
                Delete the crawl state index. URLs will need to be re-crawled.
                {stateIndex && ` (${stateIndex.doc_count} URLs)`}
              </p>
            </div>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Reset State
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Reset Crawl State</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will delete the crawl state index containing{" "}
                    <strong>{stateIndex?.doc_count || 0}</strong> tracked URLs.
                    <br />
                    <br />
                    The crawler will treat all URLs as new and re-crawl
                    everything. This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() => resetStateMutation.mutate()}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    Delete State Index
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>

          {/* Reset Search Indices */}
          <div className="flex items-center justify-between rounded-lg border border-destructive/50 p-4">
            <div>
              <p className="font-medium">Reset Search Indices</p>
              <p className="text-sm text-muted-foreground">
                Delete all search indices. You will need to re-index after
                crawling.
                {searchIndices.length > 0 && (
                  <>
                    {" "}
                    ({searchIndices.reduce(
                      (sum, i) => sum + i.doc_count,
                      0,
                    )}{" "}
                    documents in {searchIndices.length} indices)
                  </>
                )}
              </p>
            </div>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Reset Indices
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Reset Search Indices</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will delete <strong>{searchIndices.length}</strong>{" "}
                    search indices containing{" "}
                    <strong>
                      {searchIndices.reduce((sum, i) => sum + i.doc_count, 0)}
                    </strong>{" "}
                    documents.
                    <br />
                    <br />
                    Search will not work until you run the indexer again. This
                    action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() => resetSearchMutation.mutate()}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    Delete Search Indices
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
