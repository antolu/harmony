import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Key,
  ExternalLink,
  Trash2,
  CheckCircle,
  XCircle,
  LogIn,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/api/client";

export function Auth() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [vncUrl, setVncUrl] = useState<string | null>(null);
  const [loginProvider, setLoginProvider] = useState<string | null>(null);

  const { data: providers, isLoading: providersLoading } = useQuery({
    queryKey: ["authProviders"],
    queryFn: () => api.listAuthProviders(),
  });

  const { data: sessions, isLoading: sessionsLoading } = useQuery({
    queryKey: ["authSessions"],
    queryFn: () => api.listAuthSessions(),
  });

  const startLoginMutation = useMutation({
    mutationFn: (provider: string) => api.startSSOLogin(provider),
    onSuccess: (data, provider) => {
      setVncUrl(data.vnc_url);
      setLoginProvider(provider);
      toast({ title: "Login session started", description: data.message });
    },
    onError: (error) => {
      toast({
        title: "Login failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const completeLoginMutation = useMutation({
    mutationFn: (provider: string) => api.completeSSOLogin(provider),
    onSuccess: () => {
      toast({ title: "Login completed" });
      setVncUrl(null);
      setLoginProvider(null);
      queryClient.invalidateQueries({ queryKey: ["authProviders"] });
      queryClient.invalidateQueries({ queryKey: ["authSessions"] });
    },
    onError: (error) => {
      toast({
        title: "Complete failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const clearSessionMutation = useMutation({
    mutationFn: (provider: string) => api.clearAuthSession(provider),
    onSuccess: () => {
      toast({ title: "Session cleared" });
      queryClient.invalidateQueries({ queryKey: ["authProviders"] });
      queryClient.invalidateQueries({ queryKey: ["authSessions"] });
    },
    onError: (error) => {
      toast({
        title: "Clear failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  if (providersLoading || sessionsLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">
          Crawler Authentication
        </h2>
        <p className="text-muted-foreground">
          Manage authentication sessions for protected sites
        </p>
      </div>

      {/* Auth Providers */}
      <Card>
        <CardHeader>
          <CardTitle>Configured Providers</CardTitle>
          <CardDescription>
            Authentication providers configured in crawler configs
          </CardDescription>
        </CardHeader>
        <CardContent>
          {providers?.providers.length === 0 ? (
            <p className="text-muted-foreground">
              No auth providers configured. Add authentication settings to a
              crawler config.
            </p>
          ) : (
            <div className="space-y-4">
              {providers?.providers.map((provider) => (
                <div
                  key={provider.name}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Key className="h-4 w-4" />
                      <span className="font-medium">{provider.name}</span>
                      <Badge variant="outline">{provider.type}</Badge>
                      {provider.has_session ? (
                        <Badge variant="success">
                          <CheckCircle className="mr-1 h-3 w-3" />
                          Session Active
                        </Badge>
                      ) : (
                        <Badge variant="secondary">
                          <XCircle className="mr-1 h-3 w-3" />
                          No Session
                        </Badge>
                      )}
                    </div>
                    {provider.domains.length > 0 && (
                      <p className="text-sm text-muted-foreground">
                        Domains: {provider.domains.join(", ")}
                      </p>
                    )}
                  </div>

                  <div className="flex gap-2">
                    {provider.type === "sso" || provider.type === "browser" ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => startLoginMutation.mutate(provider.name)}
                        disabled={startLoginMutation.isPending}
                      >
                        <LogIn className="mr-2 h-4 w-4" />
                        Login via VNC
                      </Button>
                    ) : null}

                    {provider.has_session && (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="destructive" size="sm">
                            <Trash2 className="mr-2 h-4 w-4" />
                            Clear Session
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Clear Session</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to clear the session for "
                              {provider.name}"? You will need to login again.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() =>
                                clearSessionMutation.mutate(provider.name)
                              }
                            >
                              Clear
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Active Sessions */}
      <Card>
        <CardHeader>
          <CardTitle>Active Sessions</CardTitle>
          <CardDescription>
            Currently saved authentication sessions
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sessions?.sessions.length === 0 ? (
            <p className="text-muted-foreground">No active sessions</p>
          ) : (
            <div className="space-y-2">
              {sessions?.sessions.map((session) => (
                <div
                  key={session.provider}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div>
                    <span className="font-medium">{session.provider}</span>
                    <p className="text-sm text-muted-foreground">
                      Created: {new Date(session.created_at).toLocaleString()}
                    </p>
                  </div>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="ghost" size="sm">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Clear Session</AlertDialogTitle>
                        <AlertDialogDescription>
                          Clear session for "{session.provider}"?
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() =>
                            clearSessionMutation.mutate(session.provider)
                          }
                        >
                          Clear
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* VNC Dialog */}
      <Dialog open={!!vncUrl} onOpenChange={(open) => !open && setVncUrl(null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Login via VNC - {loginProvider}</DialogTitle>
            <DialogDescription>
              Complete the login in the browser below. Click "Complete Login"
              when done.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="rounded-lg border bg-muted aspect-video flex items-center justify-center">
              {vncUrl ? (
                <iframe
                  src={vncUrl}
                  className="w-full h-full rounded-lg"
                  title="VNC Browser"
                />
              ) : (
                <p className="text-muted-foreground">VNC viewer loading...</p>
              )}
            </div>

            <div className="flex justify-between">
              <Button variant="outline" asChild>
                <a
                  href={vncUrl || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink className="mr-2 h-4 w-4" />
                  Open in New Tab
                </a>
              </Button>

              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setVncUrl(null)}>
                  Cancel
                </Button>
                <Button
                  onClick={() =>
                    loginProvider && completeLoginMutation.mutate(loginProvider)
                  }
                  disabled={completeLoginMutation.isPending}
                >
                  Complete Login
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
