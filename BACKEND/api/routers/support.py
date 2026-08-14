from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session, selectinload

from api.deps import get_db
from api.enums import PermissionCode
from api.models import Order, Seller, Shipment, SupportTicket, SupportTicketMessage, User
from api.permissions import get_user_permissions, require_any_permission, require_permission
from api.schemas import (
    PaginatedSupportTicketResponse,
    SupportTicketCreate,
    SupportTicketMessageCreate,
    SupportTicketMessageResponse,
    SupportTicketResponse,
    SupportTicketUpdate,
)

router = APIRouter(tags=["Support"])


def _ticket_number() -> str:
    return f"SUP-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:8].upper()}"


def _display_name(user: User | None) -> str | None:
    if not user:
        return None
    name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return name or user.email


def _serialize_message(message: SupportTicketMessage) -> SupportTicketMessageResponse:
    return SupportTicketMessageResponse(
        id=message.id,
        sender_id=message.sender_id,
        sender_name=_display_name(message.sender),
        sender_role=message.sender_role,
        message=message.message,
        visibility=message.visibility,
        created_at=message.created_at,
    )


def _serialize_ticket(ticket: SupportTicket, *, include_internal_messages: bool) -> SupportTicketResponse:
    participants = []
    if ticket.customer:
        participants.append({"id": ticket.customer.id, "user_id": ticket.customer.id, "name": _display_name(ticket.customer), "email": ticket.customer.email, "role": "customer"})
    if ticket.seller and ticket.seller.user:
        participants.append({"id": ticket.seller.id, "user_id": ticket.seller.user_id, "name": ticket.seller.business_name, "email": ticket.seller.contact_email or ticket.seller.user.email, "role": "seller"})
    if ticket.assigned_to:
        participants.append({"id": ticket.assigned_to.id, "user_id": ticket.assigned_to.id, "name": _display_name(ticket.assigned_to), "email": ticket.assigned_to.email, "role": "staff"})
    if ticket.shipment:
        participants.append({"id": ticket.shipment.id, "user_id": None, "name": ticket.shipment.carrier_name, "email": None, "role": "logistics"})

    return SupportTicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        user_id=ticket.customer_id,
        customer_name=_display_name(ticket.customer),
        customer_email=ticket.customer.email if ticket.customer else None,
        subject=ticket.subject,
        description=ticket.description,
        category=ticket.category,
        channel=ticket.channel,
        priority=ticket.priority,
        status=ticket.status,
        assigned_to_id=ticket.assigned_to_id,
        assigned_to_name=_display_name(ticket.assigned_to),
        order_id=ticket.order_id,
        seller_id=ticket.seller_id,
        seller_name=ticket.seller.business_name if ticket.seller else None,
        shipment_id=ticket.shipment_id,
        logistics_provider=ticket.shipment.carrier_name if ticket.shipment else None,
        participants=participants,
        messages=[_serialize_message(m) for m in ticket.messages if include_internal_messages or m.visibility != "internal"],
        resolution_note=ticket.resolution_note,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _load_ticket(db: Session, ticket_id: UUID) -> SupportTicket | None:
    return (
        db.query(SupportTicket)
        .options(
            selectinload(SupportTicket.customer),
            selectinload(SupportTicket.assigned_to),
            selectinload(SupportTicket.seller).selectinload(Seller.user),
            selectinload(SupportTicket.order),
            selectinload(SupportTicket.shipment),
            selectinload(SupportTicket.messages).selectinload(SupportTicketMessage.sender),
        )
        .filter(SupportTicket.id == ticket_id)
        .first()
    )


def _has_permission(db: Session, user: User, code: str) -> bool:
    return code in get_user_permissions(db, user)


def _is_ticket_participant(ticket: SupportTicket, user: User) -> bool:
    return (
        ticket.customer_id == user.id
        or (ticket.seller is not None and ticket.seller.user_id == user.id)
        or ticket.assigned_to_id == user.id
    )


def _require_ticket_access(db: Session, ticket: SupportTicket, user: User) -> None:
    if _has_permission(db, user, PermissionCode.support_tickets_read.value):
        return
    if not _is_ticket_participant(ticket, user):
        raise HTTPException(status_code=403, detail="You do not have access to this support ticket")


@router.post("/support/tickets", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
def create_support_ticket(
    data: SupportTicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.support_tickets_create.value)),
):
    if data.priority not in {"low", "medium", "high", "urgent"}:
        raise HTTPException(status_code=400, detail="Invalid ticket priority")
    if data.order_id is not None:
        order = db.query(Order).filter(Order.id == data.order_id).first()
        if not order or order.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Order not found")
    if data.seller_id is not None and not db.query(Seller).filter(Seller.id == data.seller_id).first():
        raise HTTPException(status_code=404, detail="Seller not found")
    if data.shipment_id is not None:
        shipment = db.query(Shipment).join(Order, Shipment.order_id == Order.id).filter(
            Shipment.id == data.shipment_id,
            Order.user_id == current_user.id,
        ).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

    ticket = SupportTicket(
        ticket_number=_ticket_number(),
        customer_id=current_user.id,
        seller_id=data.seller_id,
        order_id=data.order_id,
        shipment_id=data.shipment_id,
        subject=data.subject.strip(),
        description=data.description,
        category=data.category,
        channel=data.channel,
        priority=data.priority,
        status="open",
    )
    db.add(ticket)
    db.flush()

    if data.description:
        db.add(SupportTicketMessage(
            ticket_id=ticket.id,
            sender_id=current_user.id,
            sender_role="customer",
            message=data.description,
            visibility="all",
        ))

    db.commit()
    return _serialize_ticket(_load_ticket(db, ticket.id), include_internal_messages=False)


@router.get("/support/tickets/my", response_model=PaginatedSupportTicketResponse)
def list_my_support_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.support_tickets_read_own.value)),
):
    query = db.query(SupportTicket).outerjoin(Seller, SupportTicket.seller_id == Seller.id).filter(or_(
        SupportTicket.customer_id == current_user.id,
        Seller.user_id == current_user.id,
        SupportTicket.assigned_to_id == current_user.id,
    ))
    total = query.count()
    rows = (
        query.options(
            selectinload(SupportTicket.customer),
            selectinload(SupportTicket.assigned_to),
            selectinload(SupportTicket.seller).selectinload(Seller.user),
            selectinload(SupportTicket.shipment),
            selectinload(SupportTicket.messages).selectinload(SupportTicketMessage.sender),
        )
        .order_by(SupportTicket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "page": page, "page_size": page_size, "total_pages": 0 if total == 0 else (total + page_size - 1) // page_size, "results": [_serialize_ticket(t, include_internal_messages=False) for t in rows]}


@router.get("/support/tickets/{ticket_id}", response_model=SupportTicketResponse)
def get_support_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(PermissionCode.support_tickets_read_own.value, PermissionCode.support_tickets_read.value)),
):
    ticket = _load_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    _require_ticket_access(db, ticket, current_user)
    return _serialize_ticket(ticket, include_internal_messages=_has_permission(db, current_user, PermissionCode.support_tickets_read.value))


@router.post("/support/tickets/{ticket_id}/messages", response_model=SupportTicketMessageResponse, status_code=status.HTTP_201_CREATED)
def reply_support_ticket(
    ticket_id: UUID,
    data: SupportTicketMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(PermissionCode.support_tickets_reply_own.value, PermissionCode.support_tickets_reply.value)),
):
    ticket = _load_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    _require_ticket_access(db, ticket, current_user)

    can_reply_all = _has_permission(db, current_user, PermissionCode.support_tickets_reply.value)
    if data.visibility == "internal" and not can_reply_all:
        raise HTTPException(status_code=403, detail="Internal notes require support_tickets:reply")

    sender_role = "customer"
    if ticket.seller is not None and ticket.seller.user_id == current_user.id:
        sender_role = "seller"
    elif can_reply_all:
        sender_role = "staff"

    message = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        sender_role=sender_role,
        message=data.message.strip(),
        visibility=data.visibility,
    )
    db.add(message)
    if ticket.status in {"resolved", "closed"}:
        ticket.status = "in_progress"
        ticket.resolved_at = None
        ticket.closed_at = None
    db.commit()
    db.refresh(message)
    return _serialize_message(message)


@router.get("/admin/support-tickets", response_model=PaginatedSupportTicketResponse)
def list_all_support_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    ticket_status: str | None = Query(None, alias="status"),
    priority: str | None = Query(None),
    channel: str | None = Query(None),
    category: str | None = Query(None),
    participant_role: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.support_tickets_read.value)),
):
    query = db.query(SupportTicket).join(User, SupportTicket.customer_id == User.id).outerjoin(
        Seller, SupportTicket.seller_id == Seller.id
    ).outerjoin(Shipment, SupportTicket.shipment_id == Shipment.id)

    if ticket_status:
        query = query.filter(SupportTicket.status == ticket_status)
    if priority:
        query = query.filter(SupportTicket.priority == priority)
    if channel:
        query = query.filter(SupportTicket.channel == channel)
    if category:
        query = query.filter(SupportTicket.category == category)
    if participant_role == "seller":
        query = query.filter(SupportTicket.seller_id.isnot(None))
    elif participant_role == "logistics":
        query = query.filter(SupportTicket.shipment_id.isnot(None))
    elif participant_role == "customer":
        query = query.filter(SupportTicket.customer_id.isnot(None))

    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(or_(
            SupportTicket.ticket_number.ilike(pattern),
            SupportTicket.subject.ilike(pattern),
            SupportTicket.description.ilike(pattern),
            cast(SupportTicket.order_id, String).ilike(pattern),
            User.first_name.ilike(pattern),
            User.last_name.ilike(pattern),
            User.email.ilike(pattern),
            Seller.business_name.ilike(pattern),
            Shipment.tracking_number.ilike(pattern),
            Shipment.carrier_name.ilike(pattern),
        ))

    total = query.count()
    rows = (
        query.options(
            selectinload(SupportTicket.customer),
            selectinload(SupportTicket.assigned_to),
            selectinload(SupportTicket.seller).selectinload(Seller.user),
            selectinload(SupportTicket.shipment),
            selectinload(SupportTicket.messages).selectinload(SupportTicketMessage.sender),
        )
        .order_by(SupportTicket.updated_at.desc().nullslast(), SupportTicket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "page": page, "page_size": page_size, "total_pages": 0 if total == 0 else (total + page_size - 1) // page_size, "results": [_serialize_ticket(t, include_internal_messages=True) for t in rows]}


@router.get("/admin/support-tickets/{ticket_id}", response_model=SupportTicketResponse)
def get_admin_support_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.support_tickets_read.value)),
):
    ticket = _load_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    return _serialize_ticket(ticket, include_internal_messages=True)


@router.patch("/admin/support-tickets/{ticket_id}", response_model=SupportTicketResponse)
def update_admin_support_ticket(
    ticket_id: UUID,
    data: SupportTicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(
        PermissionCode.support_tickets_manage.value,
        PermissionCode.support_tickets_assign.value,
        PermissionCode.support_tickets_resolve.value,
    )),
):
    ticket = _load_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")

    granted = get_user_permissions(db, current_user)
    update_data = data.model_dump(exclude_unset=True)

    if "assigned_to_id" in update_data:
        if PermissionCode.support_tickets_assign.value not in granted:
            raise HTTPException(status_code=403, detail="Permission denied. Required: support_tickets:assign")
        assignee_id = update_data["assigned_to_id"]
        if assignee_id is not None and not db.query(User).filter(User.id == assignee_id).first():
            raise HTTPException(status_code=404, detail="Assignee not found")
        ticket.assigned_to_id = assignee_id

    if "priority" in update_data:
        if PermissionCode.support_tickets_manage.value not in granted:
            raise HTTPException(status_code=403, detail="Permission denied. Required: support_tickets:manage")
        if update_data["priority"] not in {"low", "medium", "high", "urgent"}:
            raise HTTPException(status_code=400, detail="Invalid priority")
        ticket.priority = update_data["priority"]

    if "status" in update_data:
        next_status = update_data["status"]
        if next_status not in {"open", "pending", "in_progress", "processing", "resolved", "closed"}:
            raise HTTPException(status_code=400, detail="Invalid status")
        if next_status in {"resolved", "closed"}:
            if PermissionCode.support_tickets_resolve.value not in granted:
                raise HTTPException(status_code=403, detail="Permission denied. Required: support_tickets:resolve")
            if next_status == "resolved":
                ticket.resolved_at = datetime.now(timezone.utc)
            else:
                ticket.closed_at = datetime.now(timezone.utc)
        else:
            if PermissionCode.support_tickets_manage.value not in granted:
                raise HTTPException(status_code=403, detail="Permission denied. Required: support_tickets:manage")
        ticket.status = next_status

    if "resolution_note" in update_data:
        if PermissionCode.support_tickets_resolve.value not in granted:
            raise HTTPException(status_code=403, detail="Permission denied. Required: support_tickets:resolve")
        ticket.resolution_note = update_data["resolution_note"]

    db.commit()
    return _serialize_ticket(_load_ticket(db, ticket.id), include_internal_messages=True)


@router.post("/admin/support-tickets/{ticket_id}/messages", response_model=SupportTicketMessageResponse, status_code=status.HTTP_201_CREATED)
def reply_admin_support_ticket(
    ticket_id: UUID,
    data: SupportTicketMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.support_tickets_reply.value)),
):
    ticket = _load_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")

    message = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        sender_role="staff",
        message=data.message.strip(),
        visibility=data.visibility,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return _serialize_message(message)
