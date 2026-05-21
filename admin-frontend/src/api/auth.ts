import { api as _api } from "@/api/client";

const API_BASE = "/api";

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (response.status === 401) {
    sessionStorage.setItem(
      "harmony_redirect_after_login",
      window.location.pathname + window.location.search,
    );
    window.location.href = `/auth/login?redirect=${encodeURIComponent(window.location.pathname)}`;
    throw new Error("Authentication required");
  }

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    const detail = Array.isArray(error.detail)
      ? error.detail
          .map((e: { loc?: string[]; msg?: string }) =>
            [e.loc?.join("."), e.msg].filter(Boolean).join(": "),
          )
          .join("; ")
      : error.detail;
    throw new Error(detail || "Request failed");
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json();
}

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
