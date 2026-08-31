from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from api.models import (EscrowEvent, EscrowHold, MarketplaceSettings, Order, OrderItem, OrderItemDispute, Shipment, ShipmentDeliveryProof, ShipmentHandover, ShipmentItem, ShipmentPickupProof)
from api.services.escrow_service import release_escrow_hold_funds

ACTIVE={"submitted","under_review","evidence_required"}
SELLER_HOLD_REASONS={"wrong_product","not_as_described","defective_on_arrival","damaged_on_arrival","missing_item","other"}
RESP={"wrong_product":"seller","not_as_described":"seller","defective_on_arrival":"seller","damaged_on_arrival":"undetermined","missing_item":"undetermined","other":"undetermined","package_tampered":"logistics","late_delivery":"logistics","customer_accidental_damage":"customer","change_of_mind":"customer"}

def _settings(db): return db.query(MarketplaceSettings).filter(MarketplaceSettings.singleton_key==1).first()
def seller_grace_hours(db):
    row=_settings(db); return int(getattr(row,"seller_release_grace_hours",None) or 144)
def dispute_hours(db):
    row=_settings(db); return min(int(getattr(row,"dispute_period_hours",None) or seller_grace_hours(db)),seller_grace_hours(db))

def schedule_shipment_seller_release_after_delivery(db:Session,*,shipment:Shipment,delivery_proof:ShipmentDeliveryProof):
    if delivery_proof.status!="verified" or not delivery_proof.verified_at: raise ValueError("Verified delivery proof is required")
    handover=db.query(ShipmentHandover).filter(ShipmentHandover.shipment_id==shipment.id,ShipmentHandover.status=="seller_confirmed").first()
    pickup=db.query(ShipmentPickupProof).filter(ShipmentPickupProof.shipment_id==shipment.id).first()
    if not handover or not pickup: raise ValueError("Seller handover and pickup evidence are required before the Seller protection clock can start")
    ids=[r[0] for r in db.query(ShipmentItem.order_item_id).filter(ShipmentItem.shipment_id==shipment.id).all()]
    deadline=delivery_proof.verified_at+timedelta(hours=seller_grace_hours(db))
    holds=db.query(EscrowHold).filter(EscrowHold.order_id==shipment.order_id,EscrowHold.order_item_id.in_(ids)).with_for_update().all() if ids else []
    for h in holds:
        if h.status in {"released","refunded"}: continue
        h.seller_release_shipment_id=shipment.id; h.seller_release_handover_id=handover.id; h.seller_release_proof_id=pickup.id; h.seller_release_delivery_proof_id=delivery_proof.id; h.delivery_verified_at=delivery_proof.verified_at; h.release_after=deadline; h.seller_release_trigger="verified_delivery"; h.seller_release_verified_at=delivery_proof.verified_at
        db.add(EscrowEvent(escrow_hold_id=h.id,event_type="delivery_protection_started",note=f"Verified delivery; Seller release scheduled for {deadline.isoformat()}"))
    db.flush(); return holds

def accept_order_item(db:Session,*,order:Order,item_id,customer_id,note=None):
    item=db.query(OrderItem).filter(OrderItem.id==item_id,OrderItem.order_id==order.id).first()
    if not item: raise ValueError("Order item not found")
    hold=db.query(EscrowHold).filter(EscrowHold.order_id==order.id,EscrowHold.order_item_id==item.id).with_for_update().first()
    if not hold: raise ValueError("No Seller escrow exists for this item")
    if hold.status=="released": return hold
    if not hold.delivery_verified_at: raise ValueError("Item can be accepted only after verified delivery")
    active=db.query(OrderItemDispute.id).filter(OrderItemDispute.escrow_hold_id==hold.id,OrderItemDispute.escrow_impact.is_(True),OrderItemDispute.resolution_status.in_(ACTIVE)).first()
    if active: raise ValueError("This item has an active protection dispute")
    hold.customer_accepted_at=datetime.now(timezone.utc); hold.customer_accepted_by_id=customer_id
    return release_escrow_hold_funds(db,hold=hold,note=note or "Customer accepted this item",created_by_id=customer_id,event_type="customer_item_accepted")

def create_customer_disputes(db:Session,*,order:Order,customer_id,scope,order_item_id,reason,notes,evidence_urls):
    if order.user_id!=customer_id: raise ValueError("Not authorized")
    items=db.query(OrderItem).filter(OrderItem.order_id==order.id).all()
    if scope=="item": items=[i for i in items if i.id==order_item_id]
    if not items: raise ValueError("No affected order item was found")
    case=f"DSP-{uuid.uuid4().hex[:10].upper()}"; rows=[]; now=datetime.now(timezone.utc)
    for item in items:
        hold=db.query(EscrowHold).filter(EscrowHold.order_item_id==item.id).with_for_update().first()
        if not hold or not hold.delivery_verified_at: raise ValueError("A marketplace-protection claim can be opened only after verified delivery")
        if hold.status=="released" or hold.customer_accepted_at:
            if scope == "order":
                continue
            raise ValueError(f"{item.product_name} has already been accepted/settled; use the return or warranty flow")
        deadline=hold.delivery_verified_at+timedelta(hours=dispute_hours(db))
        if now>deadline: raise ValueError("The marketplace-protection claim window has ended; use the return or warranty flow")
        if db.query(OrderItemDispute.id).filter(OrderItemDispute.order_item_id==item.id,OrderItemDispute.resolution_status.in_(ACTIVE)).first(): raise ValueError(f"{item.product_name} already has an active protection case")
        impact=reason in SELLER_HOLD_REASONS
        row=OrderItemDispute(case_reference=case,order_id=order.id,order_item_id=item.id,customer_id=customer_id,seller_id=item.seller_id,shipment_id=hold.seller_release_shipment_id,scope=scope,reason=reason,notes=notes,evidence_urls=evidence_urls or [],quantity=item.quantity,escrow_hold_id=hold.id,amount_held=Decimal(hold.seller_amount or 0) if impact else Decimal("0"),escrow_impact=impact,responsibility_status=RESP.get(reason,"undetermined"),resolution_status="submitted" if impact else "recorded_no_escrow_hold")
        db.add(row)
        if impact:
            hold.status="disputed"; hold.disputed_at=now; db.add(EscrowEvent(escrow_hold_id=hold.id,event_type="customer_item_disputed",note=f"Protection case {case}: {reason}. Only this item entitlement is blocked.",created_by_id=customer_id))
        rows.append(row)
    if not rows:
        raise ValueError("All items in this order are already accepted/settled; use the return or warranty flow")
    db.flush(); return rows

def resolve_customer_dispute(db:Session,*,row:OrderItemDispute,user_id,responsibility_status,resolution_status,resolution_note,release_seller=False):
    row=db.query(OrderItemDispute).filter(OrderItemDispute.id==row.id).with_for_update().one(); row.responsibility_status=responsibility_status; row.resolution_status=resolution_status; row.resolution_note=resolution_note or "Protection case reviewed by Admin"; row.resolved_by_id=user_id
    if resolution_status in {"resolved","rejected"}: row.resolved_at=datetime.now(timezone.utc)
    hold=db.query(EscrowHold).filter(EscrowHold.id==row.escrow_hold_id).with_for_update().first() if row.escrow_hold_id else None
    should_release=release_seller or resolution_status=="rejected" or (resolution_status=="resolved" and responsibility_status in {"customer","logistics","platform"})
    if should_release and hold and hold.status!="released":
        hold.status="held"
        release_escrow_hold_funds(db,hold=hold,note=f"Protection case {row.case_reference} resolved; Seller entitlement released",created_by_id=user_id,event_type="dispute_resolved_seller_release")
    db.flush(); return row
