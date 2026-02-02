from __future__ import annotations

import json
import typing
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from harmony.api.models.config import ConfigEntry, ConfigType
from harmony.crawler.config import CrawlerConfig
from harmony.indexer.config import IndexerConfig


class ConfigStore:
    """Filesystem-based configuration storage."""

    def __init__(self) -> None:
        self._base_path: Path | None = None

    def initialize(self, base_path: Path) -> None:
        """Initialize the config store with a base path."""
        self._base_path = base_path
        (base_path / "crawler").mkdir(parents=True, exist_ok=True)
        (base_path / "indexer").mkdir(parents=True, exist_ok=True)

    @property
    def base_path(self) -> Path:
        if self._base_path is None:
            msg = "ConfigStore not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return self._base_path

    def get_config_path(self, config_type: ConfigType, name: str) -> Path:
        """Get the path to a config file."""
        return self.base_path / config_type / f"{name}.yaml"

    def _get_meta_path(self, config_type: ConfigType, name: str) -> Path:
        return self.base_path / config_type / f"{name}.meta.json"

    def list_configs(self, config_type: ConfigType) -> list[ConfigEntry]:
        """List all saved configs of a given type."""
        config_dir = self.base_path / config_type
        entries = []

        for yaml_file in config_dir.glob("*.yaml"):
            name = yaml_file.stem
            meta_path = self._get_meta_path(config_type, name)

            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                entries.append(
                    ConfigEntry(
                        name=name,
                        type=config_type,
                        created_at=datetime.fromisoformat(meta["created_at"]),
                        updated_at=datetime.fromisoformat(meta["updated_at"]),
                        description=meta.get("description"),
                    )
                )
            else:
                stat = yaml_file.stat()
                entries.append(
                    ConfigEntry(
                        name=name,
                        type=config_type,
                        created_at=datetime.fromtimestamp(stat.st_ctime, tz=UTC),
                        updated_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                    )
                )

        return sorted(entries, key=lambda e: e.updated_at, reverse=True)

    def get_config(
        self, config_type: ConfigType, name: str
    ) -> dict[str, typing.Any] | None:
        """Get a config by name."""
        config_path = self.get_config_path(config_type, name)
        if not config_path.exists():
            return None

        with config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_config_entry(
        self, config_type: ConfigType, name: str
    ) -> ConfigEntry | None:
        """Get config metadata."""
        config_path = self.get_config_path(config_type, name)
        if not config_path.exists():
            return None

        meta_path = self._get_meta_path(config_type, name)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            return ConfigEntry(
                name=name,
                type=config_type,
                created_at=datetime.fromisoformat(meta["created_at"]),
                updated_at=datetime.fromisoformat(meta["updated_at"]),
                description=meta.get("description"),
            )

        stat = config_path.stat()
        return ConfigEntry(
            name=name,
            type=config_type,
            created_at=datetime.fromtimestamp(stat.st_ctime, tz=UTC),
            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )

    def save_config(
        self,
        config_type: ConfigType,
        name: str,
        config: dict[str, typing.Any],
        description: str | None = None,
    ) -> ConfigEntry:
        """Save a config."""
        self._validate_config(config_type, config)

        config_path = self.get_config_path(config_type, name)
        meta_path = self._get_meta_path(config_type, name)

        now = datetime.now(UTC)

        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            created_at = datetime.fromisoformat(meta["created_at"])
        else:
            created_at = now

        with config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                config,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

        meta = {
            "created_at": created_at.isoformat(),
            "updated_at": now.isoformat(),
            "description": description,
        }
        meta_path.write_text(json.dumps(meta, indent=2))

        return ConfigEntry(
            name=name,
            type=config_type,
            created_at=created_at,
            updated_at=now,
            description=description,
        )

    def delete_config(self, config_type: ConfigType, name: str) -> bool:
        """Delete a config."""
        config_path = self.get_config_path(config_type, name)
        meta_path = self._get_meta_path(config_type, name)

        if not config_path.exists():
            return False

        config_path.unlink()
        if meta_path.exists():
            meta_path.unlink()

        return True

    def export_yaml(self, config_type: ConfigType, name: str) -> str | None:
        """Export config as YAML string."""
        config_path = self.get_config_path(config_type, name)
        if not config_path.exists():
            return None

        return config_path.read_text(encoding="utf-8")

    def import_yaml(
        self,
        config_type: ConfigType,
        name: str,
        yaml_content: str,
        description: str | None = None,
    ) -> ConfigEntry:
        """Import config from YAML string."""
        config = yaml.safe_load(yaml_content)
        return self.save_config(config_type, name, config, description)

    def _validate_config(
        self, config_type: ConfigType, config: dict[str, typing.Any]
    ) -> None:
        """Validate config against its Pydantic model."""
        try:
            if config_type == "crawler":
                CrawlerConfig(**config)
            elif config_type == "indexer":
                IndexerConfig(**config)
        except ValidationError as e:
            errors = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                msg = error["msg"]
                errors.append(f"{field}: {msg}")
            raise ValueError("Validation failed:\n" + "\n".join(errors)) from e


config_store = ConfigStore()
