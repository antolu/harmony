import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { Layout } from "@/components/layout/Layout";
import { ChatLayout } from "@/components/layout/ChatLayout";
import { Dashboard } from "@/pages/Dashboard";
import { Chat } from "@/pages/Chat";
import { CrawlerConfig } from "@/pages/CrawlerConfig";
import { IndexerConfig } from "@/pages/IndexerConfig";
import { Jobs } from "@/pages/Jobs";
import { JobDetail } from "@/pages/JobDetail";
import { Auth } from "@/pages/Auth";
import { Models } from "@/pages/Models";
import { Settings } from "@/pages/Settings";
import { TokenUsage } from "@/pages/TokenUsage";
import { SetupWizard } from "@/pages/SetupWizard";
import { Toaster } from "@/components/ui/toaster";
import { setupApi } from "@/api/setup";
import { api } from "@/api/client";
import { getOidcSettings } from "@/api/auth";
import { Loader2, ServerCrash } from "lucide-react";

function App() {
  const [isConfigured, setIsConfigured] = useState<boolean | null>(null);
  const [backendDown, setBackendDown] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const location = useLocation();

  useEffect(() => {
    checkSetup();
  }, []);

  const checkSetup = async () => {
    try {
      const [status, oidc, user] = await Promise.all([
        setupApi.getStatus(),
        getOidcSettings(),
        api.getCurrentUser(),
      ]);
      setIsConfigured(status.is_configured);
      const hasOidc = !!(oidc.issuerUrl && oidc.clientId);
      setIsAuthenticated(!hasOidc || user.id !== "anonymous");
      setBackendDown(false);
    } catch {
      setBackendDown(true);
      setIsConfigured(null);
      setIsAuthenticated(null);
    }
  };

  if (backendDown) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 text-muted-foreground">
        <ServerCrash className="h-12 w-12" />
        <p className="text-lg font-medium">Backend unreachable</p>
        <p className="text-sm">Make sure the API is running and try again.</p>
        <button
          className="mt-2 text-sm underline"
          onClick={() => {
            setBackendDown(false);
            checkSetup();
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (isConfigured === null) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isConfigured && location.pathname !== "/setup") {
    return <Navigate to="/setup" replace />;
  }

  if (isConfigured && location.pathname === "/setup") {
    return <Navigate to="/" replace />;
  }

  if (isAuthenticated === false && location.pathname.startsWith("/admin")) {
    window.location.href = `/api/auth/login?redirect=${encodeURIComponent(location.pathname)}`;
    return null;
  }

  return (
    <>
      <Routes>
        <Route path="/setup" element={<SetupWizard />} />
        <Route path="/" element={<ChatLayout />}>
          <Route index element={<Chat />} />
          <Route path="c/:conversationId" element={<Chat />} />
        </Route>
        <Route path="/admin" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="crawler" element={<CrawlerConfig />} />
          <Route path="indexer" element={<IndexerConfig />} />
          <Route path="jobs" element={<Jobs />} />
          <Route path="jobs/:jobId" element={<JobDetail />} />
          <Route path="auth" element={<Auth />} />
          <Route path="models" element={<Models />} />
          <Route path="settings" element={<Settings />} />
          <Route path="token-usage" element={<TokenUsage />} />
        </Route>
      </Routes>
      <Toaster />
    </>
  );
}

export default App;
