import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { Layout } from "@/components/layout/Layout";
import { Dashboard } from "@/pages/Dashboard";
import { CrawlerConfig } from "@/pages/CrawlerConfig";
import { IndexerConfig } from "@/pages/IndexerConfig";
import { Jobs } from "@/pages/Jobs";
import { JobDetail } from "@/pages/JobDetail";
import { Auth } from "@/pages/Auth";
import { Models } from "@/pages/Models";
import { Settings } from "@/pages/Settings";
import { SetupWizard } from "@/pages/SetupWizard";
import { Toaster } from "@/components/ui/toaster";
import { setupApi } from "@/api/setup";
import { Loader2 } from "lucide-react";

function App() {
  const [isConfigured, setIsConfigured] = useState<boolean | null>(null);
  const location = useLocation();

  useEffect(() => {
    checkSetup();
  }, []);

  const checkSetup = async () => {
    try {
      const status = await setupApi.getStatus();
      setIsConfigured(status.is_configured);
    } catch {
      setIsConfigured(null);
    }
  };

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

  return (
    <>
      <Routes>
        <Route path="/setup" element={<SetupWizard />} />
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="crawler" element={<CrawlerConfig />} />
          <Route path="indexer" element={<IndexerConfig />} />
          <Route path="jobs" element={<Jobs />} />
          <Route path="jobs/:jobId" element={<JobDetail />} />
          <Route path="auth" element={<Auth />} />
          <Route path="models" element={<Models />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
      <Toaster />
    </>
  );
}

export default App;
