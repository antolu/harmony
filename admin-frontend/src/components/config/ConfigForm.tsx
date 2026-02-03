import { useState, useEffect, useRef } from "react";
import { stringify as yamlStringify, parse as yamlParse } from "yaml";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import Editor, { OnMount } from "@monaco-editor/react";
import type * as Monaco from "monaco-editor";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { TagInput } from "emblor";
import { api } from "@/api/client";
import { AuthProviderForm } from "@/components/config/AuthProviderForm";
import { DomainRoutingForm } from "@/components/config/DomainRoutingForm";
import { SpiderSettingsForm } from "@/components/config/SpiderSettingsForm";

interface ConfigFormProps {
  schema: Record<string, unknown>;
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
  onSave: () => void;
  onRun?: () => void;
  isSaving?: boolean;
  isRunning?: boolean;
}

export function ConfigForm({
  schema,
  config,
  onChange,
  onSave,
  onRun,
  isSaving,
  isRunning,
}: ConfigFormProps) {
  const [yamlContent, setYamlContent] = useState("");
  const [yamlError, setYamlError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [esValidating, setEsValidating] = useState(false);
  const [esValidation, setEsValidation] = useState<{
    valid: boolean;
    message?: string;
    clusterName?: string;
  } | null>(null);
  const monacoRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null);
  const activeTagIndices = useRef<Record<string, number | null>>({});

  useEffect(() => {
    try {
      setYamlContent(yamlStringify(config));
      setYamlError(null);
    } catch {
      // Keep existing content on error
    }
  }, [config]);

  const validateAgainstSchema = async (parsed: Record<string, unknown>) => {
    setValidationErrors([]);

    const properties = (schema as Record<string, unknown>).properties as
      | Record<string, unknown>
      | undefined;
    const required = (schema as Record<string, unknown>).required as
      | string[]
      | undefined;

    if (!properties || !required) return;

    const errors: string[] = [];
    for (const field of required) {
      if (
        !(field in parsed) ||
        parsed[field] === null ||
        parsed[field] === undefined
      ) {
        errors.push(`${field}: Field is required`);
      }
    }

    // Cross-field validation
    const auth = parsed.auth as Record<string, unknown> | undefined;
    if (
      auth?.enabled &&
      Array.isArray(auth.providers) &&
      auth.providers.length === 0
    ) {
      errors.push(
        "auth: At least one provider is required when authentication is enabled",
      );
    }

    if (parsed.recrawl_mode === "age-based") {
      const maxAge = parsed.max_age_days as number;
      if (!maxAge || maxAge <= 0) {
        errors.push(
          "max_age_days: Must be greater than 0 when recrawl_mode is age-based",
        );
      }
    }

    if (errors.length > 0) {
      setValidationErrors(errors);
    }
  };

  const resolveNestedSchema = (
    path: string,
    rootSchema: Record<string, unknown>,
  ): Record<string, unknown> | null => {
    const parts = path.split(".");
    let current = rootSchema;

    for (const part of parts) {
      const props = current.properties as Record<string, unknown> | undefined;
      if (!props || !props[part]) return null;
      current = props[part] as Record<string, unknown>;
    }
    return current;
  };

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    monacoRef.current = editor;

    monaco.languages.registerHoverProvider("yaml", {
      provideHover: (
        model: Monaco.editor.ITextModel,
        position: Monaco.Position,
      ) => {
        const lineText = model.getLineContent(position.lineNumber);
        const word = model.getWordAtPosition(position);
        if (!word) return null;

        // Determine indentation context for nested fields
        const indent = lineText.match(/^(\s*)/)?.[1]?.length || 0;
        let parentKey: string | null = null;

        if (indent > 0) {
          // Look backwards for the parent key at a lower indentation level
          for (let line = position.lineNumber - 1; line >= 1; line--) {
            const prevLine = model.getLineContent(line);
            const prevIndent = prevLine.match(/^(\s*)/)?.[1]?.length || 0;
            if (prevIndent < indent && prevLine.trim().length > 0) {
              const match = prevLine.match(/^\s*(\w+)\s*:/);
              if (match) {
                parentKey = match[1];
              }
              break;
            }
          }
        }

        const key = word.word;

        // Try nested path first, then fall back to top-level
        const paths = parentKey ? [`${parentKey}.${key}`, key] : [key];
        let propSchema: Record<string, unknown> | null = null;

        for (const path of paths) {
          propSchema = resolveNestedSchema(path, schema);
          if (propSchema) break;
        }

        if (!propSchema) return null;

        const description = propSchema.description as string | undefined;
        const type = propSchema.type as string | undefined;
        const defaultValue = propSchema.default;
        const enumValues = propSchema.enum as string[] | undefined;

        if (!description) return null;

        const contents = [`**${key}**`, "", description];

        if (type) {
          contents.push("", `*Type:* \`${type}\``);
        }

        if (defaultValue !== undefined) {
          contents.push(`*Default:* \`${JSON.stringify(defaultValue)}\``);
        }

        if (enumValues) {
          contents.push(
            `*Allowed values:* ${enumValues.map((v) => `\`${v}\``).join(", ")}`,
          );
        }

        return {
          range: new monaco.Range(
            position.lineNumber,
            word.startColumn,
            position.lineNumber,
            word.endColumn,
          ),
          contents: contents.map((text) => ({ value: text })),
        };
      },
    });
  };

  const handleYamlChange = (value: string | undefined) => {
    if (value === undefined) return;

    setYamlContent(value);
    try {
      const parsed = yamlParse(value);
      onChange(parsed);
      setYamlError(null);
      validateAgainstSchema(parsed);
    } catch (e) {
      setYamlError(e instanceof Error ? e.message : "Invalid YAML");
      setValidationErrors([]);
    }
  };

  const updateConfig = (path: string, value: unknown) => {
    const newConfig = { ...config };
    const parts = path.split(".");
    let current: Record<string, unknown> = newConfig;

    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]] || typeof current[parts[i]] !== "object") {
        current[parts[i]] = {};
      }
      current[parts[i]] = { ...(current[parts[i]] as Record<string, unknown>) };
      current = current[parts[i]] as Record<string, unknown>;
    }

    current[parts[parts.length - 1]] = value;

    // Auto-populate domain_routing.exact from start_urls
    if (path === "start_urls" && Array.isArray(value)) {
      const routing =
        (newConfig.domain_routing as Record<string, unknown>) || {};
      const exact = { ...((routing.exact as Record<string, string>) || {}) };
      let changed = false;
      for (const url of value as string[]) {
        try {
          const domain = new URL(url).hostname;
          if (domain && !(domain in exact)) {
            exact[domain] = "generic";
            changed = true;
          }
        } catch {
          // skip malformed URLs
        }
      }
      if (changed) {
        newConfig.domain_routing = { ...routing, exact };
      }
    }

    onChange(newConfig);
  };

  const getPropertySchema = (
    path: string,
  ): Record<string, unknown> | undefined => {
    const properties = (schema as Record<string, unknown>).properties as Record<
      string,
      unknown
    >;
    if (!properties) return undefined;

    const parts = path.split(".");
    let current = properties;

    for (const part of parts) {
      if (!current[part]) return undefined;
      const prop = current[part] as Record<string, unknown>;
      if (prop.properties) {
        current = prop.properties as Record<string, unknown>;
      } else {
        return prop;
      }
    }
    return current as Record<string, unknown>;
  };

  const getDefaultValue = (propSchema: Record<string, unknown>): unknown => {
    if ("default" in propSchema) {
      return propSchema.default;
    }
    const type = propSchema.type as string;
    if (type === "array") return [];
    if (type === "boolean") return false;
    if (type === "integer" || type === "number") return 0;
    return "";
  };

  const validateElasticsearch = async (url: string) => {
    if (!url || !url.startsWith("http")) {
      setEsValidation(null);
      return;
    }

    setEsValidating(true);
    try {
      const result = await api.validateElasticsearch(url);
      setEsValidation({
        valid: true,
        message: `Connected to ${result.cluster_name} (${result.number_of_nodes} nodes, status: ${result.status})`,
        clusterName: result.cluster_name,
      });
    } catch (error) {
      setEsValidation({
        valid: false,
        message: error instanceof Error ? error.message : "Connection failed",
      });
    } finally {
      setEsValidating(false);
    }
  };

  useEffect(() => {
    const esHost = config.es_state_host as string;
    if (esHost) {
      const timer = setTimeout(() => validateElasticsearch(esHost), 500);
      return () => clearTimeout(timer);
    }
    setEsValidation(null);
  }, [config.es_state_host]);

  const renderField = (path: string, propSchema: Record<string, unknown>) => {
    const value = path.split(".").reduce((obj, key) => {
      return obj && typeof obj === "object"
        ? (obj as Record<string, unknown>)[key]
        : undefined;
    }, config as unknown);

    const type = propSchema.type as string;
    const label = (propSchema.title as string) || path.split(".").pop();
    const description = propSchema.description as string | undefined;
    const enumValues = propSchema.enum as string[] | undefined;
    const defaultValue = getDefaultValue(propSchema);
    const schemaDefault = propSchema.default;

    if (enumValues) {
      return (
        <div key={path} className="space-y-2">
          <Label htmlFor={path}>{label}</Label>
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
          <Select
            value={(value as string) || enumValues[0]}
            onValueChange={(v) => updateConfig(path, v)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {enumValues.map((enumValue) => (
                <SelectItem key={enumValue} value={enumValue}>
                  {enumValue}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      );
    }

    if (type === "boolean") {
      return (
        <div key={path} className="flex items-center justify-between">
          <div>
            <Label htmlFor={path}>{label}</Label>
            {description && (
              <p className="text-xs text-muted-foreground">{description}</p>
            )}
          </div>
          <Switch
            id={path}
            checked={(value as boolean) || false}
            onCheckedChange={(v) => updateConfig(path, v)}
          />
        </div>
      );
    }

    if (type === "array") {
      const currentItems = (value as unknown[]) || [];
      const items = currentItems.map((item, index) => ({
        id: `${path}-${index}`,
        text: String(item),
      }));
      const defaultItems = Array.isArray(schemaDefault)
        ? (schemaDefault as string[])
        : [];
      const showDefaults = currentItems.length === 0 && defaultItems.length > 0;

      return (
        <div key={path} className="space-y-2">
          <Label>{label}</Label>
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
          {showDefaults && (
            <div className="flex flex-wrap gap-1">
              {defaultItems.map((tag, i) => (
                <span
                  key={i}
                  className="inline-flex items-center px-2 py-0.5 text-xs rounded-md bg-muted text-muted-foreground border border-dashed"
                >
                  {tag}
                </span>
              ))}
              <span className="text-xs text-muted-foreground self-center ml-1">
                ← defaults (type to override)
              </span>
            </div>
          )}
          <TagInput
            tags={items}
            setTags={(newTags) => {
              const values = Array.isArray(newTags)
                ? newTags.map((tag) =>
                    typeof tag === "string" ? tag : tag.text,
                  )
                : [];
              updateConfig(path, values);
            }}
            placeholder="Type and press Enter to add..."
            activeTagIndex={activeTagIndices.current[path] ?? null}
            setActiveTagIndex={(idx) => {
              activeTagIndices.current[path] =
                typeof idx === "function"
                  ? idx(activeTagIndices.current[path] ?? null)
                  : idx;
            }}
            delimiterList={[" ", ","]}
            addOnPaste
            styleClasses={{
              input: "h-9",
              tag: {
                body: "pl-2 pr-1",
              },
            }}
            className="border rounded-md"
          />
        </div>
      );
    }

    if (type === "integer" || type === "number") {
      return (
        <div key={path} className="space-y-2">
          <Label htmlFor={path}>{label}</Label>
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
          <Input
            id={path}
            type="number"
            value={
              value !== undefined && value !== null
                ? (value as number)
                : (defaultValue as number) || ""
            }
            onChange={(e) =>
              updateConfig(
                path,
                type === "integer"
                  ? parseInt(e.target.value)
                  : parseFloat(e.target.value),
              )
            }
            placeholder={
              defaultValue !== undefined ? String(defaultValue) : undefined
            }
          />
        </div>
      );
    }

    // ES host validation
    const isEsHost = path === "es_state_host";
    const urlValue = (value as string) || "";

    return (
      <div key={path} className="space-y-2">
        <Label htmlFor={path}>{label}</Label>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
        <div className="relative">
          <Input
            id={path}
            value={urlValue}
            onChange={(e) => updateConfig(path, e.target.value)}
            className={
              isEsHost && esValidation && !esValidation.valid
                ? "border-destructive pr-10"
                : isEsHost && esValidation?.valid
                  ? "border-green-500 pr-10"
                  : ""
            }
            placeholder={
              defaultValue !== undefined ? String(defaultValue) : undefined
            }
          />
          {isEsHost && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              {esValidating ? (
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              ) : esValidation?.valid ? (
                <CheckCircle2 className="h-4 w-4 text-green-500" />
              ) : esValidation ? (
                <XCircle className="h-4 w-4 text-destructive" />
              ) : null}
            </div>
          )}
        </div>
        {isEsHost && esValidation && (
          <p
            className={`text-xs ${esValidation.valid ? "text-green-600" : "text-destructive"}`}
          >
            {esValidation.message}
          </p>
        )}
      </div>
    );
  };

  // Derived state for nested forms
  const proxyEnabled = !!(config.proxy as Record<string, unknown>);
  const proxy = (config.proxy as Record<string, unknown>) || {};
  const authEnabled = !!(config.auth as Record<string, unknown>);
  const auth = (config.auth as Record<string, unknown>) || {};
  const authProviders = (auth.providers as unknown[]) || [];

  const domainRouting = (config.domain_routing as Record<string, unknown>) || {
    exact: {},
    patterns: [],
    default: "generic",
  };

  const spiderSettings = (config.spider_settings as Record<
    string,
    unknown
  >) || {
    docs: { skip_versions: false, version_allowlist: [], deny_patterns: [] },
    drupal: { deny_patterns: [] },
    generic: { deny_patterns: [] },
  };

  return (
    <Tabs defaultValue="form">
      <div className="flex items-center justify-between mb-4">
        <TabsList>
          <TabsTrigger value="form">Form</TabsTrigger>
          <TabsTrigger value="yaml">YAML</TabsTrigger>
        </TabsList>

        <div className="flex gap-2">
          <Button
            onClick={onSave}
            disabled={isSaving || !!yamlError || validationErrors.length > 0}
          >
            {isSaving ? "Saving..." : "Save"}
          </Button>
          {onRun && (
            <Button
              onClick={onRun}
              disabled={isRunning || !!yamlError || validationErrors.length > 0}
              variant="secondary"
            >
              {isRunning ? "Starting..." : "Run"}
            </Button>
          )}
        </div>
      </div>

      <TabsContent value="form" className="space-y-4">
        {/* Basic Settings */}
        <Card>
          <CardHeader>
            <CardTitle>Basic Settings</CardTitle>
            <CardDescription>Core configuration options</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {renderField(
              "start_urls",
              getPropertySchema("start_urls") || {
                type: "array",
                description: "URLs to start crawling from",
              },
            )}
            {renderField(
              "output",
              getPropertySchema("output") || {
                type: "string",
                description: "Output directory",
              },
            )}
            {renderField(
              "max_depth",
              getPropertySchema("max_depth") || {
                type: "integer",
                description: "Maximum crawl depth",
              },
            )}
            {renderField(
              "delay",
              getPropertySchema("delay") || {
                type: "number",
                description: "Delay between requests",
              },
            )}
            {renderField(
              "concurrent",
              getPropertySchema("concurrent") || {
                type: "integer",
                description: "Concurrent requests",
              },
            )}
            {renderField(
              "download_timeout",
              getPropertySchema("download_timeout") || {
                type: "number",
                description: "Request timeout in seconds",
              },
            )}
          </CardContent>
        </Card>

        <Accordion type="single" collapsible>
          {/* Domain Settings */}
          <AccordionItem value="domains">
            <AccordionTrigger>Domain Settings</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              {renderField(
                "allowed_domains",
                getPropertySchema("allowed_domains") || {
                  type: "array",
                  description: "Additional allowed domain patterns",
                },
              )}
              {renderField(
                "forbidden_domains",
                getPropertySchema("forbidden_domains") || {
                  type: "array",
                  description: "Domain patterns to exclude",
                },
              )}
              {renderField(
                "link_extractor_deny",
                getPropertySchema("link_extractor_deny") || {
                  type: "array",
                  description:
                    "Regex patterns for URLs to skip (scope filtering)",
                },
              )}
            </AccordionContent>
          </AccordionItem>

          {/* Domain Routing */}
          <AccordionItem value="routing">
            <AccordionTrigger>Domain Routing</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              <p className="text-xs text-muted-foreground">
                Route domains to specific spider types based on exact matches or
                regex patterns
              </p>
              <DomainRoutingForm
                routing={{
                  exact: (domainRouting.exact as Record<string, string>) || {},
                  patterns:
                    (domainRouting.patterns as Array<{
                      pattern: string;
                      spider: string;
                    }>) || [],
                  default: (domainRouting.default as string) || "generic",
                }}
                onChange={(routing) => updateConfig("domain_routing", routing)}
              />
            </AccordionContent>
          </AccordionItem>

          {/* Spider Settings */}
          <AccordionItem value="spiders">
            <AccordionTrigger>Spider Settings</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              <SpiderSettingsForm
                settings={{
                  docs: {
                    skip_versions:
                      ((spiderSettings.docs as Record<string, unknown>)
                        ?.skip_versions as boolean) || false,
                    version_allowlist:
                      ((spiderSettings.docs as Record<string, unknown>)
                        ?.version_allowlist as string[]) || [],
                    deny_patterns:
                      ((spiderSettings.docs as Record<string, unknown>)
                        ?.deny_patterns as string[]) || [],
                  },
                  drupal: {
                    deny_patterns:
                      ((spiderSettings.drupal as Record<string, unknown>)
                        ?.deny_patterns as string[]) || [],
                  },
                  generic: {
                    deny_patterns:
                      ((spiderSettings.generic as Record<string, unknown>)
                        ?.deny_patterns as string[]) || [],
                  },
                }}
                onChange={(settings) =>
                  updateConfig("spider_settings", settings)
                }
              />
            </AccordionContent>
          </AccordionItem>

          {/* Proxy Configuration */}
          <AccordionItem value="proxy">
            <AccordionTrigger>Proxy Configuration</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>Enable proxy</Label>
                  <p className="text-xs text-muted-foreground">
                    Route requests through a proxy server
                  </p>
                </div>
                <Switch
                  checked={proxyEnabled}
                  onCheckedChange={(v) => {
                    if (v) {
                      updateConfig("proxy", {
                        url: "",
                        username: null,
                        password: null,
                      });
                    } else {
                      updateConfig("proxy", null);
                    }
                  }}
                />
              </div>
              {proxyEnabled && (
                <div className="space-y-3">
                  <div className="space-y-1">
                    <Label>Proxy URL</Label>
                    <p className="text-xs text-muted-foreground">
                      Scheme determines type (http/https/socks4/socks5)
                    </p>
                    <Input
                      value={(proxy.url as string) || ""}
                      onChange={(e) =>
                        updateConfig("proxy.url", e.target.value)
                      }
                      placeholder="http://proxy.example.com:8080"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label>Username</Label>
                      <Input
                        value={(proxy.username as string) || ""}
                        onChange={(e) =>
                          updateConfig("proxy.username", e.target.value || null)
                        }
                        placeholder="Optional"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label>Password</Label>
                      <Input
                        type="password"
                        value={(proxy.password as string) || ""}
                        onChange={(e) =>
                          updateConfig("proxy.password", e.target.value || null)
                        }
                        placeholder="Optional"
                      />
                    </div>
                  </div>
                </div>
              )}
            </AccordionContent>
          </AccordionItem>

          {/* Authentication */}
          <AccordionItem value="auth">
            <AccordionTrigger>Authentication</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>Enable authentication</Label>
                  <p className="text-xs text-muted-foreground">
                    Configure auth providers for protected sites
                  </p>
                </div>
                <Switch
                  checked={authEnabled}
                  onCheckedChange={(v) => {
                    if (v) {
                      updateConfig("auth", {
                        enabled: true,
                        session_storage_path: ".harmony-auth-sessions",
                        retry_on_auth_failure: true,
                        max_auth_retries: 2,
                        auto_authenticate_on_403: true,
                        providers: [],
                      });
                    } else {
                      updateConfig("auth", null);
                    }
                  }}
                />
              </div>
              {authEnabled && (
                <div className="space-y-4">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>Retry on auth failure</Label>
                        <p className="text-xs text-muted-foreground">
                          Re-authenticate and retry on failure
                        </p>
                      </div>
                      <Switch
                        checked={
                          (auth.retry_on_auth_failure as boolean) ?? true
                        }
                        onCheckedChange={(v) =>
                          updateConfig("auth.retry_on_auth_failure", v)
                        }
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>Auto-authenticate on 403</Label>
                        <p className="text-xs text-muted-foreground">
                          Trigger auth flow automatically on 403 responses
                        </p>
                      </div>
                      <Switch
                        checked={
                          (auth.auto_authenticate_on_403 as boolean) ?? true
                        }
                        onCheckedChange={(v) =>
                          updateConfig("auth.auto_authenticate_on_403", v)
                        }
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label>Max auth retries</Label>
                        <Input
                          type="number"
                          value={(auth.max_auth_retries as number) ?? 2}
                          onChange={(e) =>
                            updateConfig(
                              "auth.max_auth_retries",
                              parseInt(e.target.value),
                            )
                          }
                        />
                      </div>
                      <div className="space-y-1">
                        <Label>Session storage path</Label>
                        <Input
                          value={
                            (auth.session_storage_path as string) ||
                            ".harmony-auth-sessions"
                          }
                          onChange={(e) =>
                            updateConfig(
                              "auth.session_storage_path",
                              e.target.value,
                            )
                          }
                        />
                      </div>
                    </div>
                  </div>

                  <div className="border-t pt-3">
                    <Label className="text-sm font-medium">
                      Auth Providers
                    </Label>
                    <p className="text-xs text-muted-foreground mb-2">
                      Add providers to authenticate with protected sites
                    </p>
                    {authEnabled && authProviders.length === 0 && (
                      <p className="text-xs text-destructive mb-2">
                        At least one provider is required when authentication is
                        enabled
                      </p>
                    )}
                    <AuthProviderForm
                      providers={
                        authProviders as Array<{
                          type: string;
                          domains: string[];
                          [key: string]: unknown;
                        }>
                      }
                      onChange={(providers) =>
                        updateConfig("auth.providers", providers)
                      }
                    />
                  </div>
                </div>
              )}
            </AccordionContent>
          </AccordionItem>

          {/* Safety Settings */}
          <AccordionItem value="safety">
            <AccordionTrigger>Safety Settings</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              {renderField(
                "safe_mode",
                getPropertySchema("safe_mode") || {
                  type: "boolean",
                  description: "Enable strict safety checks",
                },
              )}
              {renderField(
                "dry_run",
                getPropertySchema("dry_run") || {
                  type: "boolean",
                  description: "Log URLs without requesting",
                },
              )}
              {renderField(
                "allow_mutations",
                getPropertySchema("allow_mutations") || {
                  type: "boolean",
                  description: "Allow mutation endpoints",
                },
              )}
              {renderField(
                "ignore_robots",
                getPropertySchema("ignore_robots") || {
                  type: "boolean",
                  description: "Ignore robots.txt",
                },
              )}
              {renderField(
                "interactive_safety",
                getPropertySchema("interactive_safety") || {
                  type: "boolean",
                  description:
                    "Prompt to approve/deny blocked URLs interactively",
                },
              )}
              {renderField(
                "safety_allow_list",
                getPropertySchema("safety_allow_list") || {
                  type: "array",
                  description: "URL patterns to always allow",
                },
              )}
              {renderField(
                "safety_deny_list",
                getPropertySchema("safety_deny_list") || {
                  type: "array",
                  description: "URL patterns to always deny",
                },
              )}
              <div className="space-y-2">
                <Label htmlFor="safety_lists_file">safety_lists_file</Label>
                <p className="text-xs text-muted-foreground">
                  File to persist learned allow/deny patterns
                </p>
                <Input
                  id="safety_lists_file"
                  value={
                    (config.safety_lists_file as string) ||
                    ".harmony-safety-lists.json"
                  }
                  onChange={(e) =>
                    updateConfig("safety_lists_file", e.target.value)
                  }
                  placeholder=".harmony-safety-lists.json"
                />
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* State Tracking */}
          <AccordionItem value="state">
            <AccordionTrigger>State Tracking</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              {renderField(
                "es_state_host",
                getPropertySchema("es_state_host") || {
                  type: "string",
                  description: "Elasticsearch host for state tracking",
                },
              )}
              {renderField(
                "es_state_index",
                getPropertySchema("es_state_index") || {
                  type: "string",
                  description: "State index name",
                },
              )}
              {renderField(
                "recrawl_mode",
                getPropertySchema("recrawl_mode") || {
                  type: "string",
                  enum: ["full", "age-based"],
                  description: "Re-crawl mode",
                },
              )}
              {renderField(
                "max_age_days",
                getPropertySchema("max_age_days") || {
                  type: "integer",
                  description: "Max age for re-crawling",
                },
              )}
              {renderField(
                "delete_missing",
                getPropertySchema("delete_missing") || {
                  type: "boolean",
                  description: "Auto-delete URLs missing for threshold crawls",
                },
              )}
              {(config.delete_missing as boolean) && (
                <div className="pl-4 border-l-2 border-destructive/30">
                  <p className="text-xs text-destructive mb-2">
                    Enabling this will automatically delete URLs from the state
                    index after they are missing for the configured number of
                    crawls.
                  </p>
                  {renderField(
                    "missing_threshold",
                    getPropertySchema("missing_threshold") || {
                      type: "integer",
                      description: "Crawls before marking URL for deletion",
                    },
                  )}
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="jobdir">jobdir</Label>
                <p className="text-xs text-muted-foreground">
                  Directory for pause/resume state
                </p>
                <Input
                  id="jobdir"
                  value={(config.jobdir as string) || ""}
                  onChange={(e) =>
                    updateConfig("jobdir", e.target.value || null)
                  }
                  placeholder="e.g. .crawl-state"
                />
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* Throttling */}
          <AccordionItem value="throttle">
            <AccordionTrigger>Throttling</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              {renderField(
                "autothrottle_enabled",
                getPropertySchema("autothrottle_enabled") || {
                  type: "boolean",
                  description: "Enable auto-throttle",
                },
              )}
              {renderField(
                "autothrottle_start_delay",
                getPropertySchema("autothrottle_start_delay") || {
                  type: "number",
                  description: "Start delay",
                },
              )}
              {renderField(
                "autothrottle_max_delay",
                getPropertySchema("autothrottle_max_delay") || {
                  type: "number",
                  description: "Max delay",
                },
              )}
            </AccordionContent>
          </AccordionItem>

          {/* Advanced Settings */}
          <AccordionItem value="advanced">
            <AccordionTrigger>Advanced Settings</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              {renderField(
                "languages",
                getPropertySchema("languages") || {
                  type: "array",
                  description: "Restrict language detection to these languages",
                },
              )}
              <div className="space-y-2">
                <Label htmlFor="verbose">verbose</Label>
                <p className="text-xs text-muted-foreground">
                  Verbosity level (0=INFO, 1+=DEBUG)
                </p>
                <Select
                  value={String((config.verbose as number) ?? 0)}
                  onValueChange={(v) => updateConfig("verbose", parseInt(v))}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">0 (INFO)</SelectItem>
                    <SelectItem value="1">1 (DEBUG)</SelectItem>
                    <SelectItem value="2">2 (VERBOSE)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="stats_export_file">stats_export_file</Label>
                <p className="text-xs text-muted-foreground">
                  File path to export crawl stats JSON
                </p>
                <Input
                  id="stats_export_file"
                  value={(config.stats_export_file as string) || ""}
                  onChange={(e) =>
                    updateConfig("stats_export_file", e.target.value || null)
                  }
                  placeholder="e.g. stats.json"
                />
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </TabsContent>

      <TabsContent value="yaml">
        <Card>
          <CardHeader>
            <CardTitle>YAML Configuration</CardTitle>
            <CardDescription>Edit configuration as YAML</CardDescription>
          </CardHeader>
          <CardContent>
            {yamlError && (
              <div className="mb-2 p-2 bg-destructive/10 border border-destructive rounded">
                <p className="text-sm text-destructive font-semibold">
                  Syntax Error:
                </p>
                <p className="text-sm text-destructive">{yamlError}</p>
              </div>
            )}
            {validationErrors.length > 0 && (
              <div className="mb-2 p-2 bg-destructive/10 border border-destructive rounded">
                <p className="text-sm text-destructive font-semibold">
                  Validation Errors:
                </p>
                <ul className="text-sm text-destructive list-disc list-inside">
                  {validationErrors.map((error, i) => (
                    <li key={i}>{error}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="border rounded-md overflow-visible">
              <Editor
                height="500px"
                defaultLanguage="yaml"
                value={yamlContent}
                onChange={handleYamlChange}
                onMount={handleEditorDidMount}
                theme="light"
                options={{
                  minimap: { enabled: false },
                  fontSize: 13,
                  lineNumbers: "on",
                  scrollBeyondLastLine: false,
                  wordWrap: "on",
                  automaticLayout: true,
                  hover: {
                    above: false,
                  },
                }}
              />
            </div>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
}
