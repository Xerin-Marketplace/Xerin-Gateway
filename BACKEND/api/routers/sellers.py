from uuid import UUID, uuid4
from datetime import datetime, timezone
from pathlib import Path
import mimetypes
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
    Query,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from api.schemas import SellerProfileUpdate, SellerProfileResponse
from api.deps import get_db, get_current_user
from api.models import (
    User,
    Seller,
    SellerProfile,
    SellerKYCDocument,
    SellerPayoutAccount,
    SellerStatus,
    BusinessCategory,
    SellerBusinessCategory,
    Role,
    UserRole,
)
from api.schemas import (
    SellerResponse,
    SellerUpdate,
    SellerKYCResponse,
    SellerPayoutCreate,
    SellerPayoutResponse,
    PaginatedKYCResponse,
    PaginatedPayoutResponse,
    PaginatedSellerResponse,
    SellerApplicationRequest,
    SellerApplicationStatusResponse,
)

router = APIRouter(prefix="/sellers", tags=["Sellers"])

UPLOAD_DIR = Path("uploads/kyc")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_KYC_DOCUMENTS = [
    "tin",
    "business_profile",
    "business_registration",
]


def _assign_role(db: Session, user_id: UUID, role_name: str) -> None:
    role = db.query(Role).filter(Role.name == role_name).first()
    if role is None:
        raise RuntimeError(
            f"Required role '{role_name}' does not exist. "
            "Run: python -m api.seed_permissions"
        )

    existing = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.role_id == role.id,
    ).first()
    if existing is None:
        db.add(UserRole(user_id=user_id, role_id=role.id))


def _validated_categories(db: Session, category_ids: list[UUID]) -> list[BusinessCategory]:
    unique_ids = list(dict.fromkeys(category_ids))
    categories = db.query(BusinessCategory).filter(
        BusinessCategory.id.in_(unique_ids)
    ).all()
    if len(categories) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="One or more business categories are invalid",
        )
    return categories


def get_my_seller(db: Session, current_user: User) -> Seller:
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    return seller


def require_admin(current_user: User):
    allowed_roles = ["super_admin", "admin"]

    user_roles = [
        user_role.role.name
        for user_role in current_user.roles
    ]

    if not any(role in allowed_roles for role in user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


@router.post(
    "/apply",
    response_model=SellerResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_become_seller(
    data: SellerApplicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attach a pending seller application to the authenticated customer account.

    The existing user, email, phone, password, customer role, addresses and order
    history are preserved. A second user account is never created.
    """
    existing = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "This account already has a seller application",
                "seller_id": str(existing.id),
                "status": existing.status.value if hasattr(existing.status, "value") else str(existing.status),
            },
        )

    _validated_categories(db, data.business_category_ids)

    seller = Seller(
        user_id=current_user.id,
        business_name=data.business_name.strip(),
        contact_email=str(data.contact_email).strip().lower() if data.contact_email else current_user.email,
        contact_phone=data.contact_phone or current_user.phone,
        agreement_accepted=True,
        status=SellerStatus.pending,
    )

    try:
        db.add(seller)
        db.flush()

        db.add(
            SellerProfile(
                seller_id=seller.id,
                business_description=data.business_description,
                business_country=data.business_country,
                business_region=data.business_region,
                business_city=data.business_city,
                business_address=data.business_address,
                product_description=data.product_description,
                years_in_business=data.years_in_business,
                website_url=data.website_url,
            )
        )

        for category_id in data.business_category_ids:
            db.add(
                SellerBusinessCategory(
                    seller_id=seller.id,
                    business_category_id=category_id,
                )
            )

        db.commit()
        db.refresh(seller)
    except Exception:
        db.rollback()
        raise

    return seller


@router.get(
    "/application-status",
    response_model=SellerApplicationStatusResponse,
)
def get_seller_application_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if seller is None:
        return SellerApplicationStatusResponse(has_application=False)

    seller_status = seller.status.value if hasattr(seller.status, "value") else str(seller.status)
    return SellerApplicationStatusResponse(
        has_application=True,
        seller_id=seller.id,
        status=seller_status,
        business_name=seller.business_name,
        can_access_seller_dashboard=seller.status == SellerStatus.approved,
        can_upload_kyc=seller.status in {
            SellerStatus.pending,
            SellerStatus.under_review,
            SellerStatus.rejected,
        },
        submitted_at=seller.created_at,
        approved_at=seller.approved_at,
    )


@router.get("/me", response_model=SellerResponse)
def get_my_seller_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_my_seller(db, current_user)


@router.patch("/me", response_model=SellerResponse)
def update_my_seller_profile(
    data: SellerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = get_my_seller(db, current_user)

    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(seller, key, value)

    db.commit()
    db.refresh(seller)

    return seller

@router.get("/profile", response_model=SellerProfileResponse)
def get_my_seller_business_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = get_my_seller(db, current_user)

    profile = db.query(SellerProfile).filter(
        SellerProfile.seller_id == seller.id
    ).first()

    if not profile:
        profile = SellerProfile(seller_id=seller.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return profile


@router.patch("/profile", response_model=SellerProfileResponse)
def update_my_seller_business_profile(
    data: SellerProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = get_my_seller(db, current_user)

    profile = db.query(SellerProfile).filter(
        SellerProfile.seller_id == seller.id
    ).first()

    if not profile:
        profile = SellerProfile(seller_id=seller.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)

    return profile


# =========================================================
# KYC DOCUMENTS
# =========================================================

ALLOWED_KYC_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_KYC_FILE_SIZE = 15 * 1024 * 1024  # 15 MB


def _normalize_document_type(document_type: str) -> str:
    normalized = document_type.strip().lower()
    if normalized not in REQUIRED_KYC_DOCUMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid document type. Use: "
                "tin, business_profile, business_registration"
            ),
        )
    return normalized


def _ensure_kyc_is_editable(seller: Seller) -> None:
    """Prevent approved sellers from changing documents used for approval."""
    if seller.status == SellerStatus.approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "KYC documents cannot be changed after seller approval. "
                "Contact an administrator if a correction is required."
            ),
        )


def _get_owned_kyc_document(
    db: Session,
    seller_id: UUID,
    document_id: UUID,
) -> SellerKYCDocument:
    document = db.query(SellerKYCDocument).filter(
        SellerKYCDocument.id == document_id,
        SellerKYCDocument.seller_id == seller_id,
    ).first()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC document not found",
        )

    return document


def _resolve_kyc_file_path(document: SellerKYCDocument) -> Path:
    """Resolve the saved file and prevent access outside uploads/kyc."""
    upload_root = UPLOAD_DIR.resolve()
    file_path = Path(document.document_url)

    if not file_path.is_absolute():
        file_path = file_path.resolve()
    else:
        file_path = file_path.resolve()

    try:
        file_path.relative_to(upload_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid document path",
        ) from exc

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found",
        )

    return file_path


def _delete_kyc_file(document_url: str | None) -> None:
    if not document_url:
        return

    try:
        upload_root = UPLOAD_DIR.resolve()
        file_path = Path(document_url).resolve()
        file_path.relative_to(upload_root)

        if file_path.exists() and file_path.is_file():
            file_path.unlink()
    except (OSError, ValueError):
        # Database operations should not fail only because old file cleanup failed.
        pass


async def _save_kyc_upload(
    seller_id: UUID,
    document_type: str,
    file: UploadFile,
) -> str:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded document must have a filename",
        )

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_KYC_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, JPG, JPEG, and PNG files are allowed",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded document is empty",
        )

    if len(content) > MAX_KYC_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="KYC document must not exceed 15 MB",
        )

    file_name = (
        f"{seller_id}_{document_type}_{uuid4().hex}{extension}"
    )
    file_path = UPLOAD_DIR / file_name
    file_path.write_bytes(content)

    return str(file_path)


def _synchronize_seller_kyc_status(db: Session, seller: Seller) -> None:
    uploaded_types = {
        row.document_type
        for row in db.query(SellerKYCDocument).filter(
            SellerKYCDocument.seller_id == seller.id
        ).all()
    }

    has_all_required_documents = all(
        required_type in uploaded_types
        for required_type in REQUIRED_KYC_DOCUMENTS
    )

    seller.status = (
        SellerStatus.under_review
        if has_all_required_documents
        else SellerStatus.pending
    )
    seller.approved_at = None


@router.post(
    "/kyc-documents",
    response_model=SellerKYCResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_kyc_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create one KYC document or replace the document of the same type."""
    seller = get_my_seller(db, current_user)
    _ensure_kyc_is_editable(seller)

    normalized_type = _normalize_document_type(document_type)
    new_document_url = await _save_kyc_upload(
        seller_id=seller.id,
        document_type=normalized_type,
        file=file,
    )

    existing_document = db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller.id,
        SellerKYCDocument.document_type == normalized_type,
    ).first()

    old_document_url = None

    try:
        if existing_document is not None:
            old_document_url = existing_document.document_url
            existing_document.document_url = new_document_url
            existing_document.status = "pending"
            existing_document.rejection_reason = None
            document = existing_document
        else:
            document = SellerKYCDocument(
                seller_id=seller.id,
                document_type=normalized_type,
                document_url=new_document_url,
                status="pending",
            )
            db.add(document)

        db.flush()
        _synchronize_seller_kyc_status(db, seller)
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        _delete_kyc_file(new_document_url)
        raise

    if old_document_url and old_document_url != new_document_url:
        _delete_kyc_file(old_document_url)

    return document


@router.get("/kyc-documents", response_model=PaginatedKYCResponse)
def get_my_kyc_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    document_type: str | None = None,
    status_filter: str | None = None,
):
    """List the authenticated seller's KYC document records."""
    seller = get_my_seller(db, current_user)

    query = db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller.id
    )

    if document_type:
        query = query.filter(
            SellerKYCDocument.document_type == document_type.strip().lower()
        )

    if status_filter:
        query = query.filter(
            SellerKYCDocument.status == status_filter.strip().lower()
        )

    total = query.count()
    documents = (
        query.order_by(SellerKYCDocument.uploaded_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": documents,
    }


@router.post(
    "/kyc-documents/bulk",
    response_model=list[SellerKYCResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_bulk_kyc_documents(
    tin_file: UploadFile = File(...),
    business_profile_file: UploadFile = File(...),
    business_registration_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or replace all three required KYC documents in one request."""
    seller = get_my_seller(db, current_user)
    _ensure_kyc_is_editable(seller)

    files_map = {
        "tin": tin_file,
        "business_profile": business_profile_file,
        "business_registration": business_registration_file,
    }

    saved_urls: dict[str, str] = {}
    old_urls: list[str] = []
    uploaded_documents: list[SellerKYCDocument] = []

    try:
        # Save all files first. If one fails, remove files already saved.
        for document_type, upload in files_map.items():
            saved_urls[document_type] = await _save_kyc_upload(
                seller_id=seller.id,
                document_type=document_type,
                file=upload,
            )

        for document_type, document_url in saved_urls.items():
            existing_document = db.query(SellerKYCDocument).filter(
                SellerKYCDocument.seller_id == seller.id,
                SellerKYCDocument.document_type == document_type,
            ).first()

            if existing_document is not None:
                if existing_document.document_url:
                    old_urls.append(existing_document.document_url)
                existing_document.document_url = document_url
                existing_document.status = "pending"
                existing_document.rejection_reason = None
                document = existing_document
            else:
                document = SellerKYCDocument(
                    seller_id=seller.id,
                    document_type=document_type,
                    document_url=document_url,
                    status="pending",
                )
                db.add(document)

            uploaded_documents.append(document)

        db.flush()
        _synchronize_seller_kyc_status(db, seller)
        db.commit()

        for document in uploaded_documents:
            db.refresh(document)
    except Exception:
        db.rollback()
        for saved_url in saved_urls.values():
            _delete_kyc_file(saved_url)
        raise

    for old_url in old_urls:
        if old_url not in saved_urls.values():
            _delete_kyc_file(old_url)

    return uploaded_documents


@router.get(
    "/kyc-documents/{document_id}",
    response_model=SellerKYCResponse,
)
def get_my_kyc_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return metadata for one document owned by the authenticated seller."""
    seller = get_my_seller(db, current_user)
    return _get_owned_kyc_document(db, seller.id, document_id)


@router.get("/kyc-documents/{document_id}/view")
def view_my_kyc_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream an owned PDF/image inline for browser visualization."""
    seller = get_my_seller(db, current_user)
    document = _get_owned_kyc_document(db, seller.id, document_id)
    file_path = _resolve_kyc_file_path(document)

    media_type, _ = mimetypes.guess_type(str(file_path))

    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=file_path.name,
        content_disposition_type="inline",
    )


@router.put(
    "/kyc-documents/{document_id}",
    response_model=SellerKYCResponse,
)
async def update_my_kyc_document(
    document_id: UUID,
    document_type: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a document type, replace its file, or perform both changes."""
    seller = get_my_seller(db, current_user)
    _ensure_kyc_is_editable(seller)

    document = _get_owned_kyc_document(db, seller.id, document_id)

    if document_type is None and file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide document_type, file, or both",
        )

    new_document_type = document.document_type
    if document_type is not None:
        new_document_type = _normalize_document_type(document_type)

        duplicate = db.query(SellerKYCDocument).filter(
            SellerKYCDocument.seller_id == seller.id,
            SellerKYCDocument.document_type == new_document_type,
            SellerKYCDocument.id != document.id,
        ).first()

        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A {new_document_type} document already exists",
            )

    old_document_url = document.document_url
    new_document_url = old_document_url

    if file is not None:
        new_document_url = await _save_kyc_upload(
            seller_id=seller.id,
            document_type=new_document_type,
            file=file,
        )

    try:
        document.document_type = new_document_type
        document.document_url = new_document_url
        document.status = "pending"
        document.rejection_reason = None

        _synchronize_seller_kyc_status(db, seller)
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        if new_document_url != old_document_url:
            _delete_kyc_file(new_document_url)
        raise

    if new_document_url != old_document_url:
        _delete_kyc_file(old_document_url)

    return document


@router.delete(
    "/kyc-documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_my_kyc_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a mistaken KYC upload owned by the authenticated seller."""
    seller = get_my_seller(db, current_user)
    _ensure_kyc_is_editable(seller)

    document = _get_owned_kyc_document(db, seller.id, document_id)
    document_url = document.document_url

    try:
        db.delete(document)
        db.flush()
        _synchronize_seller_kyc_status(db, seller)
        db.commit()
    except Exception:
        db.rollback()
        raise

    _delete_kyc_file(document_url)
    return None


@router.get("/kyc-status")
def get_my_kyc_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = get_my_seller(db, current_user)

    documents = db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller.id
    ).all()

    uploaded_documents = [doc.document_type for doc in documents]
    missing_documents = [
        doc_type
        for doc_type in REQUIRED_KYC_DOCUMENTS
        if doc_type not in uploaded_documents
    ]

    return {
        "seller_status": seller.status.value if seller.status else None,
        "required_documents": REQUIRED_KYC_DOCUMENTS,
        "uploaded_documents": uploaded_documents,
        "missing_documents": missing_documents,
        "can_submit_for_review": len(missing_documents) == 0,
    }


@router.post("/payout-accounts", response_model=SellerPayoutResponse, status_code=status.HTTP_201_CREATED)
def create_payout_account(
    data: SellerPayoutCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = get_my_seller(db, current_user)

    if data.is_default:
        db.query(SellerPayoutAccount).filter(
            SellerPayoutAccount.seller_id == seller.id
        ).update({"is_default": False})

    payout = SellerPayoutAccount(
        seller_id=seller.id,
        account_type=data.account_type,
        provider=data.provider,
        account_name=data.account_name,
        account_number=data.account_number,
        currency=data.currency,
        is_default=data.is_default,
    )

    db.add(payout)
    db.commit()
    db.refresh(payout)

    return payout


@router.get("/payout-accounts", response_model=PaginatedPayoutResponse)
def get_my_payout_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    seller = get_my_seller(db, current_user)

    query = db.query(SellerPayoutAccount).filter(
        SellerPayoutAccount.seller_id == seller.id
    )

    total = query.count()

    accounts = query.order_by(SellerPayoutAccount.created_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": accounts,
    }


@router.delete("/payout-accounts/{account_id}")
def delete_payout_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = get_my_seller(db, current_user)

    payout = db.query(SellerPayoutAccount).filter(
        SellerPayoutAccount.id == account_id,
        SellerPayoutAccount.seller_id == seller.id,
    ).first()

    if not payout:
        raise HTTPException(status_code=404, detail="Payout account not found")

    db.delete(payout)
    db.commit()

    return {"message": "Payout account deleted successfully"}

@router.get("/admin/pending", response_model=PaginatedSellerResponse)
def admin_get_pending_sellers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    require_admin(current_user)

    query = db.query(Seller).filter(
        Seller.status == SellerStatus.under_review
    )

    total = query.count()

    sellers = query.order_by(Seller.created_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": sellers,
    }


@router.get("/admin/documents/{document_id}/view")
def admin_view_seller_kyc_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream a seller KYC document inline for an administrator."""
    require_admin(current_user)

    document = db.query(SellerKYCDocument).filter(
        SellerKYCDocument.id == document_id
    ).first()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC document not found",
        )

    file_path = _resolve_kyc_file_path(document)
    media_type, _ = mimetypes.guess_type(str(file_path))

    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=file_path.name,
        content_disposition_type="inline",
    )


@router.get("/admin/documents/{document_id}/download")
def admin_download_seller_kyc_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a seller KYC document as an administrator."""
    require_admin(current_user)

    document = db.query(SellerKYCDocument).filter(
        SellerKYCDocument.id == document_id
    ).first()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC document not found",
        )

    file_path = _resolve_kyc_file_path(document)
    media_type, _ = mimetypes.guess_type(str(file_path))

    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=file_path.name,
        content_disposition_type="attachment",
    )


@router.get("/admin/{seller_id}/documents", response_model=list[SellerKYCResponse])
def admin_get_seller_documents(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller_id
    ).all()


@router.post("/admin/{seller_id}/approve", response_model=SellerResponse)
def admin_approve_seller(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    seller = db.query(Seller).filter(Seller.id == seller_id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    documents = db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller.id
    ).all()

    uploaded_types = [doc.document_type for doc in documents]

    missing = [
        doc_type for doc_type in REQUIRED_KYC_DOCUMENTS
        if doc_type not in uploaded_types
    ]

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Seller is missing documents: {missing}",
        )

    seller.status = SellerStatus.approved
    seller.approved_at = datetime.now(timezone.utc)
    _assign_role(db, seller.user_id, "seller")
    db.commit()
    db.refresh(seller)

    return seller

@router.post("/admin/{seller_id}/reject", response_model=SellerResponse)
def admin_reject_seller(
    seller_id: UUID,
    reason: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    seller = db.query(Seller).filter(Seller.id == seller_id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    seller.status = SellerStatus.rejected

    db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller.id
    ).update({
        "status": "rejected",
        "rejection_reason": reason,
    })

    db.commit()
    db.refresh(seller)

    return seller