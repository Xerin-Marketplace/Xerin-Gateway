from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from api.config import settings

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_PRODUCT_IMAGES = 10
MAX_IMAGE_DIMENSION = 2400
THUMBNAIL_SIZE = (480, 480)


@dataclass(frozen=True)
class StoredProductImage:
    image_url: str
    thumbnail_url: str
    storage_key: str
    original_filename: str
    mime_type: str
    file_size: int
    width: int
    height: int


def _public_url(relative_path: Path) -> str:
    clean = relative_path.as_posix().lstrip("/")
    if settings.PUBLIC_BASE_URL:
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/uploads/{clean}"
    return f"/uploads/{clean}"


def _safe_original_filename(filename: str | None) -> str:
    name = Path(filename or "product-image").name
    return name[:255]


def _prepare_image(raw: bytes) -> tuple[Image.Image, str, str]:
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Each image must not exceed {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            detected_format = (probe.format or "").upper()
            probe.verify()
        if detected_format not in ALLOWED_FORMATS:
            raise HTTPException(status_code=400, detail="Only JPEG, PNG and WEBP images are allowed")
        image = Image.open(io.BytesIO(raw))
        image.load()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid image") from exc

    image = ImageOps.exif_transpose(image)
    if image.width < 1 or image.height < 1:
        raise HTTPException(status_code=400, detail="Image dimensions are invalid")
    if image.width > MAX_IMAGE_DIMENSION or image.height > MAX_IMAGE_DIMENSION:
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)

    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGBA" if "transparency" in image.info else "RGB")
    return image, detected_format, ALLOWED_FORMATS[detected_format]


async def store_product_image(
    file: UploadFile,
    *,
    seller_id: uuid.UUID,
    product_id: uuid.UUID,
) -> StoredProductImage:
    raw = await file.read()
    image, detected_format, mime_type = _prepare_image(raw)

    image_id = uuid.uuid4()
    relative_dir = Path("products") / str(seller_id) / str(product_id)
    absolute_dir = settings.upload_path / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    # Normalize output to WEBP for smaller, browser-friendly files.
    image_name = f"{image_id}.webp"
    thumb_name = f"{image_id}_thumb.webp"
    image_path = absolute_dir / image_name
    thumb_path = absolute_dir / thumb_name

    save_image = image
    if save_image.mode == "RGBA":
        save_image.save(image_path, format="WEBP", quality=88, method=6, lossless=False)
    else:
        save_image.convert("RGB").save(image_path, format="WEBP", quality=88, method=6)

    thumbnail = image.copy()
    thumbnail.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
    if thumbnail.mode == "RGBA":
        thumbnail.save(thumb_path, format="WEBP", quality=82, method=6)
    else:
        thumbnail.convert("RGB").save(thumb_path, format="WEBP", quality=82, method=6)

    relative_image = relative_dir / image_name
    relative_thumb = relative_dir / thumb_name
    return StoredProductImage(
        image_url=_public_url(relative_image),
        thumbnail_url=_public_url(relative_thumb),
        storage_key=relative_image.as_posix(),
        original_filename=_safe_original_filename(file.filename),
        mime_type="image/webp",
        file_size=image_path.stat().st_size,
        width=image.width,
        height=image.height,
    )


def delete_product_image_files(storage_key: str | None, thumbnail_url: str | None = None) -> None:
    if not storage_key:
        return
    image_path = (settings.upload_path / storage_key).resolve()
    upload_root = settings.upload_path.resolve()
    if upload_root not in image_path.parents:
        return
    image_path.unlink(missing_ok=True)
    thumb_path = image_path.with_name(f"{image_path.stem}_thumb{image_path.suffix}")
    thumb_path.unlink(missing_ok=True)
