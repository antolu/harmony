import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Switch } from "@/shared/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { TagInput } from "emblor-maintained";

interface AuthProvider {
  type: string;
  domains: string[];
  [key: string]: unknown;
}

interface AuthProviderFormProps {
  providers: AuthProvider[];
  onChange: (providers: AuthProvider[]) => void;
}

const PROVIDER_TYPES = [
  { value: "static_cookie", label: "Static Cookie" },
  { value: "basic", label: "Basic Auth" },
  { value: "bearer", label: "Bearer Token" },
  { value: "service_account", label: "Service Account (OAuth2)" },
  { value: "playwright_sso", label: "Playwright SSO" },
];

function getProviderDefaults(type: string): AuthProvider {
  const base: AuthProvider = { type, domains: [] };
  switch (type) {
    case "static_cookie":
      return { ...base, cookies: {}, cookie_file: null };
    case "basic":
      return { ...base, username: "", password: "" };
    case "bearer":
      return {
        ...base,
        token: "",
        header_name: "Authorization",
        header_prefix: "Bearer",
      };
    case "service_account":
      return {
        ...base,
        client_id: "",
        client_secret: "",
        token_url: "",
        scope: null,
        token_expiry_buffer_seconds: 60,
      };
    case "playwright_sso":
      return {
        ...base,
        name: "",
        login_url: null,
        storage_state_file: null,
        success_url_pattern: null,
        login_complete_marker: null,
        authenticated_markers: [],
        login_required_markers: [],
        auth_domain_patterns: [],
        headless: false,
        browser_type: "chromium",
        timeout_seconds: 300,
      };
    default:
      return base;
  }
}

function SemanticAuthFields({
  provider,
  onChange,
}: {
  provider: AuthProvider;
  onChange: (provider: AuthProvider) => void;
}) {
  return (
    <div className="border-t pt-3 mt-3 space-y-3">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        Semantic Auth Detection
      </p>
      <div className="flex items-center justify-between">
        <div>
          <Label>Enable semantic detection</Label>
          <p className="text-xs text-muted-foreground">
            Use LLM to detect auth failure pages
          </p>
        </div>
        <Switch
          checked={(provider.semantic_auth_detection as boolean) || false}
          onCheckedChange={(v) =>
            onChange({ ...provider, semantic_auth_detection: v })
          }
        />
      </div>
      {(provider.semantic_auth_detection as boolean) && (
        <>
          <div className="space-y-1">
            <Label>Semantic auth model</Label>
            <Input
              value={(provider.semantic_auth_model as string) || ""}
              onChange={(e) =>
                onChange({ ...provider, semantic_auth_model: e.target.value })
              }
              placeholder="ollama_chat/qwen3:4b-instruct-2507-q4_K_M"
            />
          </div>
          <div className="space-y-1">
            <Label>Max check length</Label>
            <Input
              type="number"
              value={
                (provider.max_semantic_check_length as number) !== undefined
                  ? (provider.max_semantic_check_length as number)
                  : 500
              }
              onChange={(e) =>
                onChange({
                  ...provider,
                  max_semantic_check_length: parseInt(e.target.value),
                })
              }
            />
          </div>
        </>
      )}
    </div>
  );
}

function TagInputField({
  label,
  description,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  description?: string;
  value: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
}) {
  const [activeTagIndex, setActiveTagIndex] = useState<number | null>(null);
  const tags = value.map((item, index) => ({ id: `${index}`, text: item }));
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      <TagInput
        tags={tags}
        setTags={(newTags) => {
          const values = Array.isArray(newTags)
            ? newTags.map((tag) => (typeof tag === "string" ? tag : tag.text))
            : [];
          onChange(values);
        }}
        placeholder={placeholder || "Type and press Enter..."}
        activeTagIndex={activeTagIndex}
        setActiveTagIndex={setActiveTagIndex}
        delimiterList={[" ", ","]}
        addOnPaste
        styleClasses={{ input: "h-9", tag: { body: "pl-2 pr-1" } }}
        className="border rounded-md"
      />
    </div>
  );
}

function ProviderFields({
  provider,
  onChange,
}: {
  provider: AuthProvider;
  onChange: (provider: AuthProvider) => void;
}) {
  switch (provider.type) {
    case "static_cookie":
      return (
        <div className="space-y-3">
          <TagInputField
            label="Domains"
            description="Regex patterns for domains this provider handles"
            value={provider.domains}
            onChange={(v) => onChange({ ...provider, domains: v })}
            placeholder="e.g. example\\.com"
          />
          <div className="space-y-1">
            <Label>Cookie file path</Label>
            <Input
              value={(provider.cookie_file as string) || ""}
              onChange={(e) =>
                onChange({
                  ...provider,
                  cookie_file: e.target.value || null,
                })
              }
              placeholder="path/to/cookies.txt"
            />
          </div>
        </div>
      );

    case "basic":
      return (
        <div className="space-y-3">
          <TagInputField
            label="Domains"
            description="Regex patterns for domains this provider handles"
            value={provider.domains}
            onChange={(v) => onChange({ ...provider, domains: v })}
            placeholder="e.g. example\\.com"
          />
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Username</Label>
              <Input
                value={(provider.username as string) || ""}
                onChange={(e) =>
                  onChange({ ...provider, username: e.target.value })
                }
              />
            </div>
            <div className="space-y-1">
              <Label>Password</Label>
              <Input
                type="password"
                value={(provider.password as string) || ""}
                onChange={(e) =>
                  onChange({ ...provider, password: e.target.value })
                }
              />
            </div>
          </div>
        </div>
      );

    case "bearer":
      return (
        <div className="space-y-3">
          <TagInputField
            label="Domains"
            description="Regex patterns for domains this provider handles"
            value={provider.domains}
            onChange={(v) => onChange({ ...provider, domains: v })}
            placeholder="e.g. example\\.com"
          />
          <div className="space-y-1">
            <Label>Token</Label>
            <Input
              type="password"
              value={(provider.token as string) || ""}
              onChange={(e) => onChange({ ...provider, token: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Header name</Label>
              <Input
                value={(provider.header_name as string) || "Authorization"}
                onChange={(e) =>
                  onChange({ ...provider, header_name: e.target.value })
                }
              />
            </div>
            <div className="space-y-1">
              <Label>Header prefix</Label>
              <Input
                value={(provider.header_prefix as string) || "Bearer"}
                onChange={(e) =>
                  onChange({ ...provider, header_prefix: e.target.value })
                }
              />
            </div>
          </div>
        </div>
      );

    case "service_account":
      return (
        <div className="space-y-3">
          <TagInputField
            label="Domains"
            description="Regex patterns for domains this provider handles"
            value={provider.domains}
            onChange={(v) => onChange({ ...provider, domains: v })}
            placeholder="e.g. example\\.com"
          />
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Client ID</Label>
              <Input
                value={(provider.client_id as string) || ""}
                onChange={(e) =>
                  onChange({ ...provider, client_id: e.target.value })
                }
              />
            </div>
            <div className="space-y-1">
              <Label>Client secret</Label>
              <Input
                type="password"
                value={(provider.client_secret as string) || ""}
                onChange={(e) =>
                  onChange({ ...provider, client_secret: e.target.value })
                }
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Token URL</Label>
            <Input
              value={(provider.token_url as string) || ""}
              onChange={(e) =>
                onChange({ ...provider, token_url: e.target.value })
              }
              placeholder="https://auth.example.com/oauth/token"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Scope</Label>
              <Input
                value={(provider.scope as string) || ""}
                onChange={(e) =>
                  onChange({
                    ...provider,
                    scope: e.target.value || null,
                  })
                }
                placeholder="read write"
              />
            </div>
            <div className="space-y-1">
              <Label>Token expiry buffer (seconds)</Label>
              <Input
                type="number"
                value={(provider.token_expiry_buffer_seconds as number) ?? 60}
                onChange={(e) =>
                  onChange({
                    ...provider,
                    token_expiry_buffer_seconds: parseInt(e.target.value),
                  })
                }
              />
            </div>
          </div>
        </div>
      );

    case "playwright_sso":
      return (
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Provider name</Label>
            <Input
              value={(provider.name as string) || ""}
              onChange={(e) => onChange({ ...provider, name: e.target.value })}
              placeholder="e.g. company-sso"
            />
          </div>
          <TagInputField
            label="Domains"
            description="Regex patterns for domains this provider handles"
            value={provider.domains}
            onChange={(v) => onChange({ ...provider, domains: v })}
            placeholder="e.g. example\\.com"
          />
          <div className="space-y-1">
            <Label>Login URL</Label>
            <Input
              value={(provider.login_url as string) || ""}
              onChange={(e) =>
                onChange({
                  ...provider,
                  login_url: e.target.value || null,
                })
              }
              placeholder="https://login.example.com/sso"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Success URL pattern</Label>
              <Input
                value={(provider.success_url_pattern as string) || ""}
                onChange={(e) =>
                  onChange({
                    ...provider,
                    success_url_pattern: e.target.value || null,
                  })
                }
                placeholder="Regex for post-login URL"
              />
            </div>
            <div className="space-y-1">
              <Label>Login complete marker</Label>
              <Input
                value={(provider.login_complete_marker as string) || ""}
                onChange={(e) =>
                  onChange({
                    ...provider,
                    login_complete_marker: e.target.value || null,
                  })
                }
                placeholder="CSS selector"
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Storage state file</Label>
            <Input
              value={(provider.storage_state_file as string) || ""}
              onChange={(e) =>
                onChange({
                  ...provider,
                  storage_state_file: e.target.value || null,
                })
              }
              placeholder="path/to/state.json"
            />
          </div>
          <TagInputField
            label="Authenticated markers"
            description="CSS/text selectors indicating user is logged in"
            value={(provider.authenticated_markers as string[]) || []}
            onChange={(v) =>
              onChange({ ...provider, authenticated_markers: v })
            }
            placeholder="e.g. text=Sign out"
          />
          <TagInputField
            label="Login required markers"
            description="CSS/text selectors indicating login is needed"
            value={(provider.login_required_markers as string[]) || []}
            onChange={(v) =>
              onChange({ ...provider, login_required_markers: v })
            }
            placeholder="e.g. input[type='password']"
          />
          <TagInputField
            label="Auth domain patterns"
            description="URL substrings for auth provider domains"
            value={(provider.auth_domain_patterns as string[]) || []}
            onChange={(v) => onChange({ ...provider, auth_domain_patterns: v })}
          />
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label>Browser type</Label>
              <Select
                value={(provider.browser_type as string) || "chromium"}
                onValueChange={(v) =>
                  onChange({ ...provider, browser_type: v })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="chromium">Chromium</SelectItem>
                  <SelectItem value="firefox">Firefox</SelectItem>
                  <SelectItem value="webkit">WebKit</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Timeout (seconds)</Label>
              <Input
                type="number"
                value={(provider.timeout_seconds as number) ?? 300}
                onChange={(e) =>
                  onChange({
                    ...provider,
                    timeout_seconds: parseInt(e.target.value),
                  })
                }
              />
            </div>
            <div className="flex items-end pb-2">
              <div className="flex items-center justify-between w-full">
                <Label>Headless</Label>
                <Switch
                  checked={(provider.headless as boolean) || false}
                  onCheckedChange={(v) =>
                    onChange({ ...provider, headless: v })
                  }
                />
              </div>
            </div>
          </div>
        </div>
      );

    default:
      return (
        <TagInputField
          label="Domains"
          value={provider.domains}
          onChange={(v) => onChange({ ...provider, domains: v })}
        />
      );
  }
}

export function AuthProviderForm({
  providers,
  onChange,
}: AuthProviderFormProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const addProvider = (type: string) => {
    onChange([...providers, getProviderDefaults(type)]);
    setExpandedIndex(providers.length);
  };

  const removeProvider = (index: number) => {
    onChange(providers.filter((_, i) => i !== index));
    if (expandedIndex === index) setExpandedIndex(null);
    else if (expandedIndex !== null && expandedIndex > index)
      setExpandedIndex(expandedIndex - 1);
  };

  const updateProvider = (index: number, updated: AuthProvider) => {
    onChange(providers.map((p, i) => (i === index ? updated : p)));
  };

  return (
    <div className="space-y-3">
      {providers.map((provider, index) => {
        const typeLabel =
          PROVIDER_TYPES.find((t) => t.value === provider.type)?.label ||
          provider.type;
        const isExpanded = expandedIndex === index;

        return (
          <div key={index} className="border rounded-md">
            <div
              className="flex items-center justify-between p-3 cursor-pointer hover:bg-muted/50"
              onClick={() => setExpandedIndex(isExpanded ? null : index)}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{typeLabel}</span>
                {provider.domains.length > 0 && (
                  <span className="text-xs text-muted-foreground">
                    ({provider.domains.length} domain
                    {provider.domains.length !== 1 ? "s" : ""})
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeProvider(index);
                  }}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {isExpanded && (
              <div className="p-3 border-t space-y-3">
                <div className="space-y-1">
                  <Label>Provider type</Label>
                  <Select
                    value={provider.type}
                    onValueChange={(v) => {
                      const defaults = getProviderDefaults(v);
                      updateProvider(index, {
                        ...defaults,
                        domains: provider.domains,
                      });
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PROVIDER_TYPES.map((t) => (
                        <SelectItem key={t.value} value={t.value}>
                          {t.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <ProviderFields
                  provider={provider}
                  onChange={(updated) => updateProvider(index, updated)}
                />

                <SemanticAuthFields
                  provider={provider}
                  onChange={(updated) => updateProvider(index, updated)}
                />
              </div>
            )}
          </div>
        );
      })}

      <div className="flex flex-wrap gap-2">
        {PROVIDER_TYPES.map((t) => (
          <Button
            key={t.value}
            variant="outline"
            size="sm"
            onClick={() => addProvider(t.value)}
          >
            <Plus className="h-3 w-3 mr-1" />
            {t.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
