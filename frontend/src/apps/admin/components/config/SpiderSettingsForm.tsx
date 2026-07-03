import { useState } from "react";
import { Switch } from "@/shared/components/ui/switch";
import { Label } from "@/shared/components/ui/label";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/shared/components/ui/tabs";
import { TagInput } from "emblor-maintained";

interface DocsSpiderSettings {
  skip_versions: boolean;
  version_allowlist: string[];
  deny_patterns: string[];
}

interface DrupalSpiderSettings {
  deny_patterns: string[];
}

interface GenericSpiderSettings {
  deny_patterns: string[];
}

interface SpiderSettings {
  docs: DocsSpiderSettings;
  drupal: DrupalSpiderSettings;
  generic: GenericSpiderSettings;
}

interface SpiderSettingsFormProps {
  settings: SpiderSettings;
  onChange: (settings: SpiderSettings) => void;
}

const DOCS_DENY_DEFAULTS = [
  "/_sources/",
  "\\.rst\\.txt$",
  "/genindex\\.html$",
  "/py-modindex\\.html$",
  "/search\\.html$",
  "/searchindex\\.js$",
  "/_modules/",
];

const DRUPAL_DENY_DEFAULTS = ["/node/\\d+"];

function DenyPatternsField({
  value,
  defaults,
  onChange,
}: {
  value: string[];
  defaults: string[];
  onChange: (patterns: string[]) => void;
}) {
  const [activeTagIndex, setActiveTagIndex] = useState<number | null>(null);
  const tags = value.map((item, index) => ({ id: `${index}`, text: item }));
  const showDefaults = value.length === 0 && defaults.length > 0;

  return (
    <div className="space-y-1">
      <Label>Deny patterns</Label>
      <p className="text-xs text-muted-foreground">
        Regex patterns for URLs to skip
      </p>
      {showDefaults && (
        <div className="flex flex-wrap gap-1">
          {defaults.map((tag, i) => (
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
        tags={tags}
        setTags={(newTags) => {
          const values = Array.isArray(newTags)
            ? newTags.map((tag) => (typeof tag === "string" ? tag : tag.text))
            : [];
          onChange(values);
        }}
        placeholder="e.g. /_sources/"
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

export function SpiderSettingsForm({
  settings,
  onChange,
}: SpiderSettingsFormProps) {
  const [versionAllowlistActiveTag, setVersionAllowlistActiveTag] = useState<
    number | null
  >(null);

  return (
    <Tabs defaultValue="docs">
      <TabsList>
        <TabsTrigger value="docs">Docs</TabsTrigger>
        <TabsTrigger value="drupal">Drupal</TabsTrigger>
        <TabsTrigger value="generic">Generic</TabsTrigger>
      </TabsList>

      <TabsContent value="docs" className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <div>
            <Label>Skip versioned paths</Label>
            <p className="text-xs text-muted-foreground">
              Exclude versioned URL segments
            </p>
          </div>
          <Switch
            checked={settings.docs.skip_versions}
            onCheckedChange={(v) =>
              onChange({
                ...settings,
                docs: { ...settings.docs, skip_versions: v },
              })
            }
          />
        </div>

        {settings.docs.skip_versions && (
          <div className="space-y-1">
            <Label>Version allowlist</Label>
            <p className="text-xs text-muted-foreground">
              Version identifiers to allow (e.g. stable, latest)
            </p>
            <TagInput
              tags={settings.docs.version_allowlist.map((item, i) => ({
                id: `${i}`,
                text: item,
              }))}
              setTags={(newTags) => {
                const values = Array.isArray(newTags)
                  ? newTags.map((tag) =>
                      typeof tag === "string" ? tag : tag.text,
                    )
                  : [];
                onChange({
                  ...settings,
                  docs: { ...settings.docs, version_allowlist: values },
                });
              }}
              placeholder="e.g. stable, latest, current"
              activeTagIndex={versionAllowlistActiveTag}
              setActiveTagIndex={setVersionAllowlistActiveTag}
              delimiterList={[" ", ","]}
              addOnPaste
              styleClasses={{ input: "h-9", tag: { body: "pl-2 pr-1" } }}
              className="border rounded-md"
            />
          </div>
        )}

        <DenyPatternsField
          value={settings.docs.deny_patterns}
          defaults={DOCS_DENY_DEFAULTS}
          onChange={(v) =>
            onChange({
              ...settings,
              docs: { ...settings.docs, deny_patterns: v },
            })
          }
        />
      </TabsContent>

      <TabsContent value="drupal" className="space-y-3 pt-2">
        <DenyPatternsField
          value={settings.drupal.deny_patterns}
          defaults={DRUPAL_DENY_DEFAULTS}
          onChange={(v) =>
            onChange({
              ...settings,
              drupal: { ...settings.drupal, deny_patterns: v },
            })
          }
        />
      </TabsContent>

      <TabsContent value="generic" className="space-y-3 pt-2">
        <DenyPatternsField
          value={settings.generic.deny_patterns}
          defaults={[]}
          onChange={(v) =>
            onChange({
              ...settings,
              generic: { ...settings.generic, deny_patterns: v },
            })
          }
        />
      </TabsContent>
    </Tabs>
  );
}
