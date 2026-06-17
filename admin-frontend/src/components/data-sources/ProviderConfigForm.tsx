import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

interface ProviderConfigFormProps {
  schema: Record<string, unknown>;
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
}

type JsonSchemaProp = Record<string, unknown>;

function resolveRefs(
  schema: Record<string, unknown>,
): Record<string, JsonSchemaProp> {
  const properties = (schema.properties ?? {}) as Record<
    string,
    JsonSchemaProp
  >;
  const defs = (schema.$defs ?? {}) as Record<string, JsonSchemaProp>;

  const resolved: Record<string, JsonSchemaProp> = {};
  for (const [key, prop] of Object.entries(properties)) {
    const ref = prop.$ref as string | undefined;
    if (ref) {
      const defName = ref.replace("#/$defs/", "");
      const def = defs[defName];
      resolved[key] = def ? { ...def, ...prop } : prop;
    } else {
      resolved[key] = prop;
    }
  }
  return resolved;
}

function isPasswordField(propSchema: JsonSchemaProp): boolean {
  return propSchema.format === "password";
}

function isTextareaHint(propSchema: JsonSchemaProp): boolean {
  const description = propSchema.description as string | undefined;
  if (description?.toLowerCase().includes("multiline")) return true;
  return propSchema.format === "textarea";
}

export function ProviderConfigForm({
  schema,
  value,
  onChange,
}: ProviderConfigFormProps) {
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const properties = resolveRefs(schema);
  const required = (schema.required ?? []) as string[];

  const markTouched = (key: string) =>
    setTouched((prev) => ({ ...prev, [key]: true }));

  const updateField = (key: string, fieldValue: unknown) => {
    onChange({ ...value, [key]: fieldValue });
  };

  const renderRequiredError = (key: string, isRequired: boolean) => {
    const fieldValue = value[key];
    const isEmpty =
      fieldValue === undefined || fieldValue === null || fieldValue === "";
    if (touched[key] && isRequired && isEmpty) {
      return (
        <p className="text-xs text-destructive mt-1">This field is required</p>
      );
    }
    return null;
  };

  const renderLabel = (
    key: string,
    propSchema: JsonSchemaProp,
    isRequired: boolean,
  ) => {
    const label = (propSchema.title as string) || key;
    return (
      <Label htmlFor={key}>
        {label}
        {isRequired && <span className="text-destructive">*</span>}
      </Label>
    );
  };

  const renderDescription = (propSchema: JsonSchemaProp) => {
    const description = propSchema.description as string | undefined;
    if (!description) return null;
    return <p className="text-xs text-muted-foreground mt-1">{description}</p>;
  };

  const renderField = (key: string, propSchema: JsonSchemaProp) => {
    const isRequired = required.includes(key);
    const type = propSchema.type as string | undefined;
    const enumValues = propSchema.enum as string[] | undefined;
    const fieldValue = value[key];

    if (type === "object" && propSchema.properties) {
      const nestedValue =
        (fieldValue as Record<string, unknown> | undefined) ?? {};
      return (
        <Accordion key={key} type="single" collapsible className="w-full">
          <AccordionItem value={key}>
            <AccordionTrigger>
              {(propSchema.title as string) || key}
            </AccordionTrigger>
            <AccordionContent className="space-y-4 p-2">
              <ProviderConfigForm
                schema={propSchema}
                value={nestedValue}
                onChange={(nested) => updateField(key, nested)}
              />
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      );
    }

    if (type === "boolean") {
      return (
        <div key={key} className="flex items-center justify-between">
          {renderLabel(key, propSchema, isRequired)}
          <Switch
            id={key}
            checked={(fieldValue as boolean) || false}
            onCheckedChange={(checked) => updateField(key, checked)}
          />
        </div>
      );
    }

    if (enumValues) {
      return (
        <div key={key} className="space-y-2">
          {renderLabel(key, propSchema, isRequired)}
          <Select
            value={(fieldValue as string) || ""}
            onValueChange={(v) => updateField(key, v)}
          >
            <SelectTrigger id={key} onBlur={() => markTouched(key)}>
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
          {renderDescription(propSchema)}
          {renderRequiredError(key, isRequired)}
        </div>
      );
    }

    if (
      type === "array" &&
      (propSchema.items as JsonSchemaProp)?.type === "string"
    ) {
      const items = (fieldValue as string[] | undefined) ?? [];
      return (
        <div key={key} className="space-y-2">
          {renderLabel(key, propSchema, isRequired)}
          <Textarea
            id={key}
            value={items.join("\n")}
            onChange={(e) =>
              updateField(
                key,
                e.target.value === "" ? [] : e.target.value.split("\n"),
              )
            }
            onBlur={() => markTouched(key)}
          />
          {renderDescription(propSchema)}
          {renderRequiredError(key, isRequired)}
        </div>
      );
    }

    if (type === "number" || type === "integer") {
      return (
        <div key={key} className="space-y-2">
          {renderLabel(key, propSchema, isRequired)}
          <Input
            id={key}
            type="number"
            value={
              fieldValue !== undefined && fieldValue !== null
                ? (fieldValue as number)
                : ""
            }
            onChange={(e) =>
              updateField(
                key,
                type === "integer"
                  ? parseInt(e.target.value, 10)
                  : parseFloat(e.target.value),
              )
            }
            onBlur={() => markTouched(key)}
          />
          {renderDescription(propSchema)}
          {renderRequiredError(key, isRequired)}
        </div>
      );
    }

    if (isPasswordField(propSchema)) {
      return (
        <div key={key} className="space-y-2">
          {renderLabel(key, propSchema, isRequired)}
          <Input
            id={key}
            type="password"
            value={(fieldValue as string) || ""}
            onChange={(e) => updateField(key, e.target.value)}
            onBlur={() => markTouched(key)}
          />
          {renderDescription(propSchema)}
          {renderRequiredError(key, isRequired)}
        </div>
      );
    }

    if (isTextareaHint(propSchema)) {
      return (
        <div key={key} className="space-y-2">
          {renderLabel(key, propSchema, isRequired)}
          <Textarea
            id={key}
            value={(fieldValue as string) || ""}
            onChange={(e) => updateField(key, e.target.value)}
            onBlur={() => markTouched(key)}
          />
          {renderDescription(propSchema)}
          {renderRequiredError(key, isRequired)}
        </div>
      );
    }

    return (
      <div key={key} className="space-y-2">
        {renderLabel(key, propSchema, isRequired)}
        <Input
          id={key}
          value={(fieldValue as string) || ""}
          onChange={(e) => updateField(key, e.target.value)}
          onBlur={() => markTouched(key)}
        />
        {renderDescription(propSchema)}
        {renderRequiredError(key, isRequired)}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {Object.entries(properties).map(([key, propSchema]) =>
        renderField(key, propSchema),
      )}
    </div>
  );
}
