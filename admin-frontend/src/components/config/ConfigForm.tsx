import { useState, useEffect } from 'react'
import { stringify as yamlStringify, parse as yamlParse } from 'yaml'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'

interface ConfigFormProps {
  schema: Record<string, unknown>
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  onSave: () => void
  onRun?: () => void
  isSaving?: boolean
  isRunning?: boolean
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
  const [yamlContent, setYamlContent] = useState('')
  const [yamlError, setYamlError] = useState<string | null>(null)

  useEffect(() => {
    try {
      setYamlContent(yamlStringify(config))
      setYamlError(null)
    } catch {
      // Keep existing content on error
    }
  }, [config])

  const handleYamlChange = (value: string) => {
    setYamlContent(value)
    try {
      const parsed = yamlParse(value)
      onChange(parsed)
      setYamlError(null)
    } catch (e) {
      setYamlError(e instanceof Error ? e.message : 'Invalid YAML')
    }
  }

  const updateConfig = (path: string, value: unknown) => {
    const newConfig = { ...config }
    const parts = path.split('.')
    let current: Record<string, unknown> = newConfig

    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]]) {
        current[parts[i]] = {}
      }
      current = current[parts[i]] as Record<string, unknown>
    }

    current[parts[parts.length - 1]] = value
    onChange(newConfig)
  }

  const getPropertySchema = (path: string): Record<string, unknown> | undefined => {
    const properties = (schema as Record<string, unknown>).properties as Record<string, unknown>
    if (!properties) return undefined

    const parts = path.split('.')
    let current = properties

    for (const part of parts) {
      if (!current[part]) return undefined
      const prop = current[part] as Record<string, unknown>
      if (prop.properties) {
        current = prop.properties as Record<string, unknown>
      } else {
        return prop
      }
    }
    return current as Record<string, unknown>
  }

  const renderField = (path: string, propSchema: Record<string, unknown>) => {
    const value = path.split('.').reduce((obj, key) => {
      return obj && typeof obj === 'object' ? (obj as Record<string, unknown>)[key] : undefined
    }, config as unknown)

    const type = propSchema.type as string
    const description = propSchema.description as string | undefined

    if (type === 'boolean') {
      return (
        <div key={path} className="flex items-center justify-between">
          <div>
            <Label htmlFor={path}>{path.split('.').pop()}</Label>
            {description && (
              <p className="text-xs text-muted-foreground">{description}</p>
            )}
          </div>
          <Switch
            id={path}
            checked={value as boolean || false}
            onCheckedChange={(v) => updateConfig(path, v)}
          />
        </div>
      )
    }

    if (type === 'array') {
      const items = value as unknown[] || []
      return (
        <div key={path} className="space-y-2">
          <Label>{path.split('.').pop()}</Label>
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
          <Textarea
            value={items.join('\n')}
            onChange={(e) => updateConfig(path, e.target.value.split('\n').filter(Boolean))}
            placeholder="One item per line"
            rows={3}
          />
        </div>
      )
    }

    if (type === 'integer' || type === 'number') {
      return (
        <div key={path} className="space-y-2">
          <Label htmlFor={path}>{path.split('.').pop()}</Label>
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
          <Input
            id={path}
            type="number"
            value={value as number || ''}
            onChange={(e) => updateConfig(path, type === 'integer' ? parseInt(e.target.value) : parseFloat(e.target.value))}
          />
        </div>
      )
    }

    return (
      <div key={path} className="space-y-2">
        <Label htmlFor={path}>{path.split('.').pop()}</Label>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
        <Input
          id={path}
          value={value as string || ''}
          onChange={(e) => updateConfig(path, e.target.value)}
        />
      </div>
    )
  }

  return (
    <Tabs defaultValue="form">
      <div className="flex items-center justify-between mb-4">
        <TabsList>
          <TabsTrigger value="form">Form</TabsTrigger>
          <TabsTrigger value="yaml">YAML</TabsTrigger>
        </TabsList>

        <div className="flex gap-2">
          <Button onClick={onSave} disabled={isSaving || !!yamlError}>
            {isSaving ? 'Saving...' : 'Save'}
          </Button>
          {onRun && (
            <Button onClick={onRun} disabled={isRunning || !!yamlError} variant="secondary">
              {isRunning ? 'Starting...' : 'Run'}
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
            {renderField('start_urls', getPropertySchema('start_urls') || { type: 'array', description: 'URLs to start crawling from' })}
            {renderField('output', getPropertySchema('output') || { type: 'string', description: 'Output directory' })}
            {renderField('max_depth', getPropertySchema('max_depth') || { type: 'integer', description: 'Maximum crawl depth' })}
            {renderField('delay', getPropertySchema('delay') || { type: 'number', description: 'Delay between requests' })}
            {renderField('concurrent', getPropertySchema('concurrent') || { type: 'integer', description: 'Concurrent requests' })}
          </CardContent>
        </Card>

        {/* Domain Settings */}
        <Accordion type="single" collapsible>
          <AccordionItem value="domains">
            <AccordionTrigger>Domain Settings</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              {renderField('allowed_domains', getPropertySchema('allowed_domains') || { type: 'array', description: 'Additional allowed domain patterns' })}
              {renderField('forbidden_domains', getPropertySchema('forbidden_domains') || { type: 'array', description: 'Domain patterns to exclude' })}
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="safety">
            <AccordionTrigger>Safety Settings</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              {renderField('safe_mode', getPropertySchema('safe_mode') || { type: 'boolean', description: 'Enable strict safety checks' })}
              {renderField('dry_run', getPropertySchema('dry_run') || { type: 'boolean', description: 'Log URLs without requesting' })}
              {renderField('allow_mutations', getPropertySchema('allow_mutations') || { type: 'boolean', description: 'Allow mutation endpoints' })}
              {renderField('ignore_robots', getPropertySchema('ignore_robots') || { type: 'boolean', description: 'Ignore robots.txt' })}
              {renderField('safety_allow_list', getPropertySchema('safety_allow_list') || { type: 'array', description: 'URL patterns to always allow' })}
              {renderField('safety_deny_list', getPropertySchema('safety_deny_list') || { type: 'array', description: 'URL patterns to always deny' })}
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="state">
            <AccordionTrigger>State Tracking</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              {renderField('es_state_host', getPropertySchema('es_state_host') || { type: 'string', description: 'Elasticsearch host for state tracking' })}
              {renderField('es_state_index', getPropertySchema('es_state_index') || { type: 'string', description: 'State index name' })}
              {renderField('recrawl_mode', getPropertySchema('recrawl_mode') || { type: 'string', description: 'Re-crawl mode (full/age-based)' })}
              {renderField('max_age_days', getPropertySchema('max_age_days') || { type: 'integer', description: 'Max age for re-crawling' })}
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="throttle">
            <AccordionTrigger>Throttling</AccordionTrigger>
            <AccordionContent className="space-y-4 p-4">
              {renderField('autothrottle_enabled', getPropertySchema('autothrottle_enabled') || { type: 'boolean', description: 'Enable auto-throttle' })}
              {renderField('autothrottle_start_delay', getPropertySchema('autothrottle_start_delay') || { type: 'number', description: 'Start delay' })}
              {renderField('autothrottle_max_delay', getPropertySchema('autothrottle_max_delay') || { type: 'number', description: 'Max delay' })}
              {renderField('download_timeout', getPropertySchema('download_timeout') || { type: 'number', description: 'Download timeout' })}
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
  )
}
