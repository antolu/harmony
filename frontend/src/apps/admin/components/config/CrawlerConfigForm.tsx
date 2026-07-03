import { useState, useEffect, useRef } from "react";
import { stringify as yamlStringify, parse as yamlParse } from "yaml";
import { ChevronLeft, ChevronRight, Info } from "lucide-react";
import Editor, { OnMount } from "@monaco-editor/react";
import type * as Monaco from "monaco-editor";
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
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/shared/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/shared/components/ui/accordion";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/shared/components/ui/collapsible";
import { Separator } from "@/shared/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";
import { TagInput } from "emblor-maintained";
import { AuthProviderForm } from "@/apps/admin/components/config/AuthProviderForm";
import { DomainRoutingForm } from "@/apps/admin/components/config/DomainRoutingForm";
import { SpiderSettingsForm } from "@/apps/admin/components/config/SpiderSettingsForm";
import { cn } from "@/shared/lib/utils";

interface CrawlerConfigFormProps {
  schema: Record<string, unknown>;
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
  onSave: () => void;
  onRun?: () => void;
  isSaving?: boolean;
  isRunning?: boolean;
}

export function CrawlerConfigForm({
  schema,
  config,
  onChange,
  onSave,
  onRun,
  isSaving,
  isRunning,
}: CrawlerConfigFormProps) {
  const [yamlContent, setYamlContent] = useState("");
  const [yamlError, setYamlError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState("form");
  const [activeSection, setActiveSection] = useState("core");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [openAccordionItem, setOpenAccordionItem] = useState<
    string | undefined
  >(undefined);
  const monacoRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null);
  const activeTagIndices = useRef<Record<string, number | null>>({});

  useEffect(() => {
    try {
      if (activeTab === "yaml") {
        try {
          const currentParsed = yamlParse(yamlContent);
          if (JSON.stringify(currentParsed) === JSON.stringify(config)) {
            return;
          }
        } catch {
          return;
        }
      }
      setYamlContent(yamlStringify(config));
      setYamlError(null);
    } catch {
      // Keep existing content on error
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config, activeTab]);

  const validateAgainstSchema = async (parsed: Record<string, unknown>) => {
    setValidationErrors([]);

    const properties = (schema as Record<string, unknown>).properties as
      Record<string, unknown> | undefined;
    const required = (schema as Record<string, unknown>).required as
      string[] | undefined;

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

        const indent = lineText.match(/^(\s*)/)?.[1]?.length || 0;
        let parentKey: string | null = null;

        if (indent > 0) {
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

  // Scroll spy to track active section
  useEffect(() => {
    if (activeTab !== "form") return;

    let timeoutId: NodeJS.Timeout | null = null;

    const handleScroll = () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      timeoutId = setTimeout(() => {
        const sections = [
          "core",
          "scope",
          "scope-domains",
          "scope-languages",
          "scope-routing",
          "scope-spiders",
          "auth",
          "advanced",
          "advanced-state",
          "advanced-performance",
          "advanced-safety",
          "advanced-storage",
        ];

        for (const sectionId of sections) {
          const element = document.getElementById(sectionId);
          if (element) {
            const rect = element.getBoundingClientRect();
            if (rect.top <= 100 && rect.bottom >= 0) {
              setActiveSection(sectionId);
              break;
            }
          }
        }
      }, 100);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll(); // Initial check

    return () => {
      window.removeEventListener("scroll", handleScroll);
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [activeTab]);

  const LabelWithTooltip = ({
    htmlFor,
    label,
    description,
  }: {
    htmlFor?: string;
    label: string;
    description?: string | undefined;
  }) => {
    if (!description) {
      return <Label htmlFor={htmlFor}>{label}</Label>;
    }

    return (
      <div className="flex items-center gap-1.5">
        <Label htmlFor={htmlFor}>{label}</Label>
        <Tooltip>
          <TooltipTrigger asChild>
            <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
          </TooltipTrigger>
          <TooltipContent side="right" className="max-w-xs">
            <p className="text-xs">{description}</p>
          </TooltipContent>
        </Tooltip>
      </div>
    );
  };

  const renderField = (path: string, propSchema: Record<string, unknown>) => {
    const value = path.split(".").reduce((obj, key) => {
      return obj && typeof obj === "object"
        ? (obj as Record<string, unknown>)[key]
        : undefined;
    }, config as unknown);

    const type = propSchema.type as string;
    const label = (propSchema.title as string) || path.split(".").pop() || path;
    const description = propSchema.description as string | undefined;
    const enumValues = propSchema.enum as string[] | undefined;
    const defaultValue = getDefaultValue(propSchema);
    const schemaDefault = propSchema.default;

    if (enumValues) {
      return (
        <div key={path} className="space-y-2">
          <LabelWithTooltip
            htmlFor={path}
            label={label}
            description={description}
          />
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
          <LabelWithTooltip
            htmlFor={path}
            label={label}
            description={description}
          />
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
          <LabelWithTooltip label={label} description={description} />
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
            delimiterList={["Enter", " ", ","]}
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
          <LabelWithTooltip
            htmlFor={path}
            label={label}
            description={description}
          />
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

    return (
      <div key={path} className="space-y-2">
        <LabelWithTooltip
          htmlFor={path}
          label={label}
          description={description}
        />
        <Input
          id={path}
          value={(value as string) || ""}
          onChange={(e) => updateConfig(path, e.target.value)}
          placeholder={
            defaultValue !== undefined ? String(defaultValue) : undefined
          }
        />
      </div>
    );
  };

  const proxy = (config.proxy as Record<string, unknown>) || {};
  const proxyEnabled = !!config.proxy && proxy.enabled !== false;
  const authEnabled = !!(config.auth as Record<string, unknown>);
  const auth = (config.auth as Record<string, unknown>) || {};
  const authProviders = (auth.providers as unknown[]) || [];

  const autothrottle = (config.autothrottle as Record<string, unknown>) || {};
  const autothrottleEnabled =
    !!config.autothrottle && autothrottle.enabled !== false;

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

  const scrollToSection = (sectionId: string) => {
    // Map section IDs to accordion values
    const accordionMap: Record<string, string> = {
      "scope-domains": "domains",
      "scope-languages": "languages",
      "scope-routing": "routing",
      "scope-spiders": "spiders",
    };

    // If this is a scope subitem, open the accordion first
    if (accordionMap[sectionId]) {
      setOpenAccordionItem(accordionMap[sectionId]);
      // Wait for accordion animation to complete before scrolling
      setTimeout(() => {
        const element = document.getElementById(sectionId);
        if (element) {
          element.scrollIntoView({ behavior: "smooth", block: "nearest" });
          setActiveSection(sectionId);
        }
      }, 200);
    } else {
      const element = document.getElementById(sectionId);
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "start" });
        setActiveSection(sectionId);
      }
    }
  };

  const navItems = [
    { id: "core", label: "Core Configuration" },
    {
      id: "scope",
      label: "Scope & Routing",
      subItems: [
        { id: "scope-domains", label: "Domain Rules" },
        { id: "scope-languages", label: "Languages" },
        { id: "scope-routing", label: "Domain Routing" },
        { id: "scope-spiders", label: "Spider Defaults" },
      ],
    },
    { id: "auth", label: "Authentication" },
    {
      id: "advanced",
      label: "Advanced Settings",
      subItems: [
        { id: "advanced-state", label: "State & Recrawl" },
        { id: "advanced-performance", label: "Performance & Infrastructure" },
        { id: "advanced-safety", label: "Safety" },
        { id: "advanced-storage", label: "Storage" },
      ],
    },
  ];

  return (
    <TooltipProvider>
      <Tabs defaultValue="form" value={activeTab} onValueChange={setActiveTab}>
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
                disabled={
                  isRunning || !!yamlError || validationErrors.length > 0
                }
                variant="secondary"
              >
                {isRunning ? "Starting..." : "Run"}
              </Button>
            )}
          </div>
        </div>

        <TabsContent value="form" className="mt-0">
          <div className="flex gap-6">
            {/* Collapsible Sidebar */}
            <Collapsible open={sidebarOpen} onOpenChange={setSidebarOpen}>
              <CollapsibleContent className="w-52 sticky top-4 self-start">
                <aside className="space-y-1">
                  <nav className="space-y-1">
                    {navItems.map((item) => (
                      <div key={item.id}>
                        <button
                          onClick={() => scrollToSection(item.id)}
                          className={cn(
                            "w-full text-left px-3 py-2 rounded-md text-sm font-medium transition-colors",
                            activeSection === item.id
                              ? "bg-primary text-primary-foreground"
                              : "text-muted-foreground hover:bg-muted hover:text-foreground",
                          )}
                        >
                          {item.label}
                        </button>
                        {item.subItems && (
                          <div className="ml-3 mt-1 space-y-1">
                            {item.subItems.map((subItem) => (
                              <button
                                key={subItem.id}
                                onClick={() => scrollToSection(subItem.id)}
                                className={cn(
                                  "w-full text-left px-3 py-1.5 rounded-md text-xs transition-colors",
                                  activeSection === subItem.id
                                    ? "bg-primary/10 text-primary font-medium"
                                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                                )}
                              >
                                {subItem.label}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </nav>
                </aside>
              </CollapsibleContent>

              <CollapsibleTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="fixed left-4 top-24 z-10 h-8 w-8 p-0 bg-background border shadow-sm"
                >
                  {sidebarOpen ? (
                    <ChevronLeft className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </Button>
              </CollapsibleTrigger>
            </Collapsible>

            {/* Main Form Content */}
            <div
              className={cn("flex-1 space-y-8", sidebarOpen ? "ml-0" : "ml-12")}
            >
              {/* Core Configuration */}
              <section id="core" className="space-y-4">
                <div className="pb-2 border-b">
                  <h2 className="text-2xl font-semibold">Core Configuration</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    Basic crawl settings and limits
                  </p>
                </div>
                {renderField(
                  "start_urls",
                  getPropertySchema("start_urls") || {
                    type: "array",
                    description: "URLs to start crawling from",
                  },
                )}
                <div className="grid grid-cols-2 gap-4">
                  {renderField(
                    "max_depth",
                    getPropertySchema("max_depth") || {
                      type: "integer",
                      description: "Maximum crawl depth",
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
                    "delay",
                    getPropertySchema("delay") || {
                      type: "number",
                      description: "Delay between requests",
                    },
                  )}
                  {renderField(
                    "download_timeout",
                    getPropertySchema("download_timeout") || {
                      type: "number",
                      description: "Request timeout in seconds",
                    },
                  )}
                </div>
              </section>

              <Separator />

              {/* Scope & Routing */}
              <section id="scope" className="space-y-4">
                <div className="pb-2 border-b">
                  <h2 className="text-2xl font-semibold">Scope & Routing</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    Control where the crawler can go and how it handles domains
                  </p>
                </div>
                <Accordion
                  type="single"
                  collapsible
                  className="w-full"
                  value={openAccordionItem}
                  onValueChange={setOpenAccordionItem}
                >
                  <AccordionItem value="domains">
                    <AccordionTrigger>Domain Rules</AccordionTrigger>
                    <AccordionContent className="space-y-4 p-4">
                      <div id="scope-domains">
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
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  <AccordionItem value="languages">
                    <AccordionTrigger>Languages</AccordionTrigger>
                    <AccordionContent className="space-y-4 p-4">
                      <div id="scope-languages">
                        {renderField(
                          "languages",
                          getPropertySchema("languages") || {
                            type: "array",
                            description:
                              "Restrict language detection to these languages",
                          },
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  <AccordionItem value="routing">
                    <AccordionTrigger>Domain Routing</AccordionTrigger>
                    <AccordionContent className="space-y-4 p-4">
                      <div id="scope-routing">
                        <DomainRoutingForm
                          routing={{
                            exact:
                              (domainRouting.exact as Record<string, string>) ||
                              {},
                            patterns:
                              (domainRouting.patterns as Array<{
                                pattern: string;
                                spider: string;
                              }>) || [],
                            default:
                              (domainRouting.default as string) || "generic",
                          }}
                          onChange={(routing) =>
                            updateConfig("domain_routing", routing)
                          }
                        />
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  <AccordionItem value="spiders">
                    <AccordionTrigger>Spider Defaults</AccordionTrigger>
                    <AccordionContent className="space-y-4 p-4">
                      <div id="scope-spiders">
                        <SpiderSettingsForm
                          settings={{
                            docs: {
                              skip_versions:
                                ((
                                  spiderSettings.docs as Record<string, unknown>
                                )?.skip_versions as boolean) || false,
                              version_allowlist:
                                ((
                                  spiderSettings.docs as Record<string, unknown>
                                )?.version_allowlist as string[]) || [],
                              deny_patterns:
                                ((
                                  spiderSettings.docs as Record<string, unknown>
                                )?.deny_patterns as string[]) || [],
                            },
                            drupal: {
                              deny_patterns:
                                ((
                                  spiderSettings.drupal as Record<
                                    string,
                                    unknown
                                  >
                                )?.deny_patterns as string[]) || [],
                            },
                            generic: {
                              deny_patterns:
                                ((
                                  spiderSettings.generic as Record<
                                    string,
                                    unknown
                                  >
                                )?.deny_patterns as string[]) || [],
                            },
                          }}
                          onChange={(settings) =>
                            updateConfig("spider_settings", settings)
                          }
                        />
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </section>

              <Separator />

              {/* Authentication */}
              <section id="auth" className="space-y-4">
                <div className="pb-2 border-b">
                  <h2 className="text-2xl font-semibold">Authentication</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    Configure auth providers for protected sites
                  </p>
                </div>
                <div className="flex items-center justify-between">
                  <Label>Enable authentication</Label>
                  <Switch
                    checked={authEnabled}
                    onCheckedChange={(v) => {
                      if (v) {
                        updateConfig("auth", {
                          enabled: true,
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
                  <div className="pl-4 pt-3 space-y-4 border-l-2">
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <Label>Retry on auth failure</Label>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                            </TooltipTrigger>
                            <TooltipContent side="right" className="max-w-xs">
                              <p className="text-xs">
                                Re-authenticate and retry on failure
                              </p>
                            </TooltipContent>
                          </Tooltip>
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
                        <div className="flex items-center gap-1.5">
                          <Label>Auto-authenticate on 403</Label>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                            </TooltipTrigger>
                            <TooltipContent side="right" className="max-w-xs">
                              <p className="text-xs">
                                Trigger auth flow automatically on 403 responses
                              </p>
                            </TooltipContent>
                          </Tooltip>
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
                    </div>

                    <div className="border-t pt-3">
                      <div className="flex items-center gap-1.5 mb-2">
                        <Label className="text-sm font-medium">
                          Auth Providers
                        </Label>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                          </TooltipTrigger>
                          <TooltipContent side="right" className="max-w-xs">
                            <p className="text-xs">
                              Add providers to authenticate with protected sites
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      {authEnabled && authProviders.length === 0 && (
                        <p className="text-xs text-destructive mb-2">
                          At least one provider is required when authentication
                          is enabled
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
              </section>

              <Separator />

              {/* Advanced Settings */}
              <section id="advanced" className="space-y-8">
                <div className="pb-2 border-b">
                  <h2 className="text-2xl font-semibold">Advanced Settings</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    State tracking, performance, infrastructure, and safety
                  </p>
                </div>

                {/* State & Recrawl */}
                <section id="advanced-state" className="space-y-4">
                  <div className="pb-1.5 border-b border-muted">
                    <h3 className="text-lg font-medium">
                      State & Recrawl Strategy
                    </h3>
                  </div>
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
                      description:
                        "Auto-delete URLs missing for threshold crawls",
                    },
                  )}
                  {(config.delete_missing as boolean) && (
                    <div className="pl-4 border-l-2 border-destructive/30">
                      <p className="text-xs text-destructive mb-2">
                        Enabling this will automatically delete URLs from the
                        state index after they are missing for the configured
                        number of crawls.
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
                </section>

                <Separator />

                {/* Performance & Infrastructure */}
                <section id="advanced-performance" className="space-y-6">
                  <div className="pb-1.5 border-b border-muted">
                    <h3 className="text-lg font-medium">
                      Performance & Infrastructure
                    </h3>
                  </div>

                  {/* Verbosity */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <Label htmlFor="verbose">Verbosity</Label>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-xs">
                          <p className="text-xs">
                            Verbosity level (0=INFO, 1+=DEBUG)
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                    <Select
                      value={String((config.verbose as number) ?? 0)}
                      onValueChange={(v) =>
                        updateConfig("verbose", parseInt(v))
                      }
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

                  {/* AutoThrottle */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <Label className="text-sm font-medium">
                          Auto-Throttle
                        </Label>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                          </TooltipTrigger>
                          <TooltipContent side="right" className="max-w-xs">
                            <p className="text-xs">
                              Automatically adjust crawl speed based on response
                              times
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <Switch
                        checked={autothrottleEnabled}
                        onCheckedChange={(v) => {
                          const currentThrottle =
                            (config.autothrottle as Record<
                              string,
                              unknown
                            >) || {
                              start_delay: 1.0,
                              max_delay: 10.0,
                            };
                          updateConfig("autothrottle", {
                            ...currentThrottle,
                            enabled: v,
                          });
                        }}
                      />
                    </div>
                    {autothrottleEnabled && (
                      <div className="pl-4 pt-3 space-y-4 border-l-2">
                        {renderField(
                          "autothrottle.start_delay",
                          getPropertySchema("autothrottle.start_delay") || {
                            type: "number",
                            description:
                              "Initial delay between requests in seconds",
                          },
                        )}
                        {renderField(
                          "autothrottle.max_delay",
                          getPropertySchema("autothrottle.max_delay") || {
                            type: "number",
                            description: "Maximum delay between requests",
                          },
                        )}
                      </div>
                    )}
                  </div>

                  {/* Proxy */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <Label className="text-sm font-medium">Proxy</Label>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                          </TooltipTrigger>
                          <TooltipContent side="right" className="max-w-xs">
                            <p className="text-xs">
                              Route requests through a proxy server
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <Switch
                        checked={proxyEnabled}
                        onCheckedChange={(v) => {
                          const currentProxy = (config.proxy as Record<
                            string,
                            unknown
                          >) || {
                            url: "",
                            username: null,
                            password: null,
                          };
                          updateConfig("proxy", {
                            ...currentProxy,
                            enabled: v,
                          });
                        }}
                      />
                    </div>
                    {proxyEnabled && (
                      <div className="pl-4 pt-3 space-y-3 border-l-2">
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5">
                            <Label>Proxy URL</Label>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                              </TooltipTrigger>
                              <TooltipContent side="right" className="max-w-xs">
                                <p className="text-xs">
                                  Scheme determines type
                                  (http/https/socks4/socks5)
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          </div>
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
                                updateConfig(
                                  "proxy.username",
                                  e.target.value || null,
                                )
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
                                updateConfig(
                                  "proxy.password",
                                  e.target.value || null,
                                )
                              }
                              placeholder="Optional"
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </section>

                <Separator />

                {/* Safety Settings */}
                <section id="advanced-safety" className="space-y-4">
                  <div className="pb-1.5 border-b border-muted">
                    <h3 className="text-lg font-medium">Safety Settings</h3>
                  </div>
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
                </section>

                <Separator />

                {/* Storage Settings */}
                <section id="advanced-storage" className="space-y-4">
                  <div className="pb-1.5 border-b border-muted">
                    <h3 className="text-lg font-medium">Storage</h3>
                  </div>
                  <div className="p-3 bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-900 rounded-md">
                    <p className="text-sm text-yellow-800 dark:text-yellow-200 font-medium mb-1">
                      ⚠️ Warning: Do not modify unless necessary
                    </p>
                    <p className="text-xs text-yellow-700 dark:text-yellow-300">
                      The output path is configured for Docker volume mounting.
                      Changing this may cause crawled data to be lost or
                      inaccessible.
                    </p>
                  </div>
                  {renderField(
                    "output",
                    getPropertySchema("output") || {
                      type: "string",
                      description: "Output directory for crawled data",
                    },
                  )}
                </section>
              </section>
            </div>
          </div>
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
    </TooltipProvider>
  );
}
