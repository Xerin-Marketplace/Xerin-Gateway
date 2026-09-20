from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.enums import CommissionRuleType, CommissionScope, MarketplaceTransactionType
from api.models import CommissionRule, MarketplaceTransaction, Order, OrderItemCommission, Product
from api.services.wallet_service import credit_sale

MONEY = Decimal("0.01")

def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)

def _active_rules(db: Session, now: datetime):
    return db.query(CommissionRule).filter(
        CommissionRule.is_active.is_(True),
        or_(CommissionRule.starts_at.is_(None), CommissionRule.starts_at <= now),
        or_(CommissionRule.ends_at.is_(None), CommissionRule.ends_at > now),
    )

def resolve_commission_rule_for_targets(
    db: Session,
    *,
    seller_id=None,
    category_id=None,
    product_id=None,
    now: datetime | None = None,
):
    """Resolve the effective commission using fixed marketplace precedence.

    Precedence is product > seller > category > global. Priority is only used
    to resolve multiple active rules within the same scope.
    """
    now = now or datetime.now(timezone.utc)
    candidates = []
    if product_id is not None:
        candidates.append((CommissionScope.product, CommissionRule.product_id == product_id))
    if seller_id is not None:
        candidates.append((CommissionScope.seller, CommissionRule.seller_id == seller_id))
    if category_id is not None:
        candidates.append((CommissionScope.category, CommissionRule.category_id == category_id))
    candidates.append((CommissionScope.global_rule, CommissionRule.scope == CommissionScope.global_rule))

    for scope, target_filter in candidates:
        rule = (
            _active_rules(db, now)
            .filter(CommissionRule.scope == scope, target_filter)
            .order_by(CommissionRule.priority.desc(), CommissionRule.created_at.desc())
            .first()
        )
        if rule:
            return rule
    return None


def resolve_commission_rule(db: Session, item, now: datetime | None = None):
    product = db.query(Product).filter(Product.id == item.product_id).first()
    return resolve_commission_rule_for_targets(
        db,
        seller_id=item.seller_id,
        category_id=product.category_id if product else None,
        product_id=item.product_id,
        now=now,
    )

def calculate_order_commissions(
    db: Session,
    order: Order,
    *,
    settlement_eligible_at=None,
) -> list[OrderItemCommission]:
    records = []

    for item in order.items:
        existing = (
            db.query(OrderItemCommission)
            .filter(OrderItemCommission.order_item_id == item.id)
            .first()
        )
        if existing:
            records.append(existing)
            continue

        gross = _money(Decimal(item.total_price))
        seller_funded_discount = _money(
            Decimal(getattr(item, "promotion_discount_amount", 0) or 0)
        )

        rule = resolve_commission_rule(db, item)
        rate = Decimal(rule.rate) if rule else Decimal("0")

        if rule and rule.rule_type == CommissionRuleType.fixed:
            commission = min(gross, _money(rate))
            snapshot_rate = rate
        else:
            commission = _money(gross * rate / Decimal("100"))
            snapshot_rate = rate

        # Xerin commission remains based on the original marketplace line.
        # Seller-funded promotions and Broker rewards reduce the seller's own
        # settlement amount. The Broker amount is an immutable B4 snapshot on
        # the order item and must never be recalculated from the live offer.
        broker_reward = _money(
            Decimal(getattr(item, "broker_commission_amount", 0) or 0)
        )
        seller_net = _money(
            max(
                Decimal("0.00"),
                gross - commission - seller_funded_discount - broker_reward,
            )
        )

        record = OrderItemCommission(
            order_id=order.id,
            order_item_id=item.id,
            seller_id=item.seller_id,
            commission_rule_id=rule.id if rule else None,
            currency=order.currency,
            gross_amount=gross,
            commission_rate=snapshot_rate,
            commission_amount=commission,
            seller_net_amount=seller_net,
            processing_fee=Decimal("0"),
            tax_amount=Decimal("0"),
        )
        db.add(record)
        db.flush()

        txs = [
            (
                MarketplaceTransactionType.sale,
                gross,
                f"sale:{item.id}",
            ),
            (
                MarketplaceTransactionType.commission,
                commission,
                f"commission:{item.id}",
            ),
            (
                MarketplaceTransactionType.seller_earning,
                seller_net,
                f"seller_earning:{item.id}",
            ),
        ]

        for typ, amount, ref in txs:
            db.add(
                MarketplaceTransaction(
                    order_id=order.id,
                    order_item_id=item.id,
                    seller_id=item.seller_id,
                    commission_record_id=record.id,
                    transaction_type=typ,
                    currency=order.currency,
                    amount=amount,
                    reference=ref,
                    description=(
                        f"{typ.value.replace('_',' ').title()} "
                        f"for order item {item.id}"
                    ),
                )
            )

        credit_sale(
            db,
            seller_id=item.seller_id,
            amount=seller_net,
            currency=order.currency,
            order_id=order.id,
            order_item_id=item.id,
            eligible_at=settlement_eligible_at,
        )
        records.append(record)

    return records
