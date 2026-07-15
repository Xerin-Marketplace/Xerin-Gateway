import math
import re
import shutil
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode, StoreStatus
from api.models import Seller, SellerStatus, Store, User
from api.permissions import require_permission
from api.schemas import (
    PaginatedStoreResponse,
    StorePublicResponse,
    StoreResponse,
    StoreUpdate,
)

router = APIRouter(prefix="/stores", tags=["Stores"])


STORE_UPLOAD_DIR = Path("uploads/stores")
STORE_LOGO_DIR = STORE_UPLOAD_DIR / "logos"
STORE_BANNER_DIR = STORE_UPLOAD_DIR / "banners"

STORE_LOGO_DIR.mkdir(parents=True, exist_ok=True)
STORE_BANNER_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_LOGO_SIZE = 5 * 1024 * 1024
MAX_BANNER_SIZE = 10 * 1024 * 1024


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")

    return value or "store"


def generate_unique_slug(
    db: Session,
    store_name: str,
    exclude_store_id: uuid.UUID | None = None,
) -> str:
    base_slug = slugify(store_name)
    slug = base_slug
    counter = 1

    while True:
        query = db.query(Store).filter(Store.slug == slug)

        if exclude_store_id:
            query = query.filter(Store.id != exclude_store_id)

        if not query.first():
            return slug

        counter += 1
        slug = f"{base_slug}-{counter}"


def get_current_seller(
    db: Session,
    current_user: User,
) -> Seller:
    seller = (
        db.query(Seller)
        .filter(Seller.user_id == current_user.id)
        .first()
    )

    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller account not found",
        )

    return seller


def get_or_create_store(
    db: Session,
    seller: Seller,
) -> Store:
    store = (
        db.query(Store)
        .filter(Store.seller_id == seller.id)
        .first()
    )

    if store:
        return store

    store_name = seller.business_name
    slug = generate_unique_slug(db, store_name)

    store = Store(
        seller_id=seller.id,
        store_name=store_name,
        slug=slug,
        description=None,
        contact_email=seller.contact_email,
        contact_phone=seller.contact_phone,
        status=StoreStatus.draft,
        is_verified=False,
    )

    db.add(store)
    db.commit()
    db.refresh(store)

    return store


def validate_store_image(
    file: UploadFile,
    max_size: int,
) -> tuple[str, bytes]:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename",
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, JPEG, PNG and WEBP images are allowed",
        )

    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image content type",
        )

    return extension


async def save_store_image(
    file: UploadFile,
    directory: Path,
    store_id: uuid.UUID,
    image_type: str,
    max_size: int,
) -> str:
    extension = validate_store_image(file, max_size)

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if len(content) > max_size:
        maximum_mb = max_size // (1024 * 1024)

        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image must not exceed {maximum_mb} MB",
        )

    filename = (
        f"{store_id}_{image_type}_{uuid.uuid4().hex}{extension}"
    )

    file_path = directory / filename
    file_path.write_bytes(content)

    return f"/uploads/stores/{directory.name}/{filename}"


def delete_old_local_file(file_url: str | None) -> None:
    if not file_url:
        return

    normalized_path = file_url.lstrip("/")
    file_path = Path(normalized_path)

    try:
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
    except OSError:
        pass


@router.get(
    "/me",
    response_model=StoreResponse,
)
def get_my_store(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(
            PermissionCode.view_own_store.value
        )
    ),
):
    seller = get_current_seller(db, current_user)
    return get_or_create_store(db, seller)


@router.patch(
    "/me",
    response_model=StoreResponse,
)
def update_my_store(
    data: StoreUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(
            PermissionCode.update_own_store.value
        )
    ),
):
    seller = get_current_seller(db, current_user)
    store = get_or_create_store(db, seller)

    update_data = data.model_dump(exclude_unset=True)

    if "store_name" in update_data:
        store_name = update_data["store_name"].strip()

        if not store_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Store name cannot be empty",
            )

        update_data["store_name"] = store_name
        update_data["slug"] = generate_unique_slug(
            db=db,
            store_name=store_name,
            exclude_store_id=store.id,
        )

    if "opening_time" in update_data and "closing_time" in update_data:
        opening_time = update_data["opening_time"]
        closing_time = update_data["closing_time"]

        if opening_time and closing_time and opening_time >= closing_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Opening time must be earlier than closing time",
            )

    for field, value in update_data.items():
        setattr(store, field, value)

    # Store is publicly active only after seller approval.
    if seller.status == SellerStatus.approved:
        store.status = StoreStatus.active
        store.is_verified = True
    else:
        store.status = StoreStatus.draft
        store.is_verified = False

    db.commit()
    db.refresh(store)

    return store


@router.post(
    "/me/logo",
    response_model=StoreResponse,
)
async def upload_store_logo(
    logo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(
            PermissionCode.upload_store_logo.value
        )
    ),
):
    seller = get_current_seller(db, current_user)
    store = get_or_create_store(db, seller)

    old_logo = store.logo_url

    new_logo_url = await save_store_image(
        file=logo,
        directory=STORE_LOGO_DIR,
        store_id=store.id,
        image_type="logo",
        max_size=MAX_LOGO_SIZE,
    )

    store.logo_url = new_logo_url

    db.commit()
    db.refresh(store)

    delete_old_local_file(old_logo)

    return store


@router.post(
    "/me/banner",
    response_model=StoreResponse,
)
async def upload_store_banner(
    banner: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(
            PermissionCode.upload_store_banner.value
        )
    ),
):
    seller = get_current_seller(db, current_user)
    store = get_or_create_store(db, seller)

    old_banner = store.banner_url

    new_banner_url = await save_store_image(
        file=banner,
        directory=STORE_BANNER_DIR,
        store_id=store.id,
        image_type="banner",
        max_size=MAX_BANNER_SIZE,
    )

    store.banner_url = new_banner_url

    db.commit()
    db.refresh(store)

    delete_old_local_file(old_banner)

    return store


@router.get(
    "",
    response_model=PaginatedStoreResponse,
)
def list_public_stores(
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1),
    country: str | None = Query(default=None),
    region: str | None = Query(default=None),
    district: str | None = Query(default=None),
    is_verified: bool | None = Query(default=None),
    is_featured: bool | None = Query(default=None),
    minimum_rating: float | None = Query(
        default=None,
        ge=0,
        le=5,
    ),
):
    query = db.query(Store).filter(
        Store.status == StoreStatus.active
    )

    if search:
        search_value = f"%{search.strip()}%"

        query = query.filter(
            or_(
                Store.store_name.ilike(search_value),
                Store.description.ilike(search_value),
                Store.country.ilike(search_value),
                Store.region.ilike(search_value),
            )
        )

    if country:
        query = query.filter(
            Store.country.ilike(country.strip())
        )

    if region:
        query = query.filter(
            Store.region.ilike(region.strip())
        )

    if district:
        query = query.filter(
            Store.district.ilike(district.strip())
        )

    if is_verified is not None:
        query = query.filter(
            Store.is_verified == is_verified
        )

    if is_featured is not None:
        query = query.filter(
            Store.is_featured == is_featured
        )

    if minimum_rating is not None:
        query = query.filter(
            Store.rating >= minimum_rating
        )

    total = query.count()
    total_pages = math.ceil(total / page_size) if total else 0

    stores = (
        query.order_by(
            Store.is_featured.desc(),
            Store.rating.desc(),
            Store.created_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "results": stores,
    }


@router.get(
    "/{store_slug}",
    response_model=StorePublicResponse,
)
def get_public_store(
    store_slug: str,
    db: Session = Depends(get_db),
):
    store = (
        db.query(Store)
        .filter(
            Store.slug == store_slug,
            Store.status == StoreStatus.active,
        )
        .first()
    )

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found",
        )

    return store