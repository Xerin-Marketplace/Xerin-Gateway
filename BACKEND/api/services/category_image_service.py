from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from api.config import settings

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_DIMENSION = 1800
THUMBNAIL_SIZE = (400, 400)


@dataclass(frozen=True)
class StoredCategoryImage:
    image_url: str
    thumbnail_url: str
    storage_key: str


def _public_url(relative_path: Path) -> str:
    clean = relative_path.as_posix().lstrip("/")
    if settings.PUBLIC_BASE_URL:
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/uploads/{clean}"
    return f"/uploads/{clean}"


async def store_category_image(file: UploadFile, *, category_id: uuid.UUID) -> StoredCategoryImage:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded category image is empty")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Category image must not exceed {settings.MAX_UPLOAD_SIZE_MB} MB",
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
    if image.width > MAX_IMAGE_DIMENSION or image.height > MAX_IMAGE_DIMENSION:
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)

    relative_dir = Path("categories") / str(category_id)
    absolute_dir = settings.upload_path / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    image_id = uuid.uuid4()
    image_name = f"{image_id}.webp"
    thumb_name = f"{image_id}_thumb.webp"
    image_path = absolute_dir / image_name
    thumb_path = absolute_dir / thumb_name

    if image.mode == "RGBA":
        image.save(image_path, format="WEBP", quality=88, method=6)
    else:
        image.convert("RGB").save(image_path, format="WEBP", quality=88, method=6)

    thumbnail = image.copy()
    thumbnail.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
    if thumbnail.mode == "RGBA":
        thumbnail.save(thumb_path, format="WEBP", quality=82, method=6)
    else:
        thumbnail.convert("RGB").save(thumb_path, format="WEBP", quality=82, method=6)

    relative_image = relative_dir / image_name
    relative_thumb = relative_dir / thumb_name
    return StoredCategoryImage(
        image_url=_public_url(relative_image),
        thumbnail_url=_public_url(relative_thumb),
        storage_key=relative_image.as_posix(),
    )


def delete_category_image_files(storage_key: str | None) -> None:
    if not storage_key:
        return
    upload_root = settings.upload_path.resolve()
    image_path = (settings.upload_path / storage_key).resolve()
    if upload_root not in image_path.parents:
        return
    image_path.unlink(missing_ok=True)
    image_path.with_name(f"{image_path.stem}_thumb{image_path.suffix}").unlink(missing_ok=True)
