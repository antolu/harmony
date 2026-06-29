# Harmony Kubernetes manifests

These are **reference examples**, not a turnkey chart. They deploy Harmony's own
components and show how the org wires in model serving. Copy them into your own
GitOps repo / Helm chart and adapt namespace, image tags, storage classes, and
host names to your cluster.

The reference cluster is **k3s on a single GPU node**. Deltas for managed/generic
Kubernetes are called out below.

## What's here

| File | Purpose |
|------|---------|
| `configmap.example.yaml` | Non-secret env (DB/Redis/ES URLs, stateless backends, model URLs, rate limits) |
| `secret.example.yaml` | Secret template — copy, fill, **do not commit the filled copy** |
| `rbac.yaml` | ServiceAccount + namespaced Role for the Kubernetes job executor |
| `harmony-api-deployment.yaml` | 2-replica stateless API with an `alembic upgrade head` initContainer |
| `harmony-api-service.yaml` / `harmony-frontend.yaml` | ClusterIP services + frontend Deployment |
| `postgres-statefulset.yaml`, `elasticsearch-statefulset.yaml`, `qdrant-statefulset.yaml` | Data services (single-node, RWO PVCs) |
| `redis-deployment.yaml` | Redis (rate-limit counters, shared cache, session state) |
| `hpa.yaml` | CPU autoscaling for API + frontend |
| `ingress.yaml` | TLS-ready ingress placeholder |
| `vllm-completions-deployment.yaml` | Example completions model server (Deployment) |

The standalone `configs/vllm-*.yml` and `configs/k3s_nvidia_device_plugin_daemonset.yml`
files are the original model-serving examples (reranker Deployment, device plugin);
they stay as-is. `vllm-completions-deployment.yaml` is the Deployment-shaped version
of the old `configs/vllm-pod.yml`.

## Stateless backends (Phase 10)

A multi-replica API requires shared state. The ConfigMap sets:

- `DOCUMENT_CACHE_BACKEND=redis` — document cache shared across replicas
- `CONFIG_STORE=postgres` — admin config in Postgres, not pod-local disk
- `JOB_EXECUTOR=kubernetes` — crawl/index jobs run as `batch/v1` Jobs (needs `rbac.yaml`)

There is **no shared RWX PVC for logs** — job logs/stats go through Postgres/Redis.
Only per-service RWO data PVCs exist.

## Model serving (org-provided)

Harmony does not ship model serving. Point the API at yours via the ConfigMap:

- **Completions** — vLLM (`vllm-completions-deployment.yaml`) or Ollama. Set `VLLM_COMPLETIONS_URL` / `OLLAMA_HOST`.
- **Embeddings** — vLLM *or* Ollama (`VLLM_EMBEDDINGS_URL` / `OLLAMA_HOST`).
- **Reranker** — vLLM only, optional (`VLLM_RERANKER_URL`; see `configs/vllm-reranker.yml`).

Model weights are pre-pulled into the hostPath/PVC cache before first start (an
in-app model-download wizard is deferred). The API's own schema migrations run in
the `alembic-migrate` initContainer.

## k3s vs. generic Kubernetes

| Concern | k3s (reference) | Managed / generic K8s |
|---------|-----------------|-----------------------|
| GPU device plugin | `configs/k3s_nvidia_device_plugin_daemonset.yml` (manual) | Usually provided by the cloud GPU node pool / NVIDIA operator |
| Model cache volume | `hostPath` on the GPU node | `PersistentVolumeClaim` on a storage class |
| Ingress controller | traefik (built into k3s) | nginx / cloud LB — change `ingressClassName` |
| Storage | local-path provisioner | your storage class |

## Small-scale alternative

For a single-machine deployment, the production `docker-compose.yml` (single API
container, no horizontal scaling) is simpler than Kubernetes. See `docs/DEPLOYMENT.md`.

## Apply

```bash
kubectl create namespace harmony
kubectl apply -f configmap.example.yaml      # after editing values
kubectl apply -f secret.example.yaml          # after filling real values
kubectl apply -f rbac.yaml
kubectl apply -f postgres-statefulset.yaml -f elasticsearch-statefulset.yaml \
  -f qdrant-statefulset.yaml -f redis-deployment.yaml
kubectl apply -f harmony-api-deployment.yaml -f harmony-api-service.yaml \
  -f harmony-frontend.yaml -f hpa.yaml -f ingress.yaml
```

> Pin image tags (ideally digests) in production rather than `:latest`.
