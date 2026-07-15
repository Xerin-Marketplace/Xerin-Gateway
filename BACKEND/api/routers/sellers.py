from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from api.schemas import SellerProfileUpdate, SellerProfileResponse
from api.deps import get_db, get_current_user
from api.models import User, Seller, SellerProfile, SellerKYCDocument, SellerPayoutAccount, SellerStatus
from fastapi import Query
from api.schemas import (
    SellerResponse,
    SellerUpdate,
    SellerKYCResponse,
    SellerPayoutCreate,
    SellerPayoutResponse,
    PaginatedKYCResponse,
    PaginatedPayoutResponse,
    PaginatedSellerResponse,
)

router = APIRouter(prefix="/sellers", tags=["Sellers"])

UPLOAD_DIR = Path("uploads/kyc")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_KYC_DOCUMENTS = [
    "tin",
    "business_profile",
    "business_registration",
]


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


@router.post("/kyc-documents", response_model=SellerKYCResponse, status_code=status.HTTP_201_CREATED)
async def upload_kyc_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = get_my_seller(db, current_user)

    document_type = document_type.strip().lower()

    if document_type not in REQUIRED_KYC_DOCUMENTS:
        raise HTTPException(
            status_code=400,
            detail="Invalid document type. Use: tin, business_profile, business_registration",
        )

    allowed_extensions = [".pdf", ".jpg", ".jpeg", ".png"]
    file_extension = Path(file.filename).suffix.lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, JPG, JPEG, and PNG files are allowed",
        )

    existing_doc = db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller.id,
        SellerKYCDocument.document_type == document_type,
    ).first()

    file_name = f"{seller.id}_{document_type}{file_extension}"
    file_path = UPLOAD_DIR / file_name

    content = await file.read()
    file_path.write_bytes(content)

    document_url = str(file_path)

    if existing_doc:
        existing_doc.document_url = document_url
        existing_doc.status = "pending"
        existing_doc.rejection_reason = None
        db.commit()
        db.refresh(existing_doc)
        document = existing_doc
    else:
        document = SellerKYCDocument(
            seller_id=seller.id,
            document_type=document_type,
            document_url=document_url,
            status="pending",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

    uploaded_types = {
        doc.document_type
        for doc in db.query(SellerKYCDocument).filter(
            SellerKYCDocument.seller_id == seller.id
        ).all()
    }

    if all(doc_type in uploaded_types for doc_type in REQUIRED_KYC_DOCUMENTS):
        seller.status = SellerStatus.under_review
        db.commit()

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
    seller = get_my_seller(db, current_user)

    query = db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller.id
    )

    if document_type:
        query = query.filter(SellerKYCDocument.document_type == document_type)

    if status_filter:
        query = query.filter(SellerKYCDocument.status == status_filter)

    total = query.count()

    documents = query.order_by(SellerKYCDocument.uploaded_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": documents,
    }
    
    
@router.post(
    "/kyc-documents/bulk",
    response_model=list[SellerKYCResponse],
    status_code=status.HTTP_201_CREATED
)
async def upload_bulk_kyc_documents(
    tin_file: UploadFile = File(...),
    business_profile_file: UploadFile = File(...),
    business_registration_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = get_my_seller(db, current_user)

    files_map = {
        "tin": tin_file,
        "business_profile": business_profile_file,
        "business_registration": business_registration_file,
    }

    allowed_extensions = [".pdf", ".jpg", ".jpeg", ".png"]
    uploaded_documents = []

    for document_type, file in files_map.items():
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"{document_type} must be PDF, JPG, JPEG, or PNG",
            )

        file_name = f"{seller.id}_{document_type}{file_extension}"
        file_path = UPLOAD_DIR / file_name

        content = await file.read()
        file_path.write_bytes(content)

        document_url = str(file_path)

        existing_doc = db.query(SellerKYCDocument).filter(
            SellerKYCDocument.seller_id == seller.id,
            SellerKYCDocument.document_type == document_type,
        ).first()

        if existing_doc:
            existing_doc.document_url = document_url
            existing_doc.status = "pending"
            existing_doc.rejection_reason = None
            document = existing_doc
        else:
            document = SellerKYCDocument(
                seller_id=seller.id,
                document_type=document_type,
                document_url=document_url,
                status="pending",
            )
            db.add(document)

        uploaded_documents.append(document)

    seller.status = SellerStatus.under_review

    db.commit()

    for document in uploaded_documents:
        db.refresh(document)

    return uploaded_documents

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
        doc for doc in REQUIRED_KYC_DOCUMENTS if doc not in uploaded_documents
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