import { api as _api, fetchApi } from "@/shared/api/client";

export interface OidcSettings {
  oidcEnabled: boolean;
  issuerUrl: string;
  clientId: string;
  clientSecret: string;
  scopes: string;
}

export async function getOidcSettings(): Promise<OidcSettings> {
  try {
    const data = await fetchApi<{
      oidc_enabled: string;
      oidc_issuer_url: string;
      oidc_client_id: string;
      oidc_scopes: string;
    }>("/settings/oidc");
    return {
      oidcEnabled: data.oidc_enabled === "true",
      issuerUrl: data.oidc_issuer_url ?? "",
      clientId: data.oidc_client_id ?? "",
      clientSecret: "",
      scopes: data.oidc_scopes ?? "openid profile email",
    };
  } catch {
    return {
      oidcEnabled: false,
      issuerUrl: "",
      clientId: "",
      clientSecret: "",
      scopes: "openid profile email",
    };
  }
}

export async function saveOidcSettings(settings: OidcSettings): Promise<void> {
  await fetchApi<void>("/settings/oidc", {
    method: "PATCH",
    body: JSON.stringify({
      oidc_issuer_url: settings.issuerUrl,
      oidc_client_id: settings.clientId,
      oidc_client_secret: settings.clientSecret,
      oidc_scopes: settings.scopes,
      oidc_enabled: String(settings.oidcEnabled),
    }),
  });
}

export async function testOidcConnection(): Promise<{ status: string }> {
  return fetchApi<{ status: string }>("/auth/oidc/test", { method: "POST" });
}

export { _api };
