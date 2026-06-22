# Frontend Architecture

Harmony's frontend (`frontend/`) is a single Vite/React app serving two distinct UIs from one codebase: the native chat interface (homepage) and the admin dashboard (`/admin`). Both talk to the same single FastAPI backend.

## App Split

```
frontend/src/
├── apps/
│   ├── chat/       — native chat UI (homepage, "/")
│   │   ├── components/
│   │   └── pages/
│   └── admin/      — admin dashboard ("/admin/*")
│       ├── components/
│       └── pages/
└── shared/         — code used by both apps
    ├── api/        — API client, typed request/response wrappers
    ├── components/ — shared UI primitives (shadcn/ui)
    ├── hooks/
    ├── lib/
    ├── pages/       — cross-cutting pages (setup wizard, 404)
    └── stores/
```

Routing lives in `frontend/src/App.tsx` (React Router): `/` and `/c/:conversationId` render `ChatLayout` (chat app), everything under `/admin/*` renders `Layout` (admin app). There's no separate build or deploy step per app — both ship in the same bundle, split by route.

## Conventions

- **React Query** for all server state — no manual `useEffect` + `fetch` data fetching
- **shadcn/ui** (Radix + Tailwind) for components — both apps share the same component library in `shared/components/ui`
- **React Router** for navigation, with the chat/admin split enforced at the route tree level, not via separate apps

## Adding a Feature

New admin features need three pieces in lockstep — missing one is the most common integration gap:

1. A page component under `apps/admin/pages/`
2. A route registered in `App.tsx`'s `<Route path="/admin">` tree
3. Any new API calls added to `shared/api/`

New chat features follow the same shape under `apps/chat/`.

## Setup and Auth Gating

`App.tsx` gates routing on two backend checks before rendering anything:

- **Setup status** (`setupApi.getStatus()`) — if `is_configured` is false, every route redirects to `/setup` (the setup wizard) until first-run configuration completes (Ollama/Qdrant host, embedding model, etc.)
- **Auth status** — if OIDC is configured and the user isn't authenticated, navigating to `/admin/*` redirects to `/api/auth/login`. The chat UI itself does not currently force a login redirect.

## Backend Connection

In dev, the frontend Vite dev server (port 8080) proxies API calls to the backend (port 8000) — see [DEVELOPMENT.md](DEVELOPMENT.md). In production, the `harmony-frontend` container serves the built static assets and proxies `/api/*` to `harmony-api`. There is no separate "admin server" — one FastAPI app serves both `/api/search`-style routes and `/api/admin/*`.
