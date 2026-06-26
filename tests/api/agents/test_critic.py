from __future__ import annotations

import dataclasses
import typing

from harmony.api.agents._models import CritiqueDict  # noqa: PLC2701


def test_critique_dict_has_missing_information() -> None:
    fields = {f.name for f in dataclasses.fields(CritiqueDict)}
    assert "missing_information" in fields


def test_missing_information_defaults_empty() -> None:
    assert CritiqueDict().missing_information == []


def test_missing_information_roundtrips() -> None:
    gaps = ["It is unclear which protocol pyda uses.", "No mention of auth."]
    critique = CritiqueDict(missing_information=gaps)
    assert critique.missing_information == gaps


def test_missing_information_survives_field_filter() -> None:
    critique_fields = {f.name for f in dataclasses.fields(CritiqueDict)}
    raw: dict[str, typing.Any] = {
        "factual_accuracy": 0.9,
        "missing_information": ["gap one"],
        "unknown_key": "ignored",
    }
    critique = CritiqueDict(**{k: v for k, v in raw.items() if k in critique_fields})
    assert critique.missing_information == ["gap one"]
