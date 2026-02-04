import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { setupApi, type SetupStatus } from "@/api/setup";
import { CheckCircle2, XCircle, Loader2, AlertCircle } from "lucide-react";

export function SetupWizard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);

  const [elasticsearchUrl, setElasticsearchUrl] = useState(
    "http://elasticsearch:9200",
  );
  const [redisUrl, setRedisUrl] = useState("redis://redis:6379/0");

  const [validating, setValidating] = useState(false);
  const [esValidation, setEsValidation] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [redisValidation, setRedisValidation] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    checkSetupStatus();
  }, []);

  const checkSetupStatus = async () => {
    try {
      const status = await setupApi.getStatus();
      setSetupStatus(status);

      if (status.is_configured) {
        navigate("/");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to check setup status",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async () => {
    setValidating(true);
    setEsValidation(null);
    setRedisValidation(null);
    setError(null);

    try {
      const result = await setupApi.validate({
        elasticsearch_url: elasticsearchUrl,
        redis_url: redisUrl,
      });

      if (result.elasticsearch) {
        setEsValidation(result.elasticsearch);
      }
      if (result.redis) {
        setRedisValidation(result.redis);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setValidating(false);
    }
  };

  const handleComplete = async () => {
    if (!esValidation?.ok || !redisValidation?.ok) {
      setError("Please validate both services before completing setup");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await setupApi.complete({
        elasticsearch_url: elasticsearchUrl,
        redis_url: redisUrl,
      });

      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup completion failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/20 flex items-center justify-center p-4">
      <Card className="max-w-2xl w-full">
        <CardHeader>
          <CardTitle className="text-3xl">Welcome to Harmony</CardTitle>
          <CardDescription>
            Configure your Elasticsearch and Redis connections to get started
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="elasticsearch-url">Elasticsearch URL</Label>
              <Input
                id="elasticsearch-url"
                value={elasticsearchUrl}
                onChange={(e) => setElasticsearchUrl(e.target.value)}
                placeholder="http://elasticsearch:9200"
                disabled={validating || submitting}
              />
              {esValidation && (
                <div className="flex items-center gap-2 text-sm">
                  {esValidation.ok ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span className="text-green-600">
                        {esValidation.message}
                      </span>
                    </>
                  ) : (
                    <>
                      <XCircle className="h-4 w-4 text-red-500" />
                      <span className="text-red-600">
                        {esValidation.message}
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="redis-url">Redis URL</Label>
              <Input
                id="redis-url"
                value={redisUrl}
                onChange={(e) => setRedisUrl(e.target.value)}
                placeholder="redis://redis:6379/0"
                disabled={validating || submitting}
              />
              {redisValidation && (
                <div className="flex items-center gap-2 text-sm">
                  {redisValidation.ok ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span className="text-green-600">
                        {redisValidation.message}
                      </span>
                    </>
                  ) : (
                    <>
                      <XCircle className="h-4 w-4 text-red-500" />
                      <span className="text-red-600">
                        {redisValidation.message}
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="flex gap-3 pt-4">
            <Button
              onClick={handleValidate}
              disabled={
                validating || submitting || !elasticsearchUrl || !redisUrl
              }
              variant="outline"
              className="flex-1"
            >
              {validating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Validating...
                </>
              ) : (
                "Test Connections"
              )}
            </Button>

            <Button
              onClick={handleComplete}
              disabled={submitting || !esValidation?.ok || !redisValidation?.ok}
              className="flex-1"
            >
              {submitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Completing Setup...
                </>
              ) : (
                "Complete Setup"
              )}
            </Button>
          </div>

          <Alert>
            <AlertDescription className="text-sm text-muted-foreground">
              <strong>Note:</strong> These values can be overridden with
              environment variables (ES_HOST, REDIS_URL). Configuration is
              stored in PostgreSQL for persistence.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    </div>
  );
}
