# Data Source Providers

"Data source" is Harmony's top-level ingestion abstraction — it replaced the earlier "crawler config" concept. Each data source has a provider type (`web-crawler`, `filesystem`, or a custom third-party provider) that knows how to validate its own config and produce the work needed to ingest data.

This doc covers the provider extension model: how built-in providers work and how to add your own without modifying Harmony's source code.

## Architecture

```
BaseProvider (harmony/providers/_base.py)
  ├─ config_schema() → JSON schema for this provider's config (drives the admin UI form)
  └─ run() → list[ProviderJobSpec] (what to actually execute)
         ↓
ProviderRegistry (harmony/providers/_registry.py)
  ├─ Discovers built-in providers (web-crawler, filesystem)
  ├─ Discovers third-party providers via the `harmony.providers` entry point group
  └─ Exposes provider types + schemas to the admin UI (data source creation form)
         ↓
JobManager.start_from_specs(specs, data_source_id)
  └─ Executes each ProviderJobSpec as a subprocess in sequence (see Job execution: subprocess, not async task)
```

**Provider/executor decoupling:** a provider's `run()` method returns `ProviderJobSpec` objects (`entrypoint`, `args`, `env`) — it describes *what* to execute, not *how*. `JobManager` is responsible for actually running it as a subprocess. This split exists so that a future Kubernetes job executor can consume the same `ProviderJobSpec` without providers needing to know about execution backends.

## Built-in Providers

### Web Crawler (`web-crawler`)

Scrapy-based crawler with pluggable authentication (see [AUTHENTICATION.md](AUTHENTICATION.md)), safety middleware (see [CRAWLER.md](CRAWLER.md)), and delta-fetch change detection. Defined in `harmony/providers/_web_crawler.py`.

### Filesystem (`filesystem`)

Indexes files from a mounted directory (NFS, local disk, network share). Config: `root_path`, `include_patterns`/`exclude_patterns` (glob). Defined in `harmony/providers/_filesystem.py`:

```python
class FilesystemProvider(BaseProvider):
    provider_type = "filesystem"
    display_name = "Filesystem"
    description = "Index files from a mounted directory (NFS, local disk, network share)"

    def run(self) -> list[ProviderJobSpec]:
        return [
            ProviderJobSpec(
                entrypoint="harmony-ingest-fs",
                args=["--data-source-id", self._data_source_id],
                env={},
            )
        ]
```

## Writing a Custom Provider

Like custom auth providers (see [CUSTOM_AUTH_PROVIDER.md](CUSTOM_AUTH_PROVIDER.md)), custom data source providers are discovered via Python entry points — no Harmony code changes required.

### Step 1: Implement `BaseProvider`

```python
# my_company_provider/provider.py
from __future__ import annotations

import pydantic

from harmony.providers._base import BaseProvider, ProviderJobSpec


class MyProviderConfig(pydantic.BaseModel):
    api_endpoint: str = pydantic.Field(description="Source API endpoint")
    api_key: str = pydantic.Field(description="API key for the source")


class MyCustomProvider(BaseProvider):
    provider_type = "my_custom_source"  # must match the entry point name
    display_name = "My Custom Source"
    description = "Ingests data from My Company's internal API"

    def __init__(self, config: dict, data_source_id: str) -> None:
        self._config = MyProviderConfig.model_validate(config)
        self._data_source_id = data_source_id

    @classmethod
    def config_schema(cls) -> dict:
        return MyProviderConfig.model_json_schema()

    def run(self) -> list[ProviderJobSpec]:
        return [
            ProviderJobSpec(
                entrypoint="my-company-ingest-cli",
                args=["--data-source-id", self._data_source_id],
                env={"MY_API_KEY": self._config.api_key},
            )
        ]
```

`config_schema()` drives the admin UI's data source creation form automatically — no frontend changes needed for a new provider type.

### Step 2: Register the Entry Point

In your package's `pyproject.toml`:

```toml
[project.entry-points."harmony.providers"]
my_custom_source = "my_company_provider.provider:MyCustomProvider"
```

The entry point name must match `provider_type`.

### Step 3: Install and Use

```bash
pip install my-company-provider
```

The new provider type appears automatically in the admin UI's "Add Data Source" form — no Harmony restart-time registration step beyond installing the package (the registry runs entry point discovery on `ProviderRegistry()` construction; call `.discover()` to refresh without restarting).

## Job Execution Model

Provider jobs run as subprocesses, not asyncio tasks — this isolates crashes and lets jobs survive an API process restart. Each `ProviderJobSpec` becomes one subprocess step, executed sequentially via `JobManager._run_specs_sequentially`; job state is persisted to Postgres (`JobsRepo`) and live output streams to a log file. If your provider needs to perform multiple distinct steps (e.g. fetch, then index), return multiple `ProviderJobSpec` entries from `run()` — they execute in order.
