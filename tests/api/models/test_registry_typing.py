from __future__ import annotations

import typing
from datetime import datetime

from harmony.api.models.registry import ModelRegistryRow


def test_model_registry_row_datetime_fields_typed() -> None:
    hints = typing.get_type_hints(ModelRegistryRow)
    assert hints["created_at"] is datetime
    assert hints["updated_at"] is datetime
