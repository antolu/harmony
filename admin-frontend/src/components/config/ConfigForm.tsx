import { useState, useEffect } from "react";
import { stringify as yamlStringify, parse as yamlParse } from "yaml";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
  const [esValidating, setEsValidating] = useState(false);
  const [esValidation, setEsValidation] = useState<{
    valid: boolean;
    message?: string;
    clusterName?: string;
  } | null>(null);

  useEffect(() => {
    try {
      setYamlContent(yamlStringify(config));
      setYamlError(null);
    } catch {
      // Keep existing content on error
    }
  }, [config]);

  const handleYamlChange = (value: string) => {
    setYamlContent(value);
    try {
      const parsed = yamlParse(value);
      onChange(parsed);
      setYamlError(null);
    } catch (e) {
      setYamlError(e instanceof Error ? e.message : "Invalid YAML");
    }
  };

  const updateConfig = (path: string, value: unknown) => {
    const newConfig = { ...config };
    const parts = path.split(".");
    let current: Record<string, unknown> = newConfig;

    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]]) {
        current[parts[i]] = {};
      }
      current = current[parts[i]] as Record<string, unknown>;
    }

    current[parts[parts.length - 1]] = value;
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
    const description = propSchema.description as string | undefined;
    const enumValues = propSchema.enum as string[] | undefined;
    const defaultValue = getDefaultValue(propSchema);

    // Handle enum fields with select dropdown
    if (enumValues) {
      return (
        <div key={path} className="space-y-2">
          <Label htmlFor={path}>{path.split(".").pop()}</Label>
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
            <Label htmlFor={path}>{path.split(".").pop()}</Label>
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
      const items = ((value as unknown[]) || []).map((item, index) => ({
        id: `${path}-${index}`,
        text: String(item),
      }));
      return (
        <div key={path} className="space-y-2">
          <Label>{path.split(".").pop()}</Label>
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
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
          <Label htmlFor={path}>{path.split(".").pop()}</Label>
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
        <Label htmlFor={path}>{path.split(".").pop()}</Label>
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

  return (
    <Tabs defaultValue="form">
      <div className="flex items-center justify-between mb-4">
        <TabsList>
          <TabsTrigger value="form">Form</TabsTrigger>
          <TabsTrigger value="yaml">YAML</TabsTrigger>
        </TabsList>

        <div className="flex gap-2">
          <Button onClick={onSave} disabled={isSaving || !!yamlError}>
            {isSaving ? "Saving..." : "Save"}
          </Button>
          {onRun && (
            <Button
              onClick={onRun}
              disabled={isRunning || !!yamlError}
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

        {/* Domain Settings */}
        <Accordion type="single" collapsible>
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
            </AccordionContent>
          </AccordionItem>

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
            </AccordionContent>
          </AccordionItem>

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
              <p className="text-sm text-destructive mb-2">{yamlError}</p>
            )}
            <Textarea
              value={yamlContent}
              onChange={(e) => handleYamlChange(e.target.value)}
              className="font-mono min-h-[500px]"
            />
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
}
