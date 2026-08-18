from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from api.config import settings


ALLOWED_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
MAX_AD_DIMENSION = 3200


@dataclass(frozen=True)
class StoredAdvertisementImage:
    image_url: str
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
    return Path(filename or "advertisement-image").name[:255]


async def store_advertisement_image(
    file: UploadFile,
    *,
    variant: str,
) -> StoredAdvertisementImage:
    if variant not in {"desktop", "mobile"}:
        raise HTTPException(status_code=400, detail="variant must be desktop or mobile")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Advertisement image must not exceed {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            detected_format = (probe.format or "").upper()
            probe.verify()

        if detected_format not in ALLOWED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail="Only JPEG, PNG and WEBP advertisement images are allowed",
            )

        image = Image.open(io.BytesIO(raw))
        image.load()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid image",
        ) from exc

    image = ImageOps.exif_transpose(image)

    if image.width < 1 or image.height < 1:
        raise HTTPException(status_code=400, detail="Image dimensions are invalid")

    if image.width > MAX_AD_DIMENSION or image.height > MAX_AD_DIMENSION:
        image.thumbnail((MAX_AD_DIMENSION, MAX_AD_DIMENSION), Image.Resampling.LANCZOS)

    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGBA" if "transparency" in image.info else "RGB")

    relative_dir = Path("advertisements") / variant
    absolute_dir = settings.upload_path / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    image_name = f"{uuid.uuid4()}.webp"
    image_path = absolute_dir / image_name

    if image.mode == "RGBA":
        image.save(image_path, format="WEBP", quality=88, method=6, lossless=False)
    else:
        image.convert("RGB").save(image_path, format="WEBP", quality=88, method=6)

    relative_image = relative_dir / image_name

    return StoredAdvertisementImage(
        image_url=_public_url(relative_image),
        original_filename=_safe_original_filename(file.filename),
        mime_type="image/webp",
        file_size=image_path.stat().st_size,
        width=image.width,
        height=image.height,
    )
