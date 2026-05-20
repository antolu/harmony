# Model Management Frontend Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose hybrid search pipeline tuning and model management in the admin frontend: extend the setup wizard with model selection steps, add a Search Pipeline card to `/settings`, and add a new `/models` page for Ollama/LiteLLM model management with re-embed triggering.

**Architecture:** Three independent UI additions sharing a common `modelSettingsApi` client module. All model management calls go to `/api/settings/models` and `/api/models/ollama/*`. Pipeline tuning calls the existing `/settings/pipeline` endpoint. React Query handles caching and invalidation. SSE is used for Ollama pull progress (same pattern as job log streaming).

**Tech Stack:** React 18, TypeScript, React Query, Axios, Radix UI, Tailwind CSS, Lucide icons — all existing dependencies, no new packages needed.

---

## New API Client: `admin-frontend/src/api/models.ts`

All backend calls for model settings and Ollama management. No other file should call these endpoints directly.

```typescript
import axios from './client'  // existing axios instance

export interface ModelSettings {
  embedding_provider: 'ollama' | 'litellm'
  embedding_model: string
  reranker_provider: 'ollama' | 'litellm'
  reranker_model: string
  llm_provider: 'ollama' | 'litellm'
  llm_model: string
  embedding_model_changed_since_last_embed: 'true' | 'false'
}

export interface OllamaModel {
  name: string
  size: number
  modified_at: string
}

export const modelsApi = {
  getSettings: (): Promise<ModelSettings> =>
    axios.get('/api/settings/models').then(r => r.data),

  updateSettings: (patch: Partial<ModelSettings>): Promise<ModelSettings> =>
    axios.patch('/api/settings/models', patch).then(r => r.data),

  validateModel: (model: string, provider: string, model_type: string) =>
    axios.post('/api/settings/models/validate', { model, provider, model_type })
      .then(r => r.data as { valid: boolean; error?: string }),

  listOllamaModels: (): Promise<{ models: OllamaModel[] }> =>
    axios.get('/api/models/ollama').then(r => r.data),

  deleteOllamaModel: (name: string): Promise<{ deleted: boolean }> =>
    axios.delete(`/api/models/ollama/${encodeURIComponent(name)}`).then(r => r.data),

  // Returns an EventSource — caller is responsible for cleanup
  pullOllamaModel: (name: string): EventSource =>
    new EventSource(`/api/models/ollama/pull?name=${encodeURIComponent(name)}`),
    // Note: pull uses POST in backend — implement via fetch SSE, not EventSource
}

// Pull uses POST+SSE — use fetch with ReadableStream
export async function* pullOllamaModelStream(name: string): AsyncGenerator<{status: string; completed?: number; total?: number}> {
  const response = await fetch('/api/models/ollama/pull', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        yield JSON.parse(line.slice(6))
      }
    }
  }
}
```

---

## Section 1: Setup Wizard Extension

### File: `admin-frontend/src/pages/SetupWizard.tsx` (modify existing)

Add Steps 3, 4, 5 after the existing Elasticsearch (step 1) and Redis (step 2) steps.

**Step structure** (shared across steps 3–5):

```
┌─────────────────────────────────────────────────────┐
│  Step 3 of 5 — Embedding Model                      │
│                                                     │
│  Provider                                           │
│  [● Ollama (local)]  [ LiteLLM ]                   │
│                                                     │
│  Model                                              │
│  [qwen3-embedding:0.6b              ▼]  [🗑]       │  ← Ollama: dropdown
│                                                     │
│  Pull a new model                                   │
│  [_____________________________]  [Pull]            │
│  ████████░░░░░░░░ 52%  Pulling manifest...         │  ← shown during pull
│                                                     │
│  [← Back]  [Skip — use default]  [Next →]          │
└─────────────────────────────────────────────────────┘
```

For LiteLLM provider, replace the dropdown+pull section with:
```
  Model string
  [openai/text-embedding-3-small        ]  [Validate]
  ✓ Model is valid                                     ← or ✗ error message
```

**State added to wizard:**
```typescript
interface WizardModelStep {
  provider: 'ollama' | 'litellm'
  model: string
  validated: boolean
}

// Added to existing wizard state:
embeddingStep: WizardModelStep
rerankerStep: WizardModelStep
llmStep: WizardModelStep
```

Each step's "Next" button is enabled when:
- Ollama provider: a model is selected from the dropdown (non-empty)
- LiteLLM provider: `validated === true`
- Or user clicks "Skip — use default"

**On wizard completion**, the existing `setupApi.complete()` call is extended to pass model settings:
```typescript
await setupApi.complete({
  elasticsearch_url: esUrl,
  redis_url: redisUrl,
  embedding_provider: embeddingStep.provider,
  embedding_model: embeddingStep.model,
  reranker_provider: rerankerStep.provider,
  reranker_model: rerankerStep.model,
  llm_provider: llmStep.provider,
  llm_model: llmStep.model,
})
```

**Subcomponent: `ModelStepForm`** — reusable component used in all three model steps and on the `/models` page. Props:

```typescript
interface ModelStepFormProps {
  label: string                    // "Embedding Model" | "Reranker Model" | "LLM Model"
  provider: 'ollama' | 'litellm'
  model: string
  onProviderChange: (p: 'ollama' | 'litellm') => void
  onModelChange: (m: string) => void
  onValidated: (valid: boolean) => void
  modelType: 'embedding' | 'reranker' | 'llm'
}
```

File: `admin-frontend/src/components/ModelStepForm.tsx`

Internally uses:
- `useQuery(['ollamaModels'], modelsApi.listOllamaModels)` for Ollama dropdown
- Local state for pull input, pull progress, validate state
- `pullOllamaModelStream()` for pull SSE

---

## Section 2: Settings Page — Search Pipeline Card

### File: `admin-frontend/src/pages/Settings.tsx` (modify existing)

Add a new card at the top of the page, before the Elasticsearch Indices section.

```
┌─────────────────────────────────────────────────────────┐
│  Search Pipeline                                        │
│                                                         │
│  Vector Search            Reranker                      │
│  [● ON ]                  [● ON ]  (greyed if VS off)  │
│                                                         │
│  Keyword candidates    Vector top-k    Results          │
│  [     50     ]        [     20    ]   [    5   ]       │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**
- `useQuery(['pipelineConfig'], () => fetch('/settings/pipeline').then(r => r.json()))`
- Pill toggle component (new): `<PillToggle value={bool} onChange={fn} disabled={bool} />`
  - Renders as a pill-shaped button with filled/outlined state for on/off
  - `disabled` prop renders greyed with `cursor-not-allowed`
- Numeric inputs: `onBlur` fires `PATCH /settings/pipeline` with the changed field
- Toggles: `onClick` fires `PATCH /settings/pipeline` immediately
- Optimistic update: update React Query cache on change, rollback on error with toast

**`PillToggle` component** — new shared component since it's used here and on `/models`.

File: `admin-frontend/src/components/PillToggle.tsx`

```typescript
interface PillToggleProps {
  value: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
  labelOn?: string   // default "ON"
  labelOff?: string  // default "OFF"
}
```

Styles: `rounded-full px-4 py-1 text-sm font-medium transition-colors`. On: `bg-primary text-primary-foreground`. Off: `border border-input bg-background text-muted-foreground`.

---

## Section 3: New `/models` Page

### New file: `admin-frontend/src/pages/Models.tsx`

Three cards: Embedding Model, Reranker Model, LLM Model.

```
┌──────────────────────────────────┐  ┌──────────────────────────────────┐
│  Embedding Model                 │  │  Reranker Model                  │
│                                  │  │                                  │
│  Provider                        │  │  Provider                        │
│  [● Ollama]  [ LiteLLM]         │  │  [● Ollama]  [ LiteLLM]         │
│                                  │  │                                  │
│  [qwen3-embedding:0.6b  ▼]  [🗑]│  │  [bge-reranker-v2-m3    ▼]  [🗑]│
│                                  │  │                                  │
│  Pull new model                  │  │  Pull new model                  │
│  [________________]  [Pull]      │  │  [________________]  [Pull]      │
│                                  │  │                                  │
│  ┌─────────────────────────────┐ │  └──────────────────────────────────┘
│  │ ⚠ Embedding model changed — │ │
│  │ vector search disabled until │ │
│  │ re-embed completes.          │ │
│  └─────────────────────────────┘ │
│                                  │
│  [Re-embed all documents]        │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│  LLM Model                       │
│  Provider                        │
│  [ Ollama]  [● LiteLLM]         │
│                                  │
│  [gemini/gemini-3-flash-preview] │  [Validate]
│  ✓ Model is valid                │
└──────────────────────────────────┘
```

**Data flow:**
- On load: `useQuery(['modelSettings'], modelsApi.getSettings)` + `useQuery(['ollamaModels'], modelsApi.listOllamaModels)`
- Each card uses `ModelStepForm` component (shared with wizard)
- Save button per card (not auto-save — model changes are significant): calls `modelsApi.updateSettings()`
- On save success: invalidate `['modelSettings']`, show toast "Saved. Changes take effect immediately for new searches."

**Re-embed button:**
- Visible on Embedding Model card always
- If `embedding_model_changed_since_last_embed === 'true'`: yellow `Alert` banner above the button
- On click: `POST /api/jobs/embed` → on success navigate to `/jobs/{jobId}`
- Button label: "Re-embed all documents"
- Uses existing `jobsApi.startEmbedJob()` (new function in existing `admin-frontend/src/api/jobs.ts`)

**Pull progress UI** (within `ModelStepForm`):
- Local state: `pullModel: string`, `pulling: boolean`, `pullProgress: {status, completed, total} | null`, `pullError: string | null`
- On Pull click: sets `pulling = true`, calls `pullOllamaModelStream(pullModel)`, updates `pullProgress` on each event
- Shows `<Progress value={completed/total*100} />` + status text while pulling
- On completion: invalidates `['ollamaModels']`, clears pull input, sets `pulling = false`
- On error (Ollama returns error status in stream): sets `pullError`, shows inline red text

**Delete model:**
- Trash icon button next to the dropdown
- `AlertDialog` confirmation: "Delete {name}? This cannot be undone."
- On confirm: `modelsApi.deleteOllamaModel(name)`, invalidates `['ollamaModels']`
- If deleted model is the currently selected model: clear selection (shows placeholder)

---

## Section 4: Sidebar + Routing

### `admin-frontend/src/components/Sidebar.tsx` (modify)

Add "Models" entry between Dashboard and Crawler:

```typescript
{ path: '/models', label: 'Models', icon: Cpu }  // Cpu from lucide-react
```

### `admin-frontend/src/App.tsx` (modify)

Add route:
```typescript
<Route path="/models" element={<Models />} />
```

---

## Section 5: Jobs API Extension

### `admin-frontend/src/api/jobs.ts` (modify existing)

Add:
```typescript
startEmbedJob: (): Promise<Job> =>
  fetch('/api/jobs/embed', { method: 'POST' }).then(r => r.json()),
```

The returned `Job` has `type: 'embed'`. The existing `JobDetail` page handles it generically (shows logs + status) — no changes needed there since embed jobs use the same job infrastructure.

---

## Component File Summary

| File | Status | Purpose |
|------|--------|---------|
| `src/api/models.ts` | New | All model settings + Ollama API calls |
| `src/components/ModelStepForm.tsx` | New | Shared provider+model selector with pull/validate UI |
| `src/components/PillToggle.tsx` | New | Pill-shaped boolean toggle |
| `src/pages/Models.tsx` | New | `/models` page |
| `src/pages/SetupWizard.tsx` | Modify | Add steps 3–5 |
| `src/pages/Settings.tsx` | Modify | Add Search Pipeline card |
| `src/components/Sidebar.tsx` | Modify | Add Models nav entry |
| `src/App.tsx` | Modify | Add `/models` route |
| `src/api/jobs.ts` | Modify | Add `startEmbedJob()` |

---

## Testing

- `ModelStepForm`: render with Ollama provider → shows dropdown populated from mocked `listOllamaModels`; render with LiteLLM → shows text input + validate button; pull flow → shows progress, then clears on completion
- `PillToggle`: renders ON/OFF states; disabled state; fires onChange on click
- `Settings` pipeline card: loads from `GET /settings/pipeline`; toggle fires PATCH immediately; numeric input fires PATCH on blur; reranker pill disabled when vector search is off
- `Models` page: yellow banner visible when `embedding_model_changed_since_last_embed === 'true'`; Re-embed navigates to job detail on success; delete model shows confirmation dialog
- Setup wizard: steps 3–5 render; Skip keeps default; Next disabled until model selected/validated; completion call includes model settings
