# Deployment

Harmony deploys two ways:

- **Docker Compose** (single API container, no horizontal scaling) — the simplest path, right for a single machine or evaluation. Most of this document covers it.
- **Kubernetes** (multi-replica, autoscaling) — reference example manifests in [`configs/k8s/`](../configs/k8s/README.md). See [Kubernetes deployment](#kubernetes-deployment) below and [SCALING.md](SCALING.md).

This doc covers what infra needs to know to deploy Harmony outside the bundled `docker-compose.dev.yml` dev setup: required services, required vs. optional configuration, secrets, and production-specific settings.

## Required Services

| Service | Minimum version | Required? |
|---------|-----------------|------------|
| PostgreSQL | 17+ | Always — jobs, schedules, audit log, model registry, users, conversations |
| Redis | 7+ | Always — pub/sub, crawler-auth session caching, API key caching |
| Elasticsearch | 9.2.3 | Always — keyword search and indexing |
| Qdrant | v1.17.1 | Always — vector search |
| Ollama | — | Only if using local LLM/embedding models. Not required if you only use cloud LLM providers (OpenAI/Anthropic/Gemini/etc.) |

Versions above reflect what `docker-compose.yml`/`docker-compose.dev.yml` currently pin — verify against those files if running services independently of Compose.

## Required Environment Variables

These have no safe default; the API will not start (or will start insecurely) without them:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection string |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins — the API refuses to start if unset |
| `HARMONY_INTERNAL_TOKEN` | Shared secret the crawler subprocess uses to call internal `/api/internal/*` routes. Generate with `openssl rand -hex 32`. `docker-compose.yml` (prod) fails to start without it; `docker-compose.dev.yml` falls back to an insecure dev default if unset — do not rely on that fallback in production. |

## Optional Environment Variables

Everything below resolves through `ServiceConfigStore` with priority **ENV > DB (admin UI) > default** — if unset, either a sensible default applies or the value can be set later through the admin UI. See [CONFIGURATION.md](CONFIGURATION.md) for the full list.

| Variable | Default | Notes |
|----------|---------|-------|
| `ES_HOST` | `http://elasticsearch:9200` (Docker) | |
| `REDIS_URL` | `redis://redis:6379/0` (Docker) | |
| `HARMONY_BACKEND_URL` | `http://harmony-api:8000` (Docker) | Rarely needs override |
| `OLLAMA_HOST` | `http://localhost:11434` | Only relevant if using local models |
| `ES_INDEX_BASE_NAME`, `ES_LANGUAGES`, `ES_CONFIG_FILE` | `harmony`, `en,fr`, unset | Elasticsearch indexing config |

**LLM provider API keys are not environment variables.** They're configured after deployment through the admin UI's model registry (`/api/admin/models`), encrypted at rest. There is no `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`GEMINI_API_KEY` env var to set — point infra at the admin UI for LLM provider setup, not `.env`.

## Authentication (Optional, Recommended for Production)

Auth is **off by default** — `AUTH_MODE=optional` runs with no OIDC configuration needed at all, useful for evaluation or fully trusted internal networks.

For any production deployment, set `AUTH_MODE=required` and configure an OIDC identity provider. Once `AUTH_MODE=required` is set, these become required alongside it:

| Variable | Purpose |
|----------|---------|
| `OIDC_ISSUER_URL` | Internal URL the API uses to validate tokens against your IdP |
| `OIDC_PUBLIC_ISSUER_URL` | Public URL the browser uses for the OIDC login redirect |
| `OIDC_CLIENT_ID` | OIDC client ID registered with your IdP |
| `OIDC_CLIENT_SECRET` | OIDC client secret |

Also set `HARMONY_SECURE_COOKIES=true` in production (HTTPS-only cookies) — the dev default (`false`) is not safe outside local development.

**Bring your own IdP in production.** `docker-compose.dev.yml` bundles a Keycloak container for local development convenience; `docker-compose.yml` (prod) does **not** include Keycloak. Point `OIDC_ISSUER_URL`/`OIDC_PUBLIC_ISSUER_URL` at your own OIDC-compliant IdP (Keycloak, Okta, Azure AD, ADFS, etc.) — don't assume Keycloak ships with a production deployment.

The bundled `sso` Compose profile (`docker compose --profile sso up`) starts an optional noVNC browser container used for *interactive SSO crawler authentication* (logging the crawler into a site that requires browser-based SSO) — this is unrelated to OIDC/Keycloak user login and is opt-in.

## Persistent Storage

These named volumes hold state that must survive container restarts/redeploys — back them up or mount them on persistent storage:

- `pg_data` — Postgres data
- `es_data` — Elasticsearch indices
- `qdrant_data` — Qdrant vector collections
- `admin_data` — admin config storage, job logs, crawler output
- `ollama_data` — pulled Ollama models (only relevant if using local models)

See [BACKUP.md](BACKUP.md) for backup/restore procedures.

## Kubernetes deployment

For multi-replica, horizontally scaled deployments. The manifests in
[`configs/k8s/`](../configs/k8s/README.md) are **reference examples** — copy and
adapt them; they are not a black-box chart that owns your cluster topology. The
reference cluster is k3s on a single GPU node; managed/generic K8s deltas are in
the manifests README.

Three pieces make the API horizontally scalable (Phase 10), set in the example
ConfigMap:

- `DOCUMENT_CACHE_BACKEND=redis` — shared document cache across replicas
- `CONFIG_STORE=postgres` — admin config in Postgres, not pod-local disk
- `JOB_EXECUTOR=kubernetes` — crawl/index jobs run as `batch/v1` Jobs

The last requires the namespaced RBAC in `configs/k8s/rbac.yaml` (the API's
ServiceAccount can create/delete Jobs and patch Deployments). Schema migrations
run automatically in the API Deployment's `alembic-migrate` initContainer.

### 1. Raw kubectl

Prerequisites: a cluster (k3s for the reference setup), and — only if you run GPU
model serving in-cluster — the NVIDIA device plugin
(`configs/k8s/nvidia-device-plugin-daemonset.yaml`) and a node with a GPU.

```bash
kubectl create namespace harmony

# Edit configmap.example.yaml; fill secret.example.yaml with real values.
cp configs/k8s/secret.example.yaml /tmp/harmony-secret.yaml   # then edit
kubectl apply -f configs/k8s/configmap.example.yaml
kubectl apply -f /tmp/harmony-secret.yaml
kubectl apply -f configs/k8s/rbac.yaml

# Data services first, then app.
kubectl apply -f configs/k8s/postgres-statefulset.yaml \
  -f configs/k8s/elasticsearch-statefulset.yaml \
  -f configs/k8s/qdrant-statefulset.yaml \
  -f configs/k8s/redis-deployment.yaml
kubectl apply -f configs/k8s/harmony-api-deployment.yaml \
  -f configs/k8s/harmony-api-service.yaml \
  -f configs/k8s/harmony-frontend.yaml \
  -f configs/k8s/hpa.yaml -f configs/k8s/ingress.yaml
```

Storage: k3s ships the `local-path` provisioner; on managed K8s set a storage
class on the StatefulSet PVCs and swap the vLLM `hostPath` model cache for a PVC.

Model serving is org-provided — point `VLLM_*_URL` / `OLLAMA_HOST` in the ConfigMap
at your own vLLM/Ollama services (`configs/k8s/vllm-completions-deployment.yaml`
and `configs/k8s/vllm-reranker-deployment.yaml` are examples).

Smoke test:

```bash
kubectl -n harmony port-forward svc/harmony-api 8000:8000
curl localhost:8000/health   # liveness — always ok if the process is up
curl localhost:8000/ready    # readiness — 200 only when ES+Postgres+Redis are up
```

### 2. Helm

Wrap the example manifests as a chart: move them under `templates/` and replace
the hardcoded values with a `values.yaml`:

```yaml
# values.yaml (reference shape)
image:
  repository: harmony-api
  tag: "1.0.0"          # pin a tag/digest in production, not :latest
replicaCount: 2
storageClass: ""        # "" = cluster default; set on managed K8s
ingress:
  host: harmony.example.com
  tlsSecret: harmony-tls
env:
  DOCUMENT_CACHE_BACKEND: redis
  CONFIG_STORE: postgres
  JOB_EXECUTOR: kubernetes
```

Templatize the API Deployment's `replicas`, `image`, `envFrom`, and the PVC
`storageClassName`. Upgrades: `helm upgrade harmony ./chart -n harmony` — the
`alembic-migrate` initContainer runs migrations on each rollout.

### 3. Terraform + Helm

Provision the cluster and release together. Terraform owns node pools (a GPU pool
for model serving), the storage class, and DNS; the `helm_release` resource
deploys the chart:

```hcl
resource "helm_release" "harmony" {
  name       = "harmony"
  namespace  = "harmony"
  chart      = "${path.module}/charts/harmony"
  create_namespace = true

  set {
    name  = "image.tag"
    value = var.harmony_version
  }
  set {
    name  = "storageClass"
    value = var.storage_class
  }
}
```

Keep Terraform state in a remote backend (S3/GCS) so cluster and release changes
are reviewable. Secrets: feed them via `set_sensitive` from a secrets manager
rather than committing them to `values.yaml`.

## Source of Truth

This doc is derived from `docker-compose.dev.yml` (primary reference — it's the Compose file used day to day), cross-checked against `docker-compose.yml` (prod) and `.env.example`. If env vars or service versions drift from what's documented here, those three files are authoritative — verify against their current contents.
