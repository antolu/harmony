from __future__ import annotations

import typing
from pathlib import Path
from unittest import mock

import pytest

from harmony.core import ocr


def test_ocr_image_calls_pytesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_image_to_string = mock.Mock(return_value="extracted text")
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", mock_image_to_string)

    result = ocr.ocr_image(Path("/tmp/scan.png"))

    assert result == "extracted text"
    mock_image_to_string.assert_called_once_with("/tmp/scan.png")


def test_ocr_pdf_converts_pages_and_joins_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_pages = ["page1_image", "page2_image"]
    mock_convert = mock.Mock(return_value=fake_pages)
    mock_image_to_string = mock.Mock(
        side_effect=["text from page 1", "text from page 2"]
    )
    monkeypatch.setattr(ocr.pdf2image, "convert_from_path", mock_convert)
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", mock_image_to_string)

    result = ocr.ocr_pdf(Path("/tmp/scanned.pdf"))

    mock_convert.assert_called_once_with("/tmp/scanned.pdf")
    assert result == "text from page 1\n\ntext from page 2"


async def test_ocr_dispatch_falls_back_to_tesseract_when_no_vision_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_model_registry_service = mock.AsyncMock()
    mock_model_registry_service.get_active_vision_model.return_value = None
    mock_ocr_image = mock.Mock(return_value="tesseract text")
    monkeypatch.setattr(ocr, "ocr_image", mock_ocr_image)

    result = await ocr.ocr_dispatch(Path("/tmp/scan.png"), mock_model_registry_service)

    assert result == "tesseract text"
    mock_ocr_image.assert_called_once_with(Path("/tmp/scan.png"))


async def test_ocr_dispatch_uses_vision_model_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    from harmony.api.services.admin._models import ModelRegistryRow  # noqa: PLC2701

    mock_model_registry_service = mock.AsyncMock()
    mock_model_registry_service.get_active_vision_model.return_value = ModelRegistryRow(
        id="model-1",
        name="gpt-4o",
        provider="openai",
        model_id="gpt-4o",
        model_type="vision",
        api_key_id=None,
        allowed_groups=[],
        cost_per_token=None,
        enabled=True,
        model_host_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        litellm_model_id="openai/gpt-4o",
    )
    mock_model_registry_service.get_by_litellm_id.return_value = (
        mock_model_registry_service.get_active_vision_model.return_value
    )

    mock_connection = mock.Mock()
    mock_connection.api_key = "sk-test"
    mock_model_registry_service.resolve_connection.return_value = mock_connection
    mock_ocr_with_vision_model = mock.AsyncMock(return_value="vision model text")
    mock_ocr_image = mock.Mock()
    monkeypatch.setattr(ocr, "ocr_with_vision_model", mock_ocr_with_vision_model)
    monkeypatch.setattr(ocr, "ocr_image", mock_ocr_image)
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"fake-image-bytes")

    result = await ocr.ocr_dispatch(Path("/tmp/scan.png"), mock_model_registry_service)

    assert result == "vision model text"
    mock_ocr_with_vision_model.assert_called_once_with(
        b"fake-image-bytes", "openai/gpt-4o", "sk-test"
    )
    mock_ocr_image.assert_not_called()


async def test_ocr_with_vision_model_base64_encodes_and_calls_litellm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_response = mock.Mock()
    mock_response.choices = [
        mock.Mock(message=mock.Mock(content="vision extracted text"))
    ]
    mock_acompletion = mock.AsyncMock(return_value=mock_response)
    monkeypatch.setattr(ocr.litellm, "acompletion", mock_acompletion)

    result = await ocr.ocr_with_vision_model(b"raw-bytes", "openai/gpt-4o", "sk-test")

    assert result == "vision extracted text"
    call_kwargs = mock_acompletion.call_args.kwargs
    assert call_kwargs["model"] == "openai/gpt-4o"
    assert call_kwargs["api_key"] == "sk-test"
    content: list[dict[str, typing.Any]] = call_kwargs["messages"][0]["content"]
    image_part = next(part for part in content if part["type"] == "image_url")
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")
