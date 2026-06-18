import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Key,
  ExternalLink,
  Trash2,
  CheckCircle,
  XCircle,
  LogIn,
  Loader2,
} from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
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
import { useToast } from "@/shared/hooks/use-toast";
import { api } from "@/shared/api/client";

export function Auth() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [pendingProvider, setPendingProvider] = useState<string | null>(null);
  const [popupBlockedUrl, setPopupBlockedUrl] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { data: providers } = useQuery({
    queryKey: ["authProviders"],
    queryFn: () => api.listAuthProviders(),
  });

  const { data: sessions } = useQuery({
    queryKey: ["authSessions"],
    queryFn: () => api.listAuthSessions(),
  });

  const startLoginMutation = useMutation({
    mutationFn: (provider: string) => api.startLogin(provider),
    onSuccess: (data, provider) => {
      if (data.flow === "client_credentials") {
        toast({ title: "Connected", description: data.message });
        queryClient.invalidateQueries({ queryKey: ["authProviders"] });
        queryClient.invalidateQueries({ queryKey: ["authSessions"] });
        return;
      }

      if (data.auth_url) {
        const popup = window.open(
          data.auth_url,
          "_blank",
          "width=600,height=700",
        );
        if (!popup) {
          setPopupBlockedUrl(data.auth_url);
          toast({
            title: "Popup blocked",
            description: "Allow popups for this site or use the link below.",
            variant: "destructive",
          });
        }
      }
      setPendingProvider(provider);
    },
    onError: (error) => {
      toast({
        title: "Login failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const testConnectionMutation = useMutation({
    mutationFn: (provider: string) => api.testProviderConnection(provider),
    onSuccess: (data) => {
      toast({
        title: data.success ? "Connection successful" : "Connection failed",
        description: data.message,
        variant: data.success ? "default" : "destructive",
      });
    },
    onError: (error) => {
      toast({
        title: "Test failed",
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

  useEffect(() => {
    if (!pendingProvider) return;
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.getLoginStatus(pendingProvider);
        if (status.complete) {
          setPendingProvider(null);
          setPopupBlockedUrl(null);
          if (pollRef.current) clearInterval(pollRef.current);
          toast({ title: "Login complete" });
          queryClient.invalidateQueries({ queryKey: ["authProviders"] });
          queryClient.invalidateQueries({ queryKey: ["authSessions"] });
        }
      } catch {
        // ignore transient errors during polling
      }
    }, 2000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [pendingProvider, queryClient, toast]);

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
                      {pendingProvider === provider.name && (
                        <Badge variant="secondary">
                          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          Waiting for login...
                        </Badge>
                      )}
                    </div>
                    {provider.domains.length > 0 && (
                      <p className="text-sm text-muted-foreground">
                        Domains: {provider.domains.join(", ")}
                      </p>
                    )}
                    {popupBlockedUrl && pendingProvider === provider.name && (
                      <a
                        href={popupBlockedUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-blue-500 underline flex items-center gap-1"
                      >
                        <ExternalLink className="h-3 w-3" />
                        Click here to open login
                      </a>
                    )}
                  </div>

                  <div className="flex gap-2">
                    {provider.type === "oidc" && (
                      <>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() =>
                            testConnectionMutation.mutate(provider.name)
                          }
                          disabled={
                            testConnectionMutation.isPending &&
                            testConnectionMutation.variables === provider.name
                          }
                        >
                          {testConnectionMutation.isPending &&
                          testConnectionMutation.variables === provider.name ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : null}
                          Test
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            startLoginMutation.mutate(provider.name)
                          }
                          disabled={
                            startLoginMutation.isPending ||
                            pendingProvider === provider.name
                          }
                        >
                          <LogIn className="mr-2 h-4 w-4" />
                          {pendingProvider === provider.name
                            ? "Waiting..."
                            : provider.flow === "client_credentials"
                              ? "Connect"
                              : "Login"}
                        </Button>
                      </>
                    )}

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
                              Clear the session for "{provider.name}"? You will
                              need to login again.
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
    </div>
  );
}
