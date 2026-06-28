from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_db
from api.deps import get_current_user
from api.models import User, Seller, SellerKYCDocument, SellerPayoutAccount
from api.schemas import (
    SellerCreate,
    SellerResponse,
    SellerUpdate,
    SellerKYCCreate,
    SellerKYCResponse,
    SellerPayoutCreate,
    SellerPayoutResponse,
)

router = APIRouter(prefix="/sellers", tags=["Sellers"])


@router.post("/register", response_model=SellerResponse, status_code=status.HTTP_201_CREATED)
def register_seller(
    data: SellerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already have a seller account"
        )

    seller = Seller(
        user_id=current_user.id,
        business_name=data.business_name,
        business_category=data.business_category,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        agreement_accepted=data.agreement_accepted,
        status="pending",
    )

    db.add(seller)
    db.commit()
    db.refresh(seller)

    return seller


@router.get("/me", response_model=SellerResponse)
def get_my_seller_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    return seller


@router.patch("/me", response_model=SellerResponse)
def update_my_seller_profile(
    data: SellerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(seller, key, value)

    db.commit()
    db.refresh(seller)

    return seller


@router.post("/kyc-documents", response_model=SellerKYCResponse, status_code=status.HTTP_201_CREATED)
def upload_kyc_document(
    data: SellerKYCCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    document = SellerKYCDocument(
        seller_id=seller.id,
        document_type=data.document_type,
        document_url=data.document_url,
        status="pending",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


@router.get("/kyc-documents", response_model=list[SellerKYCResponse])
def get_my_kyc_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    return db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller.id
    ).order_by(SellerKYCDocument.uploaded_at.desc()).all()


@router.post("/payout-accounts", response_model=SellerPayoutResponse, status_code=status.HTTP_201_CREATED)
def create_payout_account(
    data: SellerPayoutCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

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


@router.get("/payout-accounts", response_model=list[SellerPayoutResponse])
def get_my_payout_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    return db.query(SellerPayoutAccount).filter(
        SellerPayoutAccount.seller_id == seller.id
    ).all()


@router.delete("/payout-accounts/{account_id}")
def delete_payout_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    payout = db.query(SellerPayoutAccount).filter(
        SellerPayoutAccount.id == account_id,
        SellerPayoutAccount.seller_id == seller.id,
    ).first()

    if not payout:
        raise HTTPException(status_code=404, detail="Payout account not found")

    db.delete(payout)
    db.commit()

    return {"message": "Payout account deleted successfully"}