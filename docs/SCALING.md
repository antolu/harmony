# Scaling

How to scale a Kubernetes deployment of Harmony. For the deploy steps themselves
see [DEPLOYMENT.md](DEPLOYMENT.md); for the manifests see
[`configs/k8s/`](../configs/k8s/README.md).

## What scales horizontally

The API and frontend are stateless and scale to N replicas. Three env switches
(set in the example ConfigMap) make that safe:

- `DOCUMENT_CACHE_BACKEND=redis` — shared cache, not per-pod
- `CONFIG_STORE=postgres` — shared config, not pod-local disk
- `JOB_EXECUTOR=kubernetes` — jobs run as cluster Jobs, not in-process subprocesses

`hpa.yaml` autoscales both the API (2→10) and frontend (2→5) on CPU utilization.

## API tuning

CPU-based HPA is the default. If request latency, not CPU, is your bottleneck
(e.g. lots of waiting on the LLM/ES), CPU utilization under-reports load — move to
a custom metric (in-flight requests or p95 latency via Prometheus Adapter / KEDA).
That's a deployment choice, not built in.

Watch the rate limiter caps (`RATE_LIMIT_*`) as you scale: they are per-user /
per-IP and enforced across replicas via Redis, so adding replicas does not raise a
single client's effective limit.

## Model serving (vLLM / GPU)

Model serving is org-provided and GPU-bound — it scales differently from the API.

- **Model per role.** Pick completions/embeddings/reranker models for your GPU
  memory. `--max-model-len` and quantization (AWQ/W4A16) trade quality for fit;
  the examples use small quantized Qwen3 models that fit a single mid-range GPU.
- **Large models.** Use `--tensor-parallel-size N` to shard one model across N
  GPUs on a node. Multi-node tensor/pipeline parallelism is out of scope for the
  reference setup.
- **Replicas.** vLLM Deployments can run multiple replicas behind a Service for
  throughput, one GPU each — bounded by available GPUs, not CPU.
- **GPU autoscaling is not CPU-based.** A meaningful signal is queue depth or p95
  latency, which needs a custom metric (Prometheus + KEDA, scaling on vLLM's
  queue metrics). Documented as a future option, not built here.

## Data services

The reference manifests run Elasticsearch, Qdrant, and Postgres as **single-node**
StatefulSets with ReadWriteOnce PVCs — correct for the reference cluster, the
first scaling limit for a large deployment.

- **Elasticsearch** — move to a multi-node cluster (dedicated master/data roles,
  replicas > 0) for HA and search throughput. Next step, out of scope here.
- **Qdrant** — single node scales vertically a long way; Qdrant clustering for
  sharding/replication is the HA path.
- **Postgres** — a managed Postgres (or a Postgres operator with replicas +
  failover) is the production recommendation over the single-pod StatefulSet.
- **Redis** — single replica is fine functionally; use managed/HA Redis for
  resilience since it holds rate-limit counters, the shared cache, and sessions.
