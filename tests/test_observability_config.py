from __future__ import annotations

from pathlib import Path

import yaml


def test_compose_logging_uses_json_driver() -> None:
    """OBS-02: Docker Compose harmony service uses stdout (no custom logging driver that suppresses JSON)."""
    compose_path = Path(__file__).parent.parent / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml not found"

    with compose_path.open() as f:
        compose = yaml.safe_load(f)

    harmony_service = compose.get("services", {}).get("harmony", {})
    logging_config = harmony_service.get("logging", {})

    if logging_config:
        driver = logging_config.get("driver", "json-file")
        assert driver in {
            "json-file",
            "local",
            "journald",
        }, f"Unexpected logging driver: {driver}"
