from __future__ import annotations

import base64
import io
import logging
import typing
from pathlib import Path

import litellm
import pdf2image
import pytesseract

if typing.TYPE_CHECKING:
    from harmony.api.services.admin._model_registry import ModelRegistryService

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}


def ocr_image(path: Path) -> str:
    return pytesseract.image_to_string(str(path))


def ocr_pdf(path: Path) -> str:
    pages = pdf2image.convert_from_path(str(path))
    return "\n\n".join(pytesseract.image_to_string(page) for page in pages)


async def ocr_with_vision_model(
    image_bytes: bytes, model_id: str, api_key: str | None
) -> str:
    b64 = base64.b64encode(image_bytes).decode()
    response = await litellm.acompletion(
        model=model_id,
        api_key=api_key,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                    {
                        "type": "text",
                        "text": "Extract all text from this image. Output plain text only.",
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content or ""


async def ocr_dispatch(path: Path, model_registry_service: ModelRegistryService) -> str:
    vision_row = await model_registry_service.get_active_vision_model()
    is_pdf = path.suffix.lower() == ".pdf"

    if vision_row is not None:
        litellm_model_id = vision_row.litellm_model_id
        api_key = await model_registry_service.resolve_api_key(litellm_model_id)
        if is_pdf:
            pages = pdf2image.convert_from_path(str(path))
            texts = []
            for page in pages:
                buf = io.BytesIO()
                page.save(buf, format="PNG")
                texts.append(
                    await ocr_with_vision_model(
                        buf.getvalue(), litellm_model_id, api_key
                    )
                )
            return "\n\n".join(texts)
        image_bytes = path.read_bytes()
        return await ocr_with_vision_model(image_bytes, litellm_model_id, api_key)

    if is_pdf:
        return ocr_pdf(path)
    return ocr_image(path)
