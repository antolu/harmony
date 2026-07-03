import { useEffect, useState } from "react";
import { Info } from "lucide-react";
import { TagInput } from "emblor-maintained";
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
import { Separator } from "@/shared/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";
import { cn } from "@/shared/lib/utils";

interface ProviderConfigFormProps {
  schema: Record<string, unknown>;
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
}

type JsonSchemaProp = Record<string, unknown>;

interface ResolvedField {
  key: string;
  schema: JsonSchemaProp;
  isRequired: boolean;
  optionalModel: boolean;
}

interface Section {
  id: string;
  title: string;
  description?: string;
  fields: ResolvedField[];
}

function extractRef(prop: JsonSchemaProp): string | undefined {
  if (typeof prop.$ref === "string") return prop.$ref;
  const anyOf = prop.anyOf as JsonSchemaProp[] | undefined;
  const refOption = anyOf?.find((option) => typeof option.$ref === "string");
  return refOption?.$ref as string | undefined;
}

function isOptionalModelRef(prop: JsonSchemaProp): boolean {
  const anyOf = prop.anyOf as JsonSchemaProp[] | undefined;
  if (!anyOf) return false;
  const hasNull = anyOf.some((option) => option.type === "null");
  const hasRef = anyOf.some((option) => typeof option.$ref === "string");
  return hasNull && hasRef;
}

function resolveFields(schema: Record<string, unknown>): ResolvedField[] {
  const properties = (schema.properties ?? {}) as Record<
    string,
    JsonSchemaProp
  >;
  const defs = (schema.$defs ?? {}) as Record<string, JsonSchemaProp>;
  const required = (schema.required ?? []) as string[];

  return Object.entries(properties).map(([key, prop]) => {
    const ref = extractRef(prop);
    let resolved = prop;
    if (ref) {
      const defName = ref.replace("#/$defs/", "");
      const def = defs[defName];
      resolved = def ? { ...def, ...prop, $defs: defs } : prop;
    } else if (defs && Object.keys(defs).length > 0) {
      resolved = { ...prop, $defs: defs };
    }
    return {
      key,
      schema: resolved,
      isRequired: required.includes(key),
      optionalModel: isOptionalModelRef(prop),
    };
  });
}

function isNestedModel(field: ResolvedField): boolean {
  return field.schema.type === "object" && !!field.schema.properties;
}

function buildSections(fields: ResolvedField[]): Section[] {
  const generalFields = fields.filter((f) => !isNestedModel(f));
  const modelFields = fields.filter(isNestedModel);

  const sections: Section[] = [];
  if (generalFields.length > 0) {
    sections.push({ id: "general", title: "General", fields: generalFields });
  }
  for (const field of modelFields) {
    sections.push({
      id: field.key,
      title: (field.schema.title as string) || field.key,
      description: field.schema.description as string | undefined,
      fields: [field],
    });
  }
  return sections;
}

function getDefaultValue(propSchema: JsonSchemaProp): unknown {
  if ("default" in propSchema) return propSchema.default;
  const type = propSchema.type as string | undefined;
  if (type === "array") return [];
  if (type === "boolean") return false;
  if (type === "integer" || type === "number") return 0;
  return "";
}

function LabelWithTooltip({
  htmlFor,
  label,
  description,
  required,
}: {
  htmlFor?: string;
  label: string;
  description?: string;
  required?: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <Label htmlFor={htmlFor}>
        {label}
        {required && <span className="text-destructive">*</span>}
      </Label>
      {description && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
          </TooltipTrigger>
          <TooltipContent side="right" className="max-w-xs">
            <p className="text-xs">{description}</p>
          </TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}

function RequiredError({
  touched,
  isRequired,
  fieldValue,
}: {
  touched: boolean;
  isRequired: boolean;
  fieldValue: unknown;
}) {
  const isEmpty =
    fieldValue === undefined || fieldValue === null || fieldValue === "";
  if (!(touched && isRequired && isEmpty)) return null;
  return (
    <p className="text-xs text-destructive mt-1">This field is required</p>
  );
}

function ArrayField({
  field,
  fieldValue,
  onChange,
  onTouch,
  touched,
}: {
  field: ResolvedField;
  fieldValue: string[];
  onChange: (next: string[]) => void;
  onTouch: () => void;
  touched: boolean;
}) {
  const [activeTagIndex, setActiveTagIndex] = useState<number | null>(null);

  const schemaDefault = field.schema.default;
  const defaultItems = Array.isArray(schemaDefault)
    ? (schemaDefault as string[])
    : [];
  const showDefaults = fieldValue.length === 0 && defaultItems.length > 0;

  const items = fieldValue.map((item, index) => ({
    id: `${field.key}-${index}`,
    text: item,
  }));

  return (
    <div className="space-y-2">
      <LabelWithTooltip
        label={(field.schema.title as string) || field.key}
        description={field.schema.description as string | undefined}
        required={field.isRequired}
      />
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
            ? newTags.map((tag) => (typeof tag === "string" ? tag : tag.text))
            : [];
          onChange(values);
        }}
        placeholder="Type and press Enter to add..."
        activeTagIndex={activeTagIndex}
        setActiveTagIndex={setActiveTagIndex}
        delimiterList={["Enter", " ", ","]}
        addOnPaste
        styleClasses={{ input: "h-9", tag: { body: "pl-2 pr-1" } }}
        className="border rounded-md"
        onBlur={onTouch}
      />
      <RequiredError
        touched={touched}
        isRequired={field.isRequired}
        fieldValue={fieldValue.length > 0 ? fieldValue : undefined}
      />
    </div>
  );
}

function StringMapField({
  field,
  fieldValue,
  onChange,
}: {
  field: ResolvedField;
  fieldValue: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
}) {
  const entries = Object.entries(fieldValue);

  const updateEntry = (index: number, newKey: string, newValue: string) => {
    const next = entries.map(([k, v], i) =>
      i === index ? [newKey, newValue] : [k, v],
    );
    onChange(Object.fromEntries(next));
  };

  const removeEntry = (index: number) => {
    onChange(Object.fromEntries(entries.filter((_, i) => i !== index)));
  };

  return (
    <div className="space-y-2">
      <LabelWithTooltip
        label={(field.schema.title as string) || field.key}
        description={field.schema.description as string | undefined}
        required={field.isRequired}
      />
      <div className="space-y-2">
        {entries.map(([k, v], i) => (
          <div key={i} className="flex gap-2">
            <Input
              value={k}
              onChange={(e) => updateEntry(i, e.target.value, v)}
              placeholder="Key"
            />
            <Input
              value={v}
              onChange={(e) => updateEntry(i, k, e.target.value)}
              placeholder="Value"
            />
            <button
              type="button"
              onClick={() => removeEntry(i)}
              className="text-sm text-muted-foreground hover:text-destructive px-2"
            >
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => onChange({ ...fieldValue, "": "" })}
          className="text-sm text-primary hover:underline"
        >
          + Add entry
        </button>
      </div>
    </div>
  );
}

function JsonFallbackField({
  field,
  value,
  onChange,
}: {
  field: ResolvedField;
  value: unknown;
  onChange: (next: unknown) => void;
}) {
  const [text, setText] = useState(() =>
    JSON.stringify(value ?? null, null, 2),
  );
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="space-y-2">
      <LabelWithTooltip
        label={(field.schema.title as string) || field.key}
        description={field.schema.description as string | undefined}
        required={field.isRequired}
      />
      <textarea
        className="w-full font-mono text-xs rounded-md border bg-background p-2 min-h-24"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          try {
            onChange(JSON.parse(e.target.value));
            setError(null);
          } catch {
            setError("Invalid JSON");
          }
        }}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
      <p className="text-xs text-muted-foreground">
        No dedicated editor for this field's structure yet — edit as raw JSON.
      </p>
    </div>
  );
}

function FieldRenderer({
  field,
  value,
  onChange,
  touched,
  onTouch,
}: {
  field: ResolvedField;
  value: unknown;
  onChange: (next: unknown) => void;
  touched: boolean;
  onTouch: () => void;
}) {
  const { schema: propSchema, isRequired, key } = field;
  const type = propSchema.type as string | undefined;
  const enumValues = propSchema.enum as string[] | undefined;
  const label = (propSchema.title as string) || key;
  const description = propSchema.description as string | undefined;
  const defaultValue = getDefaultValue(propSchema);

  if (type === "boolean") {
    return (
      <div className="flex items-center justify-between">
        <LabelWithTooltip
          htmlFor={key}
          label={label}
          description={description}
          required={isRequired}
        />
        <Switch
          id={key}
          checked={(value as boolean) ?? (defaultValue as boolean)}
          onCheckedChange={(checked) => onChange(checked)}
        />
      </div>
    );
  }

  if (enumValues) {
    return (
      <div className="space-y-2">
        <LabelWithTooltip
          htmlFor={key}
          label={label}
          description={description}
          required={isRequired}
        />
        <Select
          value={(value as string) || (defaultValue as string) || ""}
          onValueChange={(v) => onChange(v)}
        >
          <SelectTrigger id={key} onBlur={onTouch}>
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
        <RequiredError
          touched={touched}
          isRequired={isRequired}
          fieldValue={value}
        />
      </div>
    );
  }

  if (
    type === "array" &&
    (propSchema.items as JsonSchemaProp)?.type === "string"
  ) {
    return (
      <ArrayField
        field={field}
        fieldValue={(value as string[]) ?? []}
        onChange={onChange}
        onTouch={onTouch}
        touched={touched}
      />
    );
  }

  if (
    type === "object" &&
    propSchema.additionalProperties &&
    !propSchema.properties
  ) {
    return (
      <StringMapField
        field={field}
        fieldValue={(value as Record<string, string>) ?? {}}
        onChange={onChange}
      />
    );
  }

  if (type === "array" || (type === "object" && !propSchema.properties)) {
    return (
      <JsonFallbackField field={field} value={value} onChange={onChange} />
    );
  }

  if (type === "number" || type === "integer") {
    return (
      <div className="space-y-2">
        <LabelWithTooltip
          htmlFor={key}
          label={label}
          description={description}
          required={isRequired}
        />
        <Input
          id={key}
          type="number"
          step={type === "integer" ? 1 : "any"}
          value={value !== undefined && value !== null ? (value as number) : ""}
          onChange={(e) =>
            onChange(
              type === "integer"
                ? parseInt(e.target.value, 10)
                : parseFloat(e.target.value),
            )
          }
          placeholder={
            defaultValue !== undefined ? String(defaultValue) : undefined
          }
          onBlur={onTouch}
        />
        <RequiredError
          touched={touched}
          isRequired={isRequired}
          fieldValue={value}
        />
      </div>
    );
  }

  const isPassword = propSchema.format === "password";

  return (
    <div className="space-y-2">
      <LabelWithTooltip
        htmlFor={key}
        label={label}
        description={description}
        required={isRequired}
      />
      <Input
        id={key}
        type={isPassword ? "password" : "text"}
        value={(value as string) || ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={
          defaultValue !== undefined ? String(defaultValue) : undefined
        }
        onBlur={onTouch}
      />
      <RequiredError
        touched={touched}
        isRequired={isRequired}
        fieldValue={value}
      />
    </div>
  );
}

function NestedModelSection({
  field,
  value,
  onChange,
}: {
  field: ResolvedField;
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown> | null) => void;
}) {
  const nestedValue = value ?? {};
  if (!field.optionalModel) {
    return (
      <FormFields
        schema={field.schema}
        value={nestedValue}
        onChange={(v) => onChange(v)}
      />
    );
  }

  const enabled = value !== null && value !== undefined;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Label htmlFor={`${field.key}-enabled`}>
          Enable {(field.schema.title as string) || field.key}
        </Label>
        <Switch
          id={`${field.key}-enabled`}
          checked={enabled}
          onCheckedChange={(checked) => onChange(checked ? {} : null)}
        />
      </div>
      {enabled && (
        <FormFields
          schema={field.schema}
          value={nestedValue}
          onChange={(v) => onChange(v)}
        />
      )}
    </div>
  );
}

function FormFields({
  schema,
  value,
  onChange,
}: {
  schema: Record<string, unknown>;
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
}) {
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const fields = resolveFields(schema);

  const updateField = (key: string, fieldValue: unknown) => {
    onChange({ ...value, [key]: fieldValue });
  };
  const markTouched = (key: string) =>
    setTouched((prev) => ({ ...prev, [key]: true }));

  return (
    <div className="space-y-4">
      {fields.map((field) =>
        isNestedModel(field) ? (
          <NestedModelSection
            key={field.key}
            field={field}
            value={value[field.key] as Record<string, unknown>}
            onChange={(v) => updateField(field.key, v)}
          />
        ) : (
          <FieldRenderer
            key={field.key}
            field={field}
            value={value[field.key]}
            onChange={(v) => updateField(field.key, v)}
            touched={!!touched[field.key]}
            onTouch={() => markTouched(field.key)}
          />
        ),
      )}
    </div>
  );
}

export function ProviderConfigForm({
  schema,
  value,
  onChange,
}: ProviderConfigFormProps) {
  const fields = resolveFields(schema);
  const sections = buildSections(fields);
  const [activeSection, setActiveSection] = useState(sections[0]?.id);

  useEffect(() => {
    const handleScroll = () => {
      for (const section of sections) {
        const el = document.getElementById(`provider-config-${section.id}`);
        if (el) {
          const rect = el.getBoundingClientRect();
          if (rect.top <= 100 && rect.bottom >= 0) {
            setActiveSection(section.id);
            break;
          }
        }
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateSection = (field: ResolvedField, next: unknown) => {
    onChange({ ...value, [field.key]: next });
  };

  const scrollToSection = (id: string) => {
    const el = document.getElementById(`provider-config-${id}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveSection(id);
    }
  };

  if (sections.length <= 1) {
    return (
      <TooltipProvider>
        {sections.map((section) => (
          <FormFields
            key={section.id}
            schema={{
              properties: Object.fromEntries(
                section.fields.map((f) => [f.key, f.schema]),
              ),
              required: section.fields
                .filter((f) => f.isRequired)
                .map((f) => f.key),
            }}
            value={value}
            onChange={onChange}
          />
        ))}
      </TooltipProvider>
    );
  }

  return (
    <TooltipProvider>
      <div className="flex gap-6">
        <aside className="w-48 sticky top-4 self-start space-y-1 hidden md:block">
          <nav className="space-y-1">
            {sections.map((section) => (
              <button
                key={section.id}
                type="button"
                onClick={() => scrollToSection(section.id)}
                className={cn(
                  "w-full text-left px-3 py-2 rounded-md text-sm font-medium transition-colors",
                  activeSection === section.id
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {section.title}
              </button>
            ))}
          </nav>
        </aside>

        <div className="flex-1 space-y-8">
          {sections.map((section, i) => (
            <div key={section.id}>
              {i > 0 && <Separator className="mb-8" />}
              <section
                id={`provider-config-${section.id}`}
                className="space-y-4"
              >
                <div className="pb-2 border-b">
                  <h2 className="text-xl font-semibold">{section.title}</h2>
                  {section.description && (
                    <p className="text-sm text-muted-foreground mt-1">
                      {section.description}
                    </p>
                  )}
                </div>
                {section.id === "general" ? (
                  <FormFields
                    schema={{
                      properties: Object.fromEntries(
                        section.fields.map((f) => [f.key, f.schema]),
                      ),
                      required: section.fields
                        .filter((f) => f.isRequired)
                        .map((f) => f.key),
                    }}
                    value={value}
                    onChange={onChange}
                  />
                ) : (
                  <NestedModelSection
                    field={section.fields[0]}
                    value={
                      value[section.fields[0].key] as Record<string, unknown>
                    }
                    onChange={(v) => updateSection(section.fields[0], v)}
                  />
                )}
              </section>
            </div>
          ))}
        </div>
      </div>
    </TooltipProvider>
  );
}
