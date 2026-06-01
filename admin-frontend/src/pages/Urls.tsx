import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const PAGE_SIZE = 50;

export function Urls() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [domainFilter, setDomainFilter] = useState("");
  const [languageFilter, setLanguageFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [criticalError, setCriticalError] = useState<string | null>(null);

  const [blacklistOpen, setBlacklistOpen] = useState(false);
  const [addPatternOpen, setAddPatternOpen] = useState(false);
  const [newPattern, setNewPattern] = useState("");
  const [newReason, setNewReason] = useState("");

  const { data: currentUser } = useQuery({
    queryKey: ["currentUser"],
    queryFn: api.getCurrentUser,
  });

  const { data: domainStats } = useQuery({
    queryKey: ["domainStats"],
    queryFn: api.getDomainStats,
  });

  const urlFilters = {
    domain: domainFilter || undefined,
    language: languageFilter || undefined,
    q: searchQuery || undefined,
    limit: PAGE_SIZE,
    offset,
  };

  const { data: urlsData, isLoading } = useQuery({
    queryKey: ["urls", urlFilters],
    queryFn: () => api.listUrls(urlFilters),
  });

  const { data: blacklistData } = useQuery({
    queryKey: ["blacklist"],
    queryFn: api.listBlacklist,
  });

  const deleteMutation = useMutation({
    mutationFn: (urlId: string) => api.deleteDocument(urlId),
    onSuccess: (result) => {
      const r = result as { status?: string; error?: string; message?: string };
      if (r.status === "deleted") {
        queryClient.invalidateQueries({ queryKey: ["urls"] });
        queryClient.invalidateQueries({ queryKey: ["domainStats"] });
        toast({ title: "Document deleted from ES and Qdrant" });
      } else if (r.error === "ROLLBACK_EXECUTED") {
        toast({
          title: "Qdrant delete failed — ES document restored. No data loss.",
          variant: "destructive",
        });
      } else if (r.error === "CRITICAL") {
        setCriticalError(r.message ?? "Critical error during delete");
      }
    },
    onError: (e) => {
      toast({
        title: "Delete failed",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const addBlacklistMutation = useMutation({
    mutationFn: () => api.addBlacklist(newPattern, newReason || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["blacklist"] });
      toast({ title: "Pattern added to blacklist" });
      setAddPatternOpen(false);
      setNewPattern("");
      setNewReason("");
    },
    onError: (e) => {
      toast({
        title: "Failed to add pattern",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const removeBlacklistMutation = useMutation({
    mutationFn: (patternId: string) => api.removeBlacklist(patternId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["blacklist"] });
      toast({ title: "Pattern removed" });
    },
    onError: (e) => {
      toast({
        title: "Failed to remove pattern",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const isReadOnly = currentUser?.harmony_role === "read-only";
  const urls = urlsData?.urls ?? [];
  const total = urlsData?.total ?? 0;

  if (criticalError) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">URLs</h2>
        </div>
        <Alert variant="destructive">
          <AlertDescription>
            <p className="font-medium">Critical error during document delete</p>
            <p className="text-sm mt-1">{criticalError}</p>
            <div className="mt-3">
              <Button variant="outline" size="sm" asChild>
                <Link to="/admin/audit-log">View Audit Log</Link>
              </Button>
            </div>
          </AlertDescription>
        </Alert>
        <Button variant="ghost" onClick={() => setCriticalError(null)}>
          Dismiss
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">URLs</h2>
        <p className="text-muted-foreground">
          Browse and manage indexed documents.
        </p>
      </div>

      {domainStats && domainStats.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {domainStats.map((stat) => (
            <Card
              key={stat.domain}
              className={`cursor-pointer transition-colors ${domainFilter === stat.domain ? "border-primary" : ""}`}
              onClick={() => {
                setDomainFilter(
                  domainFilter === stat.domain ? "" : stat.domain,
                );
                setOffset(0);
              }}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium truncate">
                  {stat.domain}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{stat.document_count}</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {stat.languages.map((lang) => (
                    <Badge key={lang} variant="secondary" className="text-xs">
                      {lang}
                    </Badge>
                  ))}
                </div>
                {stat.last_crawled_at && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Last crawled:{" "}
                    {new Date(stat.last_crawled_at).toLocaleDateString()}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <Input
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setOffset(0);
          }}
          placeholder="Search URLs..."
          className="w-64"
        />
        <Input
          value={domainFilter}
          onChange={(e) => {
            setDomainFilter(e.target.value);
            setOffset(0);
          }}
          placeholder="Filter by domain"
          className="w-48"
        />
        <Select
          value={languageFilter}
          onValueChange={(v) => {
            setLanguageFilter(v === "all" ? "" : v);
            setOffset(0);
          }}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Language" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All languages</SelectItem>
            {[
              "en",
              "fr",
              "de",
              "es",
              "it",
              "pt",
              "nl",
              "ru",
              "ar",
              "zh",
              "ja",
              "ko",
            ].map((lang) => (
              <SelectItem key={lang} value={lang}>
                {lang}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : urls.length === 0 ? (
        <p className="text-sm text-muted-foreground">No documents found.</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>URL</TableHead>
                <TableHead>Domain</TableHead>
                <TableHead>Language</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Crawled At</TableHead>
                {!isReadOnly && <TableHead />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {urls.map((url) => (
                <TableRow key={url.id}>
                  <TableCell className="font-mono text-xs max-w-xs truncate">
                    <a
                      href={url.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 hover:underline"
                    >
                      {url.url}
                      <ExternalLink className="h-3 w-3 shrink-0" />
                    </a>
                  </TableCell>
                  <TableCell>{url.domain}</TableCell>
                  <TableCell>{url.language ?? "—"}</TableCell>
                  <TableCell className="max-w-xs truncate">
                    {url.title ?? "—"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs">
                    {url.crawled_at
                      ? new Date(url.crawled_at).toLocaleDateString()
                      : "—"}
                  </TableCell>
                  {!isReadOnly && (
                    <TableCell>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive"
                            aria-label={`Delete ${url.url}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>
                              Delete document?
                            </AlertDialogTitle>
                            <AlertDialogDescription>
                              This will remove the document from ES and Qdrant.
                              This cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => deleteMutation.mutate(url.id)}
                            >
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {total > offset + urls.length && (
            <Button
              variant="outline"
              onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
            >
              Load more
            </Button>
          )}
        </>
      )}

      <Collapsible open={blacklistOpen} onOpenChange={setBlacklistOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="outline">
            {blacklistOpen ? "Hide" : "Show"} URL Blacklist
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Blocked Patterns</h3>
            {!isReadOnly && (
              <Dialog open={addPatternOpen} onOpenChange={setAddPatternOpen}>
                <DialogTrigger asChild>
                  <Button size="sm">Block Pattern</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Add Blacklist Pattern</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="pattern">Pattern (regex)</Label>
                      <Input
                        id="pattern"
                        value={newPattern}
                        onChange={(e) => setNewPattern(e.target.value)}
                        placeholder="e.g. /private/.*"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="reason">Reason (optional)</Label>
                      <Textarea
                        id="reason"
                        value={newReason}
                        onChange={(e) => setNewReason(e.target.value)}
                        placeholder="Why is this pattern blocked?"
                      />
                    </div>
                    <Button
                      onClick={() => addBlacklistMutation.mutate()}
                      disabled={!newPattern || addBlacklistMutation.isPending}
                      className="w-full"
                    >
                      {addBlacklistMutation.isPending
                        ? "Adding..."
                        : "Add Pattern"}
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            )}
          </div>

          {!blacklistData?.patterns || blacklistData.patterns.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No patterns blocked.
            </p>
          ) : (
            <div className="space-y-2">
              {blacklistData.patterns.map((pattern) => (
                <div
                  key={pattern.id}
                  className="flex items-start justify-between rounded-lg border p-3"
                >
                  <div className="space-y-1">
                    <p className="font-mono text-sm">{pattern.pattern}</p>
                    {pattern.reason && (
                      <p className="text-xs text-muted-foreground">
                        {pattern.reason}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      Added by {pattern.created_by} on{" "}
                      {new Date(pattern.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  {!isReadOnly && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive shrink-0"
                      onClick={() => removeBlacklistMutation.mutate(pattern.id)}
                      aria-label={`Remove pattern ${pattern.pattern}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
