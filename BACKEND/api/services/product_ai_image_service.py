from __future__ import annotations

import base64
import io
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

import requests
from fastapi import HTTPException, status
from PIL import Image, ImageOps, UnidentifiedImageError

from api.config import settings
from api.services.product_image_service import analyze_product_image_quality

logger = logging.getLogger(__name__)

AI_IMPROVEMENT_PROMPT = """
Improve this exact seller-supplied product photograph for a trustworthy ecommerce marketplace.

Preserve the real product faithfully: its identity, shape, proportions, colors, materials,
logos, labels, text, buttons, ports, accessories and all visible physical features.
Do not invent, remove, replace, redesign or materially alter the product.

Improve only the presentation:
- increase usable resolution and apparent sharpness without changing the product;
- correct exposure, lighting and white balance;
- center the product with comfortable ecommerce margins;
- use a clean neutral white studio background;
- remove distracting background clutter while keeping the product itself unchanged;
- produce a realistic professional ecommerce photograph, not an illustration.

Do not add promotional text, watermarks, badges, extra objects, hands or people.
""".strip()


@dataclass(frozen=True)
class ImprovedProductImage:
    image_bytes: bytes
    mime_type: str
    width: int
    height: int
    model: str
    quality: dict[str, Any]
    usage: dict[str, Any] | None


def _http_error(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


def _validate_source(raw: bytes) -> tuple[str, Image.Image]:
    if not raw:
        raise _http_error("AI_IMAGE_SOURCE_EMPTY", "The source product image is empty.", 400)
    if len(raw) > settings.PRODUCT_IMAGE_AI_MAX_SOURCE_MB * 1024 * 1024:
        raise _http_error(
            "AI_IMAGE_SOURCE_TOO_LARGE",
            f"The source image must not exceed {settings.PRODUCT_IMAGE_AI_MAX_SOURCE_MB} MB.",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise _http_error("AI_IMAGE_SOURCE_INVALID", "Upload a valid JPEG, PNG or WEBP image.", 400) from exc
    fmt = (image.format or "").upper()
    # exif_transpose can drop format on some Pillow versions; inspect original when needed.
    if fmt not in {"JPEG", "PNG", "WEBP"}:
        try:
            with Image.open(io.BytesIO(raw)) as probe:
                fmt = (probe.format or "").upper()
        except Exception:
            fmt = ""
    if fmt not in {"JPEG", "PNG", "WEBP"}:
        raise _http_error("AI_IMAGE_SOURCE_INVALID", "Only JPEG, PNG and WEBP images are supported.", 400)
    return {"JPEG":"image/jpeg","PNG":"image/png","WEBP":"image/webp"}[fmt], image


def improve_product_image(raw: bytes, *, is_primary: bool) -> ImprovedProductImage:
    if not settings.PRODUCT_IMAGE_AI_ENABLED:
        raise _http_error("PRODUCT_IMAGE_AI_DISABLED", "AI image improvement is not enabled.", 503)
    if not settings.OPENROUTER_API_KEY:
        raise _http_error("PRODUCT_IMAGE_AI_NOT_CONFIGURED", "AI image improvement is not configured.", 503)

    source_mime, _ = _validate_source(raw)
    reference = "data:" + source_mime + ";base64," + base64.b64encode(raw).decode("ascii")
    payload: dict[str, Any] = {
        "model": settings.PRODUCT_IMAGE_AI_MODEL,
        "prompt": AI_IMPROVEMENT_PROMPT,
        "input_references": [{"type": "image_url", "image_url": {"url": reference}}],
        "n": 1,
        "resolution": settings.PRODUCT_IMAGE_AI_RESOLUTION,
        "aspect_ratio": "1:1" if is_primary else "auto",
        "quality": settings.PRODUCT_IMAGE_AI_QUALITY,
        "output_format": "png",
    }
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.PUBLIC_BASE_URL or "https://xerinmarketplace.com",
        "X-Title": "Xerin Marketplace",
    }

    try:
        response = requests.post(
            settings.OPENROUTER_IMAGE_API_URL,
            headers=headers,
            json=payload,
            timeout=settings.PRODUCT_IMAGE_AI_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise _http_error("PRODUCT_IMAGE_AI_TIMEOUT", "AI image improvement took too long. Please try again.", 504) from exc
    except requests.RequestException as exc:
        logger.warning("OpenRouter image request failed: %s", type(exc).__name__)
        raise _http_error("PRODUCT_IMAGE_AI_UNAVAILABLE", "AI image improvement is temporarily unavailable.", 502) from exc

    if not response.ok:
        # Never return the key or full upstream payload to the seller.
        logger.warning("OpenRouter image request returned HTTP %s: %.500s", response.status_code, response.text)
        if response.status_code in {401, 403}:
            raise _http_error("PRODUCT_IMAGE_AI_NOT_CONFIGURED", "AI image improvement is not configured correctly.", 503)
        if response.status_code == 429:
            raise _http_error("PRODUCT_IMAGE_AI_BUSY", "AI image improvement is busy. Please try again shortly.", 429)
        raise _http_error("PRODUCT_IMAGE_AI_FAILED", "The AI provider could not improve this image. Please try another image.", 502)

    try:
        result = response.json()
        images = result.get("data") or []
        encoded = images[0].get("b64_json") if images else None
        if not encoded:
            raise ValueError("missing b64_json")
        generated = base64.b64decode(encoded, validate=True)
        output = Image.open(io.BytesIO(generated))
        output.load()
        output = ImageOps.exif_transpose(output).convert("RGB")
    except Exception as exc:
        logger.warning("Invalid OpenRouter image response")
        raise _http_error("PRODUCT_IMAGE_AI_INVALID_RESPONSE", "The AI provider returned an invalid image.", 502) from exc

    quality = analyze_product_image_quality(output, is_primary=is_primary)
    quality_payload = {
        "passed": quality.passed,
        "score": quality.score,
        "image_type": quality.image_type,
        "metrics": quality.metrics,
        "issues": quality.issues,
    }

    # Task 1 deliberately returns even a failed AI result to the seller preview.
    # Task 2 can allow acceptance only when `quality.passed` is true.
    buffer = io.BytesIO()
    output.save(buffer, format="PNG", optimize=True)
    return ImprovedProductImage(
        image_bytes=buffer.getvalue(),
        mime_type="image/png",
        width=output.width,
        height=output.height,
        model=settings.PRODUCT_IMAGE_AI_MODEL,
        quality=quality_payload,
        usage=result.get("usage") if isinstance(result.get("usage"), dict) else None,
    )
