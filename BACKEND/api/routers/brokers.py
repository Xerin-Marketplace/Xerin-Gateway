from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.config import settings
from api.deps import get_current_user, get_db
from api.enums import PermissionCode
from api.models import Broker, BrokerKYCDocument, BrokerStatus, BrokerStatusHistory, User, Product, ProductImage, ProductStatus, Inventory, Category, Brand, MarketplaceSettings, PaymentCurrency
from api.permissions import require_permission
from api.services.product_image_service import MAX_PRODUCT_IMAGES, store_product_image, delete_product_image_files
from api.services.broker_listing_expiry import expire_broker_listings
from api.schemas import (
    BrokerKYCResponse,
    BrokerKYCStatusResponse,
    BrokerResponse,
    BrokerReviewRequest,
    BrokerUpdateRequest,
    PaginatedBrokerKYCResponse,
    PaginatedBrokerResponse,
    BrokerProductCreate,
    BrokerProductUpdate,
    BrokerProductResponse,
    ProductImageResponse,
)

router = APIRouter(prefix="/brokers", tags=["Brokers"])
REQUIRED_KYC_DOCUMENTS = {"national_id", "profile_photo", "selfie"}
ALLOWED_KYC_DOCUMENTS = REQUIRED_KYC_DOCUMENTS | {"national_id_back", "passport"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


def _broker_for_user(db: Session, user: User) -> Broker:
    broker = db.query(Broker).filter(Broker.user_id == user.id).first()
    if broker is None:
        raise HTTPException(status_code=404, detail="Broker profile not found")
    return broker


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _transition(db: Session, broker: Broker, new_status: BrokerStatus, actor: User | None, reason: str | None = None) -> None:
    old = _status_value(broker.status) if broker.status else None
    broker.status = new_status
    broker.status_reason = reason
    now = datetime.now(timezone.utc)
    if new_status == BrokerStatus.approved:
        broker.approved_at, broker.rejected_at, broker.suspended_at = now, None, None
    elif new_status == BrokerStatus.rejected:
        broker.rejected_at = now
    elif new_status == BrokerStatus.suspended:
        broker.suspended_at = now
    db.add(BrokerStatusHistory(broker_id=broker.id, from_status=old, to_status=new_status.value, reason=reason, changed_by_user_id=actor.id if actor else None))


@router.get("/me", response_model=BrokerResponse)
def me(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _broker_for_user(db, current_user)


@router.patch("/me", response_model=BrokerResponse)
def update_me(data: BrokerUpdateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _broker_for_user(db, current_user)
    if broker.status in {BrokerStatus.under_review, BrokerStatus.approved, BrokerStatus.suspended} and data.nida_number is not None and data.nida_number != broker.nida_number:
        raise HTTPException(status_code=409, detail="NIDA/National ID cannot be changed while the account is under review, approved, or suspended")
    for key, value in data.model_dump(exclude_unset=True).items():
        if isinstance(value, str): value = value.strip()
        setattr(broker, key, value or None)
    db.commit(); db.refresh(broker)
    return broker


@router.get("/kyc-status", response_model=BrokerKYCStatusResponse)
def kyc_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _broker_for_user(db, current_user)
    docs = db.query(BrokerKYCDocument).filter(BrokerKYCDocument.broker_id == broker.id).all()
    uploaded = {d.document_type for d in docs}
    missing = sorted(REQUIRED_KYC_DOCUMENTS - uploaded)
    return BrokerKYCStatusResponse(broker_status=_status_value(broker.status), required_documents=sorted(REQUIRED_KYC_DOCUMENTS), uploaded_documents=sorted(uploaded), missing_documents=missing, can_submit_for_review=bool(broker.nida_number) and not missing and broker.status in {BrokerStatus.pending_kyc, BrokerStatus.rejected}, can_use_broker_features=broker.status == BrokerStatus.approved)


@router.get("/kyc-documents", response_model=PaginatedBrokerKYCResponse)
def list_kyc(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _broker_for_user(db, current_user)
    q = db.query(BrokerKYCDocument).filter(BrokerKYCDocument.broker_id == broker.id)
    total = q.count(); rows = q.order_by(BrokerKYCDocument.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "results": rows}


@router.post("/kyc-documents", response_model=BrokerKYCResponse, status_code=status.HTTP_201_CREATED)
async def upload_kyc(document_type: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _broker_for_user(db, current_user)
    if broker.status in {BrokerStatus.under_review, BrokerStatus.approved, BrokerStatus.suspended}:
        raise HTTPException(status_code=409, detail="KYC documents cannot be changed in the current broker status")
    document_type = document_type.strip().lower()
    if document_type not in ALLOWED_KYC_DOCUMENTS:
        raise HTTPException(status_code=422, detail=f"Invalid document type. Allowed: {', '.join(sorted(ALLOWED_KYC_DOCUMENTS))}")
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Only JPG, PNG, WEBP, or PDF files are allowed")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="KYC file must be 8 MB or smaller")
    ext = Path(file.filename or "document").suffix.lower() or ".bin"
    folder = settings.upload_path / "broker_kyc" / str(broker.id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{document_type}-{uuid.uuid4().hex}{ext}"
    target.write_bytes(content)
    existing = db.query(BrokerKYCDocument).filter(BrokerKYCDocument.broker_id == broker.id, BrokerKYCDocument.document_type == document_type).first()
    if existing:
        old = Path(existing.file_path)
        if old.exists(): old.unlink(missing_ok=True)
        doc = existing; doc.file_path = str(target); doc.original_filename = file.filename; doc.mime_type = file.content_type; doc.status = "pending"; doc.rejection_reason = None; doc.reviewed_at = None
    else:
        doc = BrokerKYCDocument(broker_id=broker.id, document_type=document_type, file_path=str(target), original_filename=file.filename, mime_type=file.content_type, status="pending")
        db.add(doc)
    if broker.status == BrokerStatus.rejected:
        _transition(db, broker, BrokerStatus.pending_kyc, current_user, "KYC document resubmitted")
    db.commit(); db.refresh(doc)
    return doc


@router.delete("/kyc-documents/{document_id}")
def delete_kyc(document_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _broker_for_user(db, current_user)
    if broker.status in {BrokerStatus.under_review, BrokerStatus.approved, BrokerStatus.suspended}:
        raise HTTPException(status_code=409, detail="KYC documents cannot be changed in the current broker status")
    doc = db.query(BrokerKYCDocument).filter(BrokerKYCDocument.id == document_id, BrokerKYCDocument.broker_id == broker.id).first()
    if not doc: raise HTTPException(status_code=404, detail="KYC document not found")
    path = Path(doc.file_path); db.delete(doc); db.commit()
    if path.exists(): path.unlink(missing_ok=True)
    return {"message": "KYC document deleted"}


@router.post("/submit-kyc", response_model=BrokerResponse)
def submit_kyc(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _broker_for_user(db, current_user)
    uploaded = {d.document_type for d in db.query(BrokerKYCDocument).filter(BrokerKYCDocument.broker_id == broker.id).all()}
    missing = REQUIRED_KYC_DOCUMENTS - uploaded
    if not broker.nida_number: raise HTTPException(status_code=422, detail="NIDA/National ID number is required")
    if missing: raise HTTPException(status_code=422, detail=f"Missing KYC documents: {', '.join(sorted(missing))}")
    if broker.status not in {BrokerStatus.pending_kyc, BrokerStatus.rejected}: raise HTTPException(status_code=409, detail="KYC cannot be submitted in the current status")
    _transition(db, broker, BrokerStatus.kyc_submitted, current_user, "Broker submitted KYC for review")
    db.commit(); db.refresh(broker); return broker


@router.get("/admin", response_model=PaginatedBrokerResponse)
def admin_list(status_filter: str | None = Query(None, alias="status"), search: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.admin_brokers_read.value))):
    q = db.query(Broker).join(User, Broker.user_id == User.id)
    if status_filter: q = q.filter(Broker.status == status_filter)
    if search:
        term=f"%{search.strip()}%"; q=q.filter((Broker.broker_code.ilike(term)) | (User.email.ilike(term)) | (User.phone.ilike(term)) | (User.first_name.ilike(term)) | (User.last_name.ilike(term)))
    total=q.count(); rows=q.order_by(Broker.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "results": rows}


@router.get("/admin/{broker_id}", response_model=BrokerResponse)
def admin_detail(broker_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.admin_brokers_read.value))):
    broker=db.query(Broker).filter(Broker.id==broker_id).first()
    if not broker: raise HTTPException(status_code=404, detail="Broker not found")
    return broker


@router.get("/admin/{broker_id}/documents", response_model=list[BrokerKYCResponse])
def admin_documents(broker_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.admin_brokers_read.value))):
    return db.query(BrokerKYCDocument).filter(BrokerKYCDocument.broker_id==broker_id).order_by(BrokerKYCDocument.created_at.desc()).all()


@router.get("/admin/{broker_id}/documents/{document_id}/view")
def admin_document_view(broker_id: uuid.UUID, document_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.admin_brokers_read.value))):
    doc=db.query(BrokerKYCDocument).filter(BrokerKYCDocument.id==document_id, BrokerKYCDocument.broker_id==broker_id).first()
    if not doc: raise HTTPException(status_code=404, detail="KYC document not found")
    path=Path(doc.file_path).resolve(); root=(settings.upload_path / "broker_kyc").resolve()
    if root not in path.parents or not path.exists(): raise HTTPException(status_code=404, detail="KYC file not found")
    return FileResponse(path, media_type=doc.mime_type or "application/octet-stream", filename=doc.original_filename or path.name)


@router.post("/admin/{broker_id}/start-review", response_model=BrokerResponse)
def start_review(broker_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.admin_brokers_review.value))):
    broker=db.query(Broker).filter(Broker.id==broker_id).first()
    if not broker: raise HTTPException(status_code=404, detail="Broker not found")
    if broker.status != BrokerStatus.kyc_submitted: raise HTTPException(status_code=409, detail="Broker KYC has not been submitted")
    _transition(db, broker, BrokerStatus.under_review, current_user, "Admin started KYC review"); db.commit(); db.refresh(broker); return broker


@router.post("/admin/{broker_id}/approve", response_model=BrokerResponse)
def approve(broker_id: uuid.UUID, data: BrokerReviewRequest = BrokerReviewRequest(), db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.admin_brokers_review.value))):
    broker=db.query(Broker).filter(Broker.id==broker_id).first()
    if not broker: raise HTTPException(status_code=404, detail="Broker not found")
    if broker.status not in {BrokerStatus.kyc_submitted, BrokerStatus.under_review}: raise HTTPException(status_code=409, detail="Broker is not ready for approval")
    docs=db.query(BrokerKYCDocument).filter(BrokerKYCDocument.broker_id==broker.id).all(); uploaded={d.document_type for d in docs}
    if not broker.nida_number or REQUIRED_KYC_DOCUMENTS-uploaded: raise HTTPException(status_code=422, detail="Broker KYC is incomplete")
    now=datetime.now(timezone.utc)
    for d in docs: d.status="approved"; d.rejection_reason=None; d.reviewed_at=now
    _transition(db, broker, BrokerStatus.approved, current_user, data.reason or "KYC approved"); db.commit(); db.refresh(broker); return broker


@router.post("/admin/{broker_id}/reject", response_model=BrokerResponse)
def reject(broker_id: uuid.UUID, data: BrokerReviewRequest, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.admin_brokers_review.value))):
    if not data.reason: raise HTTPException(status_code=422, detail="Rejection reason is required")
    broker=db.query(Broker).filter(Broker.id==broker_id).first()
    if not broker: raise HTTPException(status_code=404, detail="Broker not found")
    now=datetime.now(timezone.utc)
    for d in db.query(BrokerKYCDocument).filter(BrokerKYCDocument.broker_id==broker.id).all(): d.status="rejected"; d.rejection_reason=data.reason; d.reviewed_at=now
    _transition(db, broker, BrokerStatus.rejected, current_user, data.reason); db.commit(); db.refresh(broker); return broker


@router.post("/admin/{broker_id}/suspend", response_model=BrokerResponse)
def suspend(broker_id: uuid.UUID, data: BrokerReviewRequest, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.admin_brokers_suspend.value))):
    if not data.reason: raise HTTPException(status_code=422, detail="Suspension reason is required")
    broker=db.query(Broker).filter(Broker.id==broker_id).first()
    if not broker: raise HTTPException(status_code=404, detail="Broker not found")
    _transition(db, broker, BrokerStatus.suspended, current_user, data.reason); db.commit(); db.refresh(broker); return broker


# -----------------------------
# B2 — Broker-owned products
# -----------------------------

def _approved_broker_for_user(db: Session, current_user: User) -> Broker:
    broker = _broker_for_user(db, current_user)
    if broker.status != BrokerStatus.approved:
        raise HTTPException(status_code=403, detail="Broker account must be approved before using own products")
    return broker


def _broker_product(db: Session, broker: Broker, product_id: uuid.UUID) -> Product:
    expire_broker_listings(db, broker_id=broker.id)
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.broker_id == broker.id,
        Product.listing_owner_type == "broker",
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Broker product not found")
    return product


def _broker_product_payload(db: Session, product: Product) -> dict:
    inventory = db.query(Inventory).filter(Inventory.product_id == product.id, Inventory.variant_id.is_(None)).first()
    remaining = None
    if product.listing_expires_at and product.is_active and product.status == ProductStatus.approved:
        remaining = max(0, int((product.listing_expires_at - datetime.now(timezone.utc)).total_seconds()))
    payload = BrokerProductResponse.model_validate(product).model_dump()
    payload.update({
        "quantity": inventory.quantity if inventory else 0,
        "reserved_quantity": inventory.reserved_quantity if inventory else 0,
        "available_quantity": inventory.available_quantity if inventory else 0,
        "seconds_remaining": remaining,
    })
    return payload


def _unique_broker_slug(db: Session, broker: Broker, name: str) -> str:
    base = "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in name).split())[:180] or "broker-product"
    base = f"{base}-{broker.broker_code.lower()}"
    slug = base
    counter = 2
    while db.query(Product).filter(Product.slug == slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def _broker_sku(db: Session, broker: Broker) -> str:
    while True:
        sku = f"{broker.broker_code}-{uuid.uuid4().hex[:8].upper()}"
        if not db.query(Product).filter(Product.sku == sku).first():
            return sku


@router.get("/products", response_model=list[BrokerProductResponse])
def my_broker_products(
    product_status: str | None = Query(None, alias="status"),
    search: str | None = Query(None, max_length=200),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _approved_broker_for_user(db, current_user)
    expire_broker_listings(db, broker_id=broker.id)
    query = db.query(Product).filter(Product.broker_id == broker.id, Product.listing_owner_type == "broker")
    if product_status:
        query = query.filter(Product.status == product_status)
    if search and search.strip():
        query = query.filter(Product.name.ilike(f"%{search.strip()}%"))
    rows = query.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()
    return [_broker_product_payload(db, row) for row in rows]


@router.post("/products", response_model=BrokerProductResponse, status_code=201)
def create_broker_product(
    data: BrokerProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _approved_broker_for_user(db, current_user)
    if not db.query(Category).filter(Category.id == data.category_id).first():
        raise HTTPException(status_code=404, detail="Category not found")
    if data.brand_id and not db.query(Brand).filter(Brand.id == data.brand_id).first():
        raise HTTPException(status_code=404, detail="Brand not found")
    currency = db.query(PaymentCurrency).filter(PaymentCurrency.code == data.currency, PaymentCurrency.is_active.is_(True)).first()
    if not currency:
        raise HTTPException(status_code=422, detail=f"Currency {data.currency} is not enabled for listings")
    product = Product(
        seller_id=None,
        store_id=None,
        broker_id=broker.id,
        listing_owner_type="broker",
        category_id=data.category_id,
        brand_id=data.brand_id,
        sku=_broker_sku(db, broker),
        name=data.name.strip(),
        slug=_unique_broker_slug(db, broker, data.name),
        description=data.description,
        seller_base_price=data.price,
        seller_sale_price=data.sale_price,
        commission_rate_snapshot=0,
        commission_amount_snapshot=0,
        price=data.price,
        sale_price=data.sale_price,
        currency=currency.code,
        weight=data.weight,
        fulfillment_location=data.fulfillment_location.strip(),
        status=ProductStatus.draft,
        is_active=True,
    )
    db.add(product)
    db.flush()
    inventory = Inventory(product_id=product.id, variant_id=None, quantity=data.quantity, reserved_quantity=0, available_quantity=data.quantity, updated_by_id=current_user.id)
    db.add(inventory)
    db.commit(); db.refresh(product)
    return _broker_product_payload(db, product)


@router.get("/products/{product_id}", response_model=BrokerProductResponse)
def get_broker_product(product_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _approved_broker_for_user(db, current_user)
    return _broker_product_payload(db, _broker_product(db, broker, product_id))


@router.patch("/products/{product_id}", response_model=BrokerProductResponse)
def update_broker_product(product_id: uuid.UUID, data: BrokerProductUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _approved_broker_for_user(db, current_user)
    product = _broker_product(db, broker, product_id)
    if product.status == ProductStatus.pending_review:
        raise HTTPException(status_code=409, detail="Product is under review")
    if product.status == ProductStatus.approved and product.is_active:
        raise HTTPException(status_code=409, detail="A live 24-hour listing cannot be edited. Archive it and create a new listing")
    values = data.model_dump(exclude_unset=True)
    quantity = values.pop("quantity", None)
    if "category_id" in values and not db.query(Category).filter(Category.id == values["category_id"]).first():
        raise HTTPException(status_code=404, detail="Category not found")
    if values.get("brand_id") and not db.query(Brand).filter(Brand.id == values["brand_id"]).first():
        raise HTTPException(status_code=404, detail="Brand not found")
    if "currency" in values:
        currency = db.query(PaymentCurrency).filter(PaymentCurrency.code == values["currency"], PaymentCurrency.is_active.is_(True)).first()
        if not currency: raise HTTPException(status_code=422, detail="Currency is not enabled for listings")
        values["currency"] = currency.code
    for key, value in values.items(): setattr(product, key, value)
    if "name" in values: product.slug = _unique_broker_slug(db, broker, values["name"])
    if quantity is not None:
        inventory = db.query(Inventory).filter(Inventory.product_id == product.id, Inventory.variant_id.is_(None)).first()
        if not inventory: inventory=Inventory(product_id=product.id, variant_id=None, reserved_quantity=0); db.add(inventory)
        if quantity < (inventory.reserved_quantity or 0):
            raise HTTPException(status_code=409, detail="Quantity cannot be lower than reserved stock")
        inventory.quantity=quantity; inventory.available_quantity=quantity-(inventory.reserved_quantity or 0); inventory.updated_by_id=current_user.id
    product.status=ProductStatus.draft; product.rejection_reason=None; product.submitted_at=None; product.approved_at=None; product.approved_by_user_id=None; product.approval_method=None; product.listing_expires_at=None; product.listing_expired_at=None; product.is_active=True
    db.commit(); db.refresh(product)
    return _broker_product_payload(db, product)


@router.post("/products/{product_id}/images", response_model=list[ProductImageResponse], status_code=201)
async def upload_broker_product_images(product_id: uuid.UUID, files: list[UploadFile] = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _approved_broker_for_user(db, current_user)
    product = _broker_product(db, broker, product_id)
    if product.status in {ProductStatus.pending_review, ProductStatus.approved}:
        raise HTTPException(status_code=409, detail="Images cannot be changed while a listing is under review or live")
    existing = db.query(ProductImage).filter(ProductImage.product_id == product.id).count()
    if existing + len(files) > MAX_PRODUCT_IMAGES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_PRODUCT_IMAGES} images allowed")
    created=[]
    next_order=existing
    for i,file in enumerate(files):
        stored=await store_product_image(file, seller_id=broker.id, product_id=product.id)
        img=ProductImage(product_id=product.id,image_url=stored.image_url,thumbnail_url=stored.thumbnail_url,storage_key=stored.storage_key,original_filename=stored.original_filename,mime_type=stored.mime_type,file_size=stored.file_size,width=stored.width,height=stored.height,alt_text=product.name,display_order=next_order+i,is_primary=(existing==0 and i==0),uploaded_by_user_id=current_user.id)
        db.add(img); created.append(img)
    db.commit()
    for img in created: db.refresh(img)
    return created


@router.delete("/products/{product_id}/images/{image_id}")
def delete_broker_product_image(product_id: uuid.UUID, image_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker=_approved_broker_for_user(db,current_user); product=_broker_product(db,broker,product_id)
    if product.status in {ProductStatus.pending_review, ProductStatus.approved}: raise HTTPException(status_code=409, detail="Images cannot be changed while a listing is under review or live")
    image=db.query(ProductImage).filter(ProductImage.id==image_id,ProductImage.product_id==product.id).first()
    if not image: raise HTTPException(status_code=404, detail="Image not found")
    key=image.storage_key; thumb=image.thumbnail_url; was_primary=image.is_primary; db.delete(image); db.flush()
    if was_primary:
        first=db.query(ProductImage).filter(ProductImage.product_id==product.id).order_by(ProductImage.display_order.asc()).first()
        if first: first.is_primary=True
    db.commit(); delete_product_image_files(key, thumb)
    return {"message":"Image deleted"}


@router.post("/products/{product_id}/publish", response_model=BrokerProductResponse)
def publish_broker_product(product_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker=_approved_broker_for_user(db,current_user); product=_broker_product(db,broker,product_id)
    if product.status not in {ProductStatus.draft, ProductStatus.rejected, ProductStatus.inactive}:
        raise HTTPException(status_code=409, detail="Only draft, rejected or archived broker products can be published")
    if not db.query(ProductImage).filter(ProductImage.product_id==product.id).first(): raise HTTPException(status_code=400, detail="Upload at least one product image before publishing")
    inventory=db.query(Inventory).filter(Inventory.product_id==product.id,Inventory.variant_id.is_(None)).first()
    if not inventory or inventory.available_quantity < 1: raise HTTPException(status_code=400, detail="Available stock must be at least 1")
    now=datetime.now(timezone.utc); market=db.query(MarketplaceSettings).filter(MarketplaceSettings.singleton_key==1).first(); auto=bool(market and market.auto_approve_products)
    product.submitted_at=now; product.rejection_reason=None; product.is_active=True; product.listing_expired_at=None
    if auto:
        product.status=ProductStatus.approved; product.approved_at=now; product.approved_by_user_id=None; product.approval_method="automatic"; product.listing_expires_at=now+timedelta(hours=24)
    else:
        product.status=ProductStatus.pending_review; product.approved_at=None; product.approved_by_user_id=None; product.approval_method=None; product.listing_expires_at=None
    db.commit(); db.refresh(product); return _broker_product_payload(db,product)


@router.delete("/products/{product_id}")
def archive_broker_product(product_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker=_approved_broker_for_user(db,current_user); product=_broker_product(db,broker,product_id)
    if product.status == ProductStatus.pending_review: raise HTTPException(status_code=409, detail="A product under review cannot be archived")
    product.is_active=False; product.status=ProductStatus.inactive
    if product.listing_expires_at and not product.listing_expired_at: product.listing_expired_at=datetime.now(timezone.utc)
    db.commit(); return {"message":"Broker product archived"}
