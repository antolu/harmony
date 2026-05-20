import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const SPIDER_TYPES = ["docs", "drupal", "generic"];

interface DomainRoutingPattern {
  pattern: string;
  spider: string;
}

interface DomainRouting {
  exact: Record<string, string>;
  patterns: DomainRoutingPattern[];
  default: string;
}

interface DomainRoutingFormProps {
  routing: DomainRouting;
  onChange: (routing: DomainRouting) => void;
}

export function DomainRoutingForm({
  routing,
  onChange,
}: DomainRoutingFormProps) {
  const exactEntries = Object.entries(routing.exact);

  const addExact = () => {
    onChange({
      ...routing,
      exact: { ...routing.exact, "": "generic" },
    });
  };

  const updateExactDomain = (oldDomain: string, newDomain: string) => {
    const updated: Record<string, string> = {};
    for (const [key, value] of Object.entries(routing.exact)) {
      updated[key === oldDomain ? newDomain : key] = value;
    }
    onChange({ ...routing, exact: updated });
  };

  const updateExactSpider = (domain: string, spider: string) => {
    onChange({
      ...routing,
      exact: { ...routing.exact, [domain]: spider },
    });
  };

  const removeExact = (domain: string) => {
    const updated = { ...routing.exact };
    delete updated[domain];
    onChange({ ...routing, exact: updated });
  };

  const addPattern = () => {
    onChange({
      ...routing,
      patterns: [...routing.patterns, { pattern: "", spider: "generic" }],
    });
  };

  const updatePattern = (
    index: number,
    field: "pattern" | "spider",
    value: string,
  ) => {
    onChange({
      ...routing,
      patterns: routing.patterns.map((p, i) =>
        i === index ? { ...p, [field]: value } : p,
      ),
    });
  };

  const removePattern = (index: number) => {
    onChange({
      ...routing,
      patterns: routing.patterns.filter((_, i) => i !== index),
    });
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium">Exact domain mappings</Label>
          <Button variant="outline" size="sm" onClick={addExact}>
            <Plus className="h-3 w-3 mr-1" />
            Add
          </Button>
        </div>
        {exactEntries.length === 0 && (
          <p className="text-xs text-muted-foreground italic">
            No exact mappings configured
          </p>
        )}
        <div className="space-y-2">
          {exactEntries.map(([domain, spider]) => (
            <div key={domain} className="flex items-center gap-2">
              <Input
                value={domain}
                onChange={(e) => updateExactDomain(domain, e.target.value)}
                placeholder="docs.example.com"
                className="flex-1"
              />
              <Select
                value={spider}
                onValueChange={(v) => updateExactSpider(domain, v)}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SPIDER_TYPES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeExact(domain)}
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium">Pattern-based routing</Label>
          <Button variant="outline" size="sm" onClick={addPattern}>
            <Plus className="h-3 w-3 mr-1" />
            Add
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Regex patterns matched against the domain
        </p>
        {routing.patterns.length === 0 && (
          <p className="text-xs text-muted-foreground italic">
            No pattern rules configured
          </p>
        )}
        <div className="space-y-2">
          {routing.patterns.map((p, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                value={p.pattern}
                onChange={(e) =>
                  updatePattern(index, "pattern", e.target.value)
                }
                placeholder=".*-docs\\..*"
                className="flex-1"
              />
              <Select
                value={p.spider}
                onValueChange={(v) => updatePattern(index, "spider", v)}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SPIDER_TYPES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removePattern(index)}
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-1">
        <Label>Default spider</Label>
        <p className="text-xs text-muted-foreground">
          Used for domains that don't match any rule
        </p>
        <Select
          value={routing.default}
          onValueChange={(v) => onChange({ ...routing, default: v })}
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SPIDER_TYPES.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
