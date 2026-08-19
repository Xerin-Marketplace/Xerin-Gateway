from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from api.enums import RefundStatus, MarketplaceTransactionType, InventoryMovementType
from api.models import Refund, RefundItem, RefundEvent, Order, OrderItem, OrderItemCommission, MarketplaceTransaction, Inventory, InventoryMovement
from api.services.wallet_service import debit_refund
from api.services.escrow_service import record_escrow_refund
MONEY=Decimal("0.01")
def money(v): return Decimal(v).quantize(MONEY,rounding=ROUND_HALF_UP)

def create_refund_request(db:Session,*,order:Order,user_id,data):
    existing=db.query(Refund).filter(Refund.idempotency_key==data.idempotency_key).first()
    if existing:return existing
    requested={x.order_item_id:x for x in data.items}
    if len(requested)!=len(data.items): raise ValueError("Duplicate order items are not allowed")
    order_items={x.id:x for x in order.items}
    active_statuses=[RefundStatus.requested,RefundStatus.under_review,RefundStatus.approved,RefundStatus.processing,RefundStatus.completed]
    previous=db.query(Refund).filter(Refund.order_id==order.id,Refund.status.in_(active_statuses)).all()
    shipping_already=money(sum((Decimal(x.shipping_amount) for x in previous),Decimal("0")))
    tax_already=money(sum((Decimal(x.tax_amount) for x in previous),Decimal("0")))
    shipping_available=max(Decimal("0"),money(order.shipping_amount)-shipping_already)
    tax_available=max(Decimal("0"),money(order.tax_amount)-tax_already)
    refund=Refund(order_id=order.id,requested_by_id=user_id,status=RefundStatus.requested,reason=data.reason,reason_details=data.reason_details,currency=order.currency,idempotency_key=data.idempotency_key,items_amount=0,shipping_amount=shipping_available if data.refund_shipping else 0,tax_amount=tax_available if data.refund_tax else 0,total_amount=0)
    db.add(refund);db.flush();items_total=Decimal("0")
    for item_id,req in requested.items():
        item=order_items.get(item_id)
        if not item: raise ValueError("Order item does not belong to this order")
        prior_items=db.query(RefundItem).join(Refund).filter(RefundItem.order_item_id==item.id,Refund.status.in_(active_statuses)).with_entities(RefundItem.quantity,RefundItem.refund_amount).all()
        remaining=item.quantity-sum(x[0] for x in prior_items)
        if req.quantity>remaining: raise ValueError(f"Refund quantity exceeds refundable quantity for {item.product_name}")
        # Refund the amount actually charged for the line, not its pre-promotion price.
        charged_total=money(item.customer_total if item.customer_total is not None else item.total_price)
        unit_charged=money(charged_total/Decimal(item.quantity))
        prior_amount=money(sum((Decimal(x[1]) for x in prior_items),Decimal("0")))
        refundable_amount=max(Decimal("0"),charged_total-prior_amount)
        amount=refundable_amount if req.quantity==remaining else min(refundable_amount,money(unit_charged*req.quantity))
        items_total+=amount
        db.add(RefundItem(refund_id=refund.id,order_item_id=item.id,seller_id=item.seller_id,quantity=req.quantity,unit_amount=unit_charged,refund_amount=amount,restock=req.restock))
    refund.items_amount=money(items_total);refund.total_amount=money(items_total+Decimal(refund.shipping_amount)+Decimal(refund.tax_amount))
    db.add(RefundEvent(refund_id=refund.id,status=RefundStatus.requested,note="Refund requested",created_by_id=user_id));db.flush();return refund

def transition_refund(db:Session,refund:Refund,status:RefundStatus,*,user_id=None,note=None,provider_reference=None):
    allowed={RefundStatus.requested:{RefundStatus.under_review,RefundStatus.approved,RefundStatus.rejected,RefundStatus.cancelled},RefundStatus.under_review:{RefundStatus.approved,RefundStatus.rejected,RefundStatus.cancelled},RefundStatus.approved:{RefundStatus.processing,RefundStatus.cancelled},RefundStatus.processing:{RefundStatus.completed,RefundStatus.failed},RefundStatus.failed:{RefundStatus.processing}}
    if status not in allowed.get(refund.status,set()): raise ValueError(f"Invalid refund transition: {refund.status.value} -> {status.value}")
    now=datetime.now(timezone.utc);refund.status=status;refund.admin_note=note or refund.admin_note
    if status in {RefundStatus.under_review,RefundStatus.approved,RefundStatus.rejected}: refund.reviewed_at=now
    if status==RefundStatus.processing: refund.processed_at=now
    if provider_reference: refund.provider_reference=provider_reference
    if status==RefundStatus.completed:
        complete_refund(db,refund,user_id=user_id);refund.completed_at=now
    db.add(RefundEvent(refund_id=refund.id,status=status,note=note,created_by_id=user_id));return refund

def complete_refund(db:Session,refund:Refund,*,user_id=None):
    for ri in refund.items:
        if ri.processed_at: continue
        item=db.query(OrderItem).filter(OrderItem.id==ri.order_item_id).with_for_update().one()
        commission=db.query(OrderItemCommission).filter(OrderItemCommission.order_item_id==item.id).first()
        ratio=Decimal(ri.quantity)/Decimal(item.quantity)
        commission_reversal=min(money(ri.refund_amount),money(Decimal(commission.commission_amount)*ratio)) if commission else Decimal("0")
        seller_reversal=money(max(Decimal("0"),Decimal(ri.refund_amount)-commission_reversal))
        record_escrow_refund(db,order_item_id=item.id,amount=ri.refund_amount,refund_id=refund.id,refund_item_id=ri.id,created_by_id=user_id)
        _,debt=debit_refund(db,seller_id=item.seller_id,amount=seller_reversal,currency=refund.currency,refund_id=refund.id,refund_item_id=ri.id,order_id=refund.order_id,order_item_id=item.id)
        ri.commission_reversal=commission_reversal;ri.seller_reversal=seller_reversal;ri.seller_debt_amount=debt;ri.processed_at=datetime.now(timezone.utc)
        refs=[(MarketplaceTransactionType.refund,money(ri.refund_amount),f"refund:{ri.id}"),(MarketplaceTransactionType.commission_reversal,commission_reversal,f"commission_reversal:{ri.id}")]
        for typ,amount,ref in refs:
            if amount and not db.query(MarketplaceTransaction).filter(MarketplaceTransaction.reference==ref).first():
                db.add(MarketplaceTransaction(order_id=refund.order_id,order_item_id=item.id,seller_id=item.seller_id,commission_record_id=commission.id if commission else None,transaction_type=typ,currency=refund.currency,amount=amount,reference=ref,description=f"{typ.value} for refund item {ri.id}"))
        if ri.restock:
            inv=db.query(Inventory).filter(Inventory.product_id==item.product_id,Inventory.variant_id==item.variant_id).with_for_update().first()
            if inv and not db.query(InventoryMovement).filter(InventoryMovement.refund_item_id==ri.id).first():
                before=inv.quantity;inv.quantity+=ri.quantity;inv.available_quantity=inv.quantity-inv.reserved_quantity
                db.add(InventoryMovement(inventory_id=inv.id,order_item_id=item.id,refund_item_id=ri.id,movement_type=InventoryMovementType.refund_restock,quantity=ri.quantity,before_quantity=before,after_quantity=inv.quantity,note=f"Restocked from refund {refund.id}",created_by_id=user_id))
    return refund
