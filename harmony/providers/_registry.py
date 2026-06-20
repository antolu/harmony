from __future__ import annotations

import logging
import typing
from importlib.metadata import entry_points
from typing import Any

import harmony.providers._web_crawler as _wc_module
from harmony.providers._base import BaseProvider

logger = logging.getLogger(__name__)

BUILTIN_PROVIDERS: dict[str, type[BaseProvider]] = {}


def _register_entry_point(
    ep: typing.Any, providers: dict[str, type[BaseProvider]]
) -> None:
    provider_class = ep.load()
    if issubclass(provider_class, BaseProvider):
        providers[ep.name] = provider_class
        logger.info(f"Loaded custom provider '{ep.name}' from {ep.value}")
    else:
        logger.warning(f"Entry point '{ep.name}' is not a BaseProvider subclass")


def _load_plugin_providers(providers: dict[str, type[BaseProvider]]) -> None:

    eps: Any
    try:
        eps = entry_points(group="harmony.providers")
    except TypeError:
        all_eps = entry_points()
        eps = (
            all_eps.get("harmony.providers", [])  # type: ignore[union-attr]
            if hasattr(all_eps, "get")
            else []
        )

    for ep in eps:
        try:
            _register_entry_point(ep, providers)
        except Exception as e:
            logger.warning(f"Failed to load provider '{ep.name}': {e}")


class ProviderRegistry:
    """Manages data source providers.

    Supports both built-in providers (web-crawler, filesystem) and custom
    providers loaded via entry points. Third-party packages can register
    custom providers using:

        [project.entry-points."harmony.providers"]
        my_custom_provider = "my_package.providers:MyCustomProvider"
    """

    def __init__(self) -> None:
        self._provider_classes = self._discover_providers()
        self._schemas = {
            name: cls.config_schema() for name, cls in self._provider_classes.items()
        }

    def _discover_providers(self) -> dict[str, type[BaseProvider]]:
        providers = BUILTIN_PROVIDERS.copy()

        providers[_wc_module.WebCrawlerProvider.provider_type] = (
            _wc_module.WebCrawlerProvider
        )

        try:
            import harmony.providers._filesystem as _fs_module  # type: ignore[import-not-found]  # noqa: PLC0415 # deferred: optional package

            providers[_fs_module.FilesystemProvider.provider_type] = (
                _fs_module.FilesystemProvider
            )
        except ImportError:
            logger.debug("FilesystemProvider not available yet")

        try:
            _load_plugin_providers(providers)
        except ImportError:
            logger.debug("importlib.metadata not available, skipping plugin discovery")
        except Exception as e:
            logger.debug(f"Error discovering custom providers: {e}")

        return providers

    def discover(self) -> None:
        """Re-run provider discovery, refreshing built-ins and plugins."""
        self._provider_classes = self._discover_providers()
        self._schemas = {
            name: cls.config_schema() for name, cls in self._provider_classes.items()
        }

    def get(self, provider_type: str) -> type[BaseProvider] | None:
        return self._provider_classes.get(provider_type)

    def list_types(self) -> list[dict[str, typing.Any]]:
        return [
            {
                "type": name,
                "display_name": cls.display_name,
                "description": cls.description,
                "schema": self._schemas[name],
            }
            for name, cls in self._provider_classes.items()
        ]
