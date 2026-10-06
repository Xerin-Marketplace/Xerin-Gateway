from __future__ import annotations

import uuid
from datetime import datetime, timezone
from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.enums import PermissionCode
from api.models import Seller, Shipment, SupportTicket, SupportTicketMessage, User
from api.permissions import require_permission
from api.schemas import (
    PaginatedSupportTickets,
    SupportTicketCreate,
    SupportTicketMessageCreate,
    SupportTicketMessageResponse,
    SupportTicketParticipantResponse,
    SupportTicketResponse,
    SupportTicketUpdate,
)

router = APIRouter(prefix="/support", tags=["Support"])
admin_router = APIRouter(prefix="/admin/support-tickets", tags=["Admin Support"])

_VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
_VALID_STATUSES = {"open", "pending", "in_progress", "resolved", "closed", "cancelled"}
_VALID_VISIBILITY = {"all", "internal"}


def _display_name(user: User | None) -> str | None:
    if user is None:
        return None
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return name or user.email


def _sender_role(sender: User | None, ticket: SupportTicket) -> str:
    if sender is None:
        return "customer"
    role_names = {ur.role.name for ur in (sender.roles or []) if ur.role is not None}
    if "admin" in role_names or "super_admin" in role_names or "staff" in role_names:
        return "admin"
    if sender.id == ticket.user_id:
        return "customer"
    if "seller" in role_names:
        return "seller"
    return next(iter(role_names), "customer")


def _message_response(message: SupportTicketMessage, ticket: SupportTicket) -> SupportTicketMessageResponse:
    sender = message.sender
    return SupportTicketMessageResponse(
        id=message.id,
        sender_id=message.sender_id,
        sender_name=_display_name(sender),
        sender_role=_sender_role(sender, ticket),
        message=message.message,
        visibility=message.visibility,
        created_at=message.created_at,
    )


def _participants(ticket: SupportTicket) -> list[SupportTicketParticipantResponse]:
    participants: list[SupportTicketParticipantResponse] = []

    customer = ticket.user
    if customer is not None:
        participants.append(SupportTicketParticipantResponse(
            user_id=customer.id, name=_display_name(customer),
            email=customer.email, role="customer",
        ))

    assignee = ticket.assigned_to
    if assignee is not None:
        participants.append(SupportTicketParticipantResponse(
            user_id=assignee.id, name=_display_name(assignee),
            email=assignee.email, role="admin",
        ))

    seller = ticket.seller
    if seller is not None:
        participants.append(SupportTicketParticipantResponse(
            id=seller.id, user_id=seller.user_id, name=seller.business_name,
            email=seller.contact_email, role="seller",
        ))

    return participants


def _ticket_response(ticket: SupportTicket, *, include_internal: bool) -> SupportTicketResponse:
    messages = [
        _message_response(m, ticket)
        for m in (ticket.messages or [])
        if include_internal or m.visibility != "internal"
    ]
    shipment: Shipment | None = ticket.shipment
    return SupportTicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        user_id=ticket.user_id,
        customer_name=_display_name(ticket.user),
        customer_email=ticket.user.email if ticket.user else None,
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
        logistics_provider=shipment.carrier_name if shipment else None,
        participants=_participants(ticket),
        messages=messages,
        resolution_note=ticket.resolution_note,
        first_response_due_at=ticket.first_response_due_at,
        resolution_due_at=ticket.resolution_due_at,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _next_ticket_number(db: Session) -> str:
    for _ in range(5):
        candidate = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        exists = db.query(SupportTicket.id).filter(SupportTicket.ticket_number == candidate).first()
        if not exists:
            return candidate
    return f"TKT-{uuid.uuid4().hex[:12].upper()}"


def _paginate(query, page: int, page_size: int, serialize) -> PaginatedSupportTickets:
    total = query.count()
    rows = (
        query.order_by(SupportTicket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedSupportTickets(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
        results=[serialize(row) for row in rows],
    )


# ---------------------------------------------------------------- Customer


@router.post("/tickets", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: SupportTicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.priority not in _VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority")

    ticket = SupportTicket(
        ticket_number=_next_ticket_number(db),
        user_id=current_user.id,
        subject=data.subject.strip(),
        description=data.description,
        category=data.category,
        channel=data.channel or "customer",
        priority=data.priority,
        status="open",
        order_id=data.order_id,
        seller_id=data.seller_id,
        shipment_id=data.shipment_id,
    )
    db.add(ticket)
    db.flush()

    if data.description:
        db.add(SupportTicketMessage(
            ticket_id=ticket.id,
            sender_id=current_user.id,
            message=data.description,
            visibility="all",
        ))

    db.commit()
    db.refresh(ticket)
    return _ticket_response(ticket, include_internal=False)


@router.get("/tickets/my", response_model=PaginatedSupportTickets)
def my_tickets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(SupportTicket).filter(SupportTicket.user_id == current_user.id)
    if status_filter:
        query = query.filter(SupportTicket.status == status_filter)
    return _paginate(query, page, page_size, lambda t: _ticket_response(t, include_internal=False))


@router.get("/tickets/{ticket_id}", response_model=SupportTicketResponse)
def get_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if ticket is None or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _ticket_response(ticket, include_internal=False)


@router.post("/tickets/{ticket_id}/messages", response_model=SupportTicketMessageResponse, status_code=status.HTTP_201_CREATED)
def reply_ticket(
    ticket_id: UUID,
    data: SupportTicketMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if ticket is None or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    message = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message=data.message,
        visibility="all",
    )
    db.add(message)
    # A customer reply re-opens a resolved/closed conversation.
    if ticket.status in {"resolved", "closed"}:
        ticket.status = "open"
        ticket.resolved_at = None
        ticket.closed_at = None
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(message)
    return _message_response(message, ticket)


# -------------------------------------------------------------------- Admin


def _admin_query(db: Session, params: dict):
    query = (
        db.query(SupportTicket)
        .outerjoin(User, SupportTicket.user_id == User.id)
        .outerjoin(Seller, SupportTicket.seller_id == Seller.id)
    )
    search = (params.get("search") or "").strip()
    if search:
        term = f"%{search}%"
        query = query.filter(or_(
            SupportTicket.ticket_number.ilike(term),
            SupportTicket.subject.ilike(term),
            SupportTicket.description.ilike(term),
            User.email.ilike(term),
            func.concat(func.coalesce(User.first_name, ""), " ", func.coalesce(User.last_name, "")).ilike(term),
            Seller.business_name.ilike(term),
        ))
    for key in ("status", "priority", "channel", "category"):
        value = params.get(key)
        if value:
            query = query.filter(getattr(SupportTicket, key) == value)

    participant_role = params.get("participant_role")
    if participant_role == "seller":
        query = query.filter(SupportTicket.seller_id.isnot(None))
    elif participant_role == "logistics":
        query = query.filter(SupportTicket.shipment_id.isnot(None))
    elif participant_role == "customer":
        query = query.filter(SupportTicket.channel == "customer")

    if params.get("date_from"):
        query = query.filter(SupportTicket.created_at >= params["date_from"])
    if params.get("date_to"):
        query = query.filter(SupportTicket.created_at <= params["date_to"])
    return query


@admin_router.get("", response_model=PaginatedSupportTickets)
def admin_list_tickets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    channel: str | None = None,
    category: str | None = None,
    participant_role: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.support_tickets_read.value)),
):
    query = _admin_query(db, {
        "search": search, "status": status_filter, "priority": priority,
        "channel": channel, "category": category,
        "participant_role": participant_role,
        "date_from": date_from, "date_to": date_to,
    })
    return _paginate(query, page, page_size, lambda t: _ticket_response(t, include_internal=True))


@admin_router.get("/{ticket_id}", response_model=SupportTicketResponse)
def admin_get_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.support_tickets_read.value)),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _ticket_response(ticket, include_internal=True)


@admin_router.patch("/{ticket_id}", response_model=SupportTicketResponse)
def admin_update_ticket(
    ticket_id: UUID,
    data: SupportTicketUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.support_tickets_manage.value)),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    changes = data.model_dump(exclude_unset=True)
    now = datetime.now(timezone.utc)

    if "status" in changes:
        new_status = changes["status"]
        if new_status not in _VALID_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid status")
        ticket.status = new_status
        if new_status == "resolved" and ticket.resolved_at is None:
            ticket.resolved_at = now
        if new_status == "closed":
            ticket.closed_at = now
            if ticket.resolved_at is None:
                ticket.resolved_at = now
        if new_status in {"open", "pending", "in_progress"}:
            ticket.closed_at = None

    if "priority" in changes:
        if changes["priority"] not in _VALID_PRIORITIES:
            raise HTTPException(status_code=422, detail="Invalid priority")
        ticket.priority = changes["priority"]

    if "assigned_to_id" in changes:
        ticket.assigned_to_id = changes["assigned_to_id"]
        if ticket.assigned_to_id and ticket.status == "open":
            ticket.status = "in_progress"

    if "resolution_note" in changes:
        ticket.resolution_note = changes["resolution_note"]

    ticket.updated_at = now
    db.commit()
    db.refresh(ticket)
    return _ticket_response(ticket, include_internal=True)


@admin_router.post("/{ticket_id}/messages", response_model=SupportTicketMessageResponse, status_code=status.HTTP_201_CREATED)
def admin_reply_ticket(
    ticket_id: UUID,
    data: SupportTicketMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.support_tickets_manage.value)),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if data.visibility not in _VALID_VISIBILITY:
        raise HTTPException(status_code=422, detail="Invalid visibility")

    message = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message=data.message,
        visibility=data.visibility,
    )
    db.add(message)
    if ticket.status == "open":
        ticket.status = "in_progress"
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(message)
    return _message_response(message, ticket)
