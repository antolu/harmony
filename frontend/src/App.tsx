import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { Layout } from "@/apps/admin/components/layout/Layout";
import { ChatLayout } from "@/apps/chat/components/layout/ChatLayout";
import { Dashboard } from "@/apps/admin/pages/Dashboard";
import { Chat } from "@/apps/chat/pages/Chat";
import { IndexerConfig } from "@/apps/admin/pages/IndexerConfig";
import { DataSources } from "@/apps/admin/pages/DataSources";
import { DataSourceDetail } from "@/apps/admin/pages/DataSourceDetail";
import { AddDataSourceWizard } from "@/apps/admin/pages/AddDataSourceWizard";
import { Jobs } from "@/apps/admin/pages/Jobs";
import { JobDetail } from "@/apps/admin/pages/JobDetail";
import { Auth } from "@/apps/admin/pages/Auth";
import { Models } from "@/apps/admin/pages/Models";
import { Settings } from "@/apps/admin/pages/Settings";
import { TokenUsage } from "@/apps/admin/pages/TokenUsage";
import { Export } from "@/apps/admin/pages/Export";
import { SetupWizard } from "@/shared/pages/SetupWizard";
import { Users } from "@/apps/admin/pages/Users";
import { Urls } from "@/apps/admin/pages/Urls";
import { AuditLog } from "@/apps/admin/pages/AuditLog";
import { Webhooks } from "@/apps/admin/pages/Webhooks";
import { NotFound } from "@/shared/pages/NotFound";
import { Toaster } from "@/shared/components/ui/toaster";
import { setupApi } from "@/shared/api/setup";
import { api } from "@/shared/api/client";
import { getOidcSettings } from "@/shared/api/auth";
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
          <Route
            path="crawler"
            element={<Navigate to="/admin/data-sources" replace />}
          />
          <Route path="data-sources" element={<DataSources />} />
          <Route path="data-sources/new" element={<AddDataSourceWizard />} />
          <Route path="data-sources/:id" element={<DataSourceDetail />} />
          <Route path="indexer" element={<IndexerConfig />} />
          <Route path="jobs" element={<Jobs />} />
          <Route path="jobs/:jobId" element={<JobDetail />} />
          <Route path="auth" element={<Auth />} />
          <Route path="models" element={<Models />} />
          <Route path="settings" element={<Settings />} />
          <Route path="token-usage" element={<TokenUsage />} />
          <Route path="users" element={<Users />} />
          <Route path="urls" element={<Urls />} />
          <Route path="audit-log" element={<AuditLog />} />
          <Route path="webhooks" element={<Webhooks />} />
          <Route path="export" element={<Export />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
      <Toaster />
    </>
  );
}

export default App;
