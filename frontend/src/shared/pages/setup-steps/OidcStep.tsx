import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import { Alert, AlertDescription } from "@/shared/components/ui/alert";
import { Switch } from "@/shared/components/ui/switch";
import { AlertCircle, Loader2 } from "lucide-react";
import { useSetupWizard } from "@/shared/contexts/SetupWizardContext";

export function OidcStep() {
  const {
    step,
    error,
    oidcEnabled,
    setOidcEnabled,
    oidcIssuerUrl,
    setOidcIssuerUrl,
    oidcClientId,
    setOidcClientId,
    oidcClientSecret,
    setOidcClientSecret,
    oidcScopes,
    setOidcScopes,
    submitting,
    setStep,
    handleComplete,
    handleOidcSave,
  } = useSetupWizard();

  return (
    <Card className="w-full max-w-lg">
      <CardHeader>
        <CardTitle>Step {step} of 5 — Single Sign-On</CardTitle>
        <CardDescription>
          Optional. Enable OIDC login for admin access.
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
          <div className="flex items-center gap-3">
            <Switch
              id="wizard-oidc-enabled"
              checked={oidcEnabled}
              onCheckedChange={setOidcEnabled}
            />
            <Label htmlFor="wizard-oidc-enabled">Enable OIDC Login</Label>
          </div>

          <div className="space-y-1">
            <Label>Issuer URL</Label>
            <Input
              placeholder="https://your-idp.example.com/realms/harmony"
              value={oidcIssuerUrl}
              onChange={(e) => setOidcIssuerUrl(e.target.value)}
              disabled={!oidcEnabled}
            />
          </div>

          <div className="space-y-1">
            <Label>Client ID</Label>
            <Input
              placeholder="harmony-admin"
              value={oidcClientId}
              onChange={(e) => setOidcClientId(e.target.value)}
              disabled={!oidcEnabled}
            />
          </div>

          <div className="space-y-1">
            <Label>Client Secret</Label>
            <Input
              type="password"
              placeholder="••••••••"
              value={oidcClientSecret}
              onChange={(e) => setOidcClientSecret(e.target.value)}
              disabled={!oidcEnabled}
            />
          </div>

          <div className="space-y-1">
            <Label>Scopes</Label>
            <Input
              value={oidcScopes}
              onChange={(e) => setOidcScopes(e.target.value)}
              disabled={!oidcEnabled}
            />
            <p className="text-xs text-muted-foreground">
              Space-separated. Must include openid.
            </p>
          </div>
        </div>

        <div className="flex justify-between">
          <Button variant="outline" onClick={() => setStep(4)}>
            Back
          </Button>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={handleComplete}>
              Skip (configure later)
            </Button>
            <Button onClick={handleOidcSave} disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Completing...
                </>
              ) : (
                "Complete Setup"
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
