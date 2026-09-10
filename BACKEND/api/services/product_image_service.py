from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError

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


@dataclass(frozen=True)
class ImageQualityResult:
    passed: bool
    score: int
    image_type: str
    metrics: dict[str, float | int]
    issues: list[dict[str, Any]]


def _public_url(relative_path: Path) -> str:
    clean = relative_path.as_posix().lstrip("/")
    if settings.PUBLIC_BASE_URL:
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/uploads/{clean}"
    return f"/uploads/{clean}"


def _safe_original_filename(filename: str | None) -> str:
    name = Path(filename or "product-image").name
    return name[:255]


def _quality_http_error(result: ImageQualityResult) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "code": "PRODUCT_IMAGE_QUALITY_REJECTED",
            "message": "The product image did not meet Xerin image quality requirements.",
            "image_type": result.image_type,
            "score": result.score,
            "issues": result.issues,
            "metrics": result.metrics,
        },
    )


def _file_http_error(*, code: str, message: str, http_status: int = 400) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={
            "code": code,
            "message": message,
        },
    )


def _rgb_for_analysis(image: Image.Image) -> Image.Image:
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        return background
    return image.convert("RGB")


def _sharpness_score(image: Image.Image) -> float:
    """Return variance of a discrete Laplacian; lower values indicate blur."""
    gray = image.convert("L")
    gray.thumbnail((512, 512), Image.Resampling.LANCZOS)
    array = np.asarray(gray, dtype=np.float32)
    if array.shape[0] < 3 or array.shape[1] < 3:
        return 0.0
    laplacian = (
        -4.0 * array[1:-1, 1:-1]
        + array[:-2, 1:-1]
        + array[2:, 1:-1]
        + array[1:-1, :-2]
        + array[1:-1, 2:]
    )
    return float(np.var(laplacian))


def _background_whiteness(image: Image.Image) -> float:
    """Estimate white-background coverage from an outer border around the image."""
    rgb = _rgb_for_analysis(image)
    rgb.thumbnail((600, 600), Image.Resampling.LANCZOS)
    arr = np.asarray(rgb, dtype=np.uint8)
    height, width, _ = arr.shape
    border_ratio = settings.PRODUCT_IMAGE_BACKGROUND_BORDER_PERCENT / 100.0
    band_y = max(1, int(height * border_ratio))
    band_x = max(1, int(width * border_ratio))

    mask = np.zeros((height, width), dtype=bool)
    mask[:band_y, :] = True
    mask[-band_y:, :] = True
    mask[:, :band_x] = True
    mask[:, -band_x:] = True
    border = arr[mask]
    if border.size == 0:
        return 0.0

    threshold = settings.PRODUCT_IMAGE_WHITE_PIXEL_THRESHOLD
    # Require all RGB channels to be near-white and reasonably neutral.
    near_white = np.all(border >= threshold, axis=1)
    neutral = (border.max(axis=1) - border.min(axis=1)) <= 20
    return float(np.mean(near_white & neutral) * 100.0)


def analyze_product_image_quality(image: Image.Image, *, is_primary: bool) -> ImageQualityResult:
    """Evaluate deterministic Xerin product-image quality rules."""
    image_type = "primary" if is_primary else "additional"
    width, height = image.size
    megapixels = (width * height) / 1_000_000.0
    aspect_ratio = width / height if height else 0.0
    analysis_rgb = _rgb_for_analysis(image)
    brightness = float(ImageStat.Stat(analysis_rgb.convert("L")).mean[0])
    sharpness = _sharpness_score(analysis_rgb)
    whiteness = _background_whiteness(analysis_rgb)

    if is_primary:
        min_width = settings.PRODUCT_IMAGE_PRIMARY_MIN_WIDTH
        min_height = settings.PRODUCT_IMAGE_PRIMARY_MIN_HEIGHT
        min_mp = settings.PRODUCT_IMAGE_PRIMARY_MIN_MEGAPIXELS
        min_ratio = settings.PRODUCT_IMAGE_PRIMARY_MIN_ASPECT_RATIO
        max_ratio = settings.PRODUCT_IMAGE_PRIMARY_MAX_ASPECT_RATIO
        min_sharpness = settings.PRODUCT_IMAGE_PRIMARY_MIN_SHARPNESS
        min_whiteness = settings.PRODUCT_IMAGE_PRIMARY_MIN_BACKGROUND_WHITENESS
    else:
        min_width = settings.PRODUCT_IMAGE_ADDITIONAL_MIN_WIDTH
        min_height = settings.PRODUCT_IMAGE_ADDITIONAL_MIN_HEIGHT
        min_mp = settings.PRODUCT_IMAGE_ADDITIONAL_MIN_MEGAPIXELS
        min_ratio = settings.PRODUCT_IMAGE_ADDITIONAL_MIN_ASPECT_RATIO
        max_ratio = settings.PRODUCT_IMAGE_ADDITIONAL_MAX_ASPECT_RATIO
        min_sharpness = settings.PRODUCT_IMAGE_ADDITIONAL_MIN_SHARPNESS
        min_whiteness = 0.0

    issues: list[dict[str, Any]] = []
    checks: list[bool] = []

    dimensions_ok = width >= min_width and height >= min_height
    checks.append(dimensions_ok)
    if not dimensions_ok:
        issues.append({
            "code": "IMAGE_DIMENSIONS_TOO_SMALL",
            "message": f"{image_type.title()} image must be at least {min_width} × {min_height} pixels.",
            "expected": {"min_width": min_width, "min_height": min_height},
            "actual": {"width": width, "height": height},
        })

    resolution_ok = megapixels >= min_mp
    checks.append(resolution_ok)
    if not resolution_ok:
        issues.append({
            "code": "IMAGE_RESOLUTION_TOO_LOW",
            "message": f"{image_type.title()} image resolution must be at least {min_mp:.2f} megapixels.",
            "expected": {"min_megapixels": min_mp},
            "actual": {"megapixels": round(megapixels, 3)},
        })

    aspect_ok = min_ratio <= aspect_ratio <= max_ratio
    checks.append(aspect_ok)
    if not aspect_ok:
        issues.append({
            "code": "IMAGE_ASPECT_RATIO_INVALID",
            "message": (
                f"{image_type.title()} image aspect ratio must be between "
                f"{min_ratio:.2f}:1 and {max_ratio:.2f}:1."
            ),
            "expected": {"min_ratio": min_ratio, "max_ratio": max_ratio},
            "actual": {"ratio": round(aspect_ratio, 3)},
        })

    sharpness_ok = sharpness >= min_sharpness
    checks.append(sharpness_ok)
    if not sharpness_ok:
        issues.append({
            "code": "IMAGE_TOO_BLURRY",
            "message": "Image appears too blurry or out of focus. Upload a sharper product photo.",
            "expected": {"min_sharpness": min_sharpness},
            "actual": {"sharpness": round(sharpness, 2)},
        })

    brightness_ok = settings.PRODUCT_IMAGE_MIN_BRIGHTNESS <= brightness <= settings.PRODUCT_IMAGE_MAX_BRIGHTNESS
    checks.append(brightness_ok)
    if not brightness_ok:
        problem = "too dark" if brightness < settings.PRODUCT_IMAGE_MIN_BRIGHTNESS else "too bright/washed out"
        issues.append({
            "code": "IMAGE_BRIGHTNESS_INVALID",
            "message": f"Image is {problem}. Use clearer, balanced lighting.",
            "expected": {
                "min_brightness": settings.PRODUCT_IMAGE_MIN_BRIGHTNESS,
                "max_brightness": settings.PRODUCT_IMAGE_MAX_BRIGHTNESS,
            },
            "actual": {"brightness": round(brightness, 2)},
        })

    if is_primary:
        background_ok = whiteness >= min_whiteness
        checks.append(background_ok)
        if not background_ok:
            issues.append({
                "code": "PRIMARY_BACKGROUND_NOT_CLEAN_WHITE",
                "message": (
                    "Primary product image must use a clean, mostly white background. "
                    "Use additional images for lifestyle or contextual backgrounds."
                ),
                "expected": {"min_background_whiteness_percent": min_whiteness},
                "actual": {"background_whiteness_percent": round(whiteness, 2)},
            })

    score = round((sum(1 for check in checks if check) / max(1, len(checks))) * 100)
    return ImageQualityResult(
        passed=not issues,
        score=score,
        image_type=image_type,
        metrics={
            "width": width,
            "height": height,
            "megapixels": round(megapixels, 3),
            "aspect_ratio": round(aspect_ratio, 3),
            "sharpness": round(sharpness, 2),
            "brightness": round(brightness, 2),
            "background_whiteness_percent": round(whiteness, 2),
        },
        issues=issues,
    )


def ensure_product_image_quality(image: Image.Image, *, is_primary: bool) -> ImageQualityResult:
    if not settings.PRODUCT_IMAGE_QUALITY_ENABLED:
        return ImageQualityResult(True, 100, "primary" if is_primary else "additional", {}, [])
    result = analyze_product_image_quality(image, is_primary=is_primary)
    if not result.passed:
        raise _quality_http_error(result)
    return result


def ensure_stored_product_image_primary_quality(storage_key: str | None) -> ImageQualityResult:
    if not settings.PRODUCT_IMAGE_QUALITY_ENABLED:
        return ImageQualityResult(True, 100, "primary", {}, [])
    if not storage_key:
        raise _file_http_error(
            code="PRODUCT_IMAGE_REUPLOAD_REQUIRED",
            message="This legacy image cannot be verified as a primary image. Please upload the image file again.",
            http_status=status.HTTP_409_CONFLICT,
        )
    image_path = (settings.upload_path / storage_key).resolve()
    upload_root = settings.upload_path.resolve()
    if upload_root not in image_path.parents or not image_path.exists():
        raise _file_http_error(
            code="PRODUCT_IMAGE_REUPLOAD_REQUIRED",
            message="The stored image file is unavailable for quality validation. Please upload it again.",
            http_status=status.HTTP_409_CONFLICT,
        )
    try:
        with Image.open(image_path) as image:
            image.load()
            image = ImageOps.exif_transpose(image)
            return ensure_product_image_quality(image, is_primary=True)
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise _file_http_error(
            code="PRODUCT_IMAGE_CORRUPT",
            message="The stored product image is corrupt. Please upload a replacement.",
        ) from exc


def _prepare_image(raw: bytes, *, is_primary: bool) -> tuple[Image.Image, str, str]:
    if not raw:
        raise _file_http_error(code="PRODUCT_IMAGE_EMPTY", message="Uploaded image is empty")
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise _file_http_error(
            code="PRODUCT_IMAGE_TOO_LARGE",
            message=f"Each image must not exceed {settings.MAX_UPLOAD_SIZE_MB} MB",
            http_status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            detected_format = (probe.format or "").upper()
            probe.verify()
        if detected_format not in ALLOWED_FORMATS:
            raise _file_http_error(
                code="PRODUCT_IMAGE_FORMAT_INVALID",
                message="Only JPEG, PNG and WEBP images are allowed",
            )
        image = Image.open(io.BytesIO(raw))
        image.load()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise _file_http_error(
            code="PRODUCT_IMAGE_CORRUPT",
            message="The uploaded file is not a valid, readable image",
        ) from exc

    image = ImageOps.exif_transpose(image)
    if image.width < 1 or image.height < 1:
        raise _file_http_error(code="PRODUCT_IMAGE_DIMENSIONS_INVALID", message="Image dimensions are invalid")

    # Quality is evaluated before resizing so sellers cannot pass a low-resolution
    # source merely because the storage pipeline normalizes its dimensions.
    ensure_product_image_quality(image, is_primary=is_primary)

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
    is_primary: bool = False,
) -> StoredProductImage:
    raw = await file.read()
    image, detected_format, mime_type = _prepare_image(raw, is_primary=is_primary)

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
