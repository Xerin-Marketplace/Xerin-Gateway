from __future__ import annotations

from io import BytesIO
from decimal import Decimal
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _money(value, currency: str) -> str:
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    if currency.upper() == "TZS":
        return f"TZS {amount:,.2f}"
    return f"{currency.upper()} {amount:,.2f}"


def _text(value) -> str:
    return str(value or "-").strip() or "-"


def build_order_invoice_pdf(order, *, logistics_company=None) -> bytes:
    """Build a customer invoice PDF from immutable order snapshots."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Xerin Invoice {order.id}",
        author="Xerin Marketplace",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallMuted", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#64748B")))
    styles.add(ParagraphStyle(name="Right", parent=styles["Normal"], alignment=TA_RIGHT, fontSize=9.5, leading=12))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading3"], fontSize=10.5, leading=13, textColor=colors.HexColor("#111827"), spaceAfter=5))

    created = order.created_at
    invoice_number = f"INV-{created:%Y%m%d}-{str(order.id)[:8].upper()}"
    currency = (order.currency or "TZS").upper()

    payment_status = "UNPAID"
    payments = sorted(list(getattr(order, "payments", []) or []), key=lambda p: getattr(p, "created_at", None) or created, reverse=True)
    if any(getattr(getattr(p, "status", None), "value", getattr(p, "status", None)) == "completed" for p in payments):
        payment_status = "PAID"

    story = []
    header = Table(
        [
            [
                Paragraph('<font size="20"><b>XERIN</b></font><br/><font size="8">MARKETPLACE</font>', styles["Normal"]),
                Paragraph(f'<font size="18"><b>INVOICE</b></font><br/><font size="9">{invoice_number}</font>', styles["Right"]),
            ]
        ],
        colWidths=[105 * mm, 57 * mm],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [header, Spacer(1, 8 * mm)]

    user = getattr(order, "user", None)
    address = getattr(order, "shipping_address", None)
    customer_name = " ".join(filter(None, [getattr(user, "first_name", None), getattr(user, "last_name", None)])) or getattr(address, "recipient_name", None) or "Customer"

    address_lines = []
    if address:
        for value in [getattr(address, "street", None), getattr(address, "ward", None), getattr(address, "city", None), getattr(address, "region", None), getattr(address, "country", None)]:
            if value and str(value).strip() and str(value).strip() not in address_lines:
                address_lines.append(str(value).strip())

    info = Table(
        [
            [Paragraph("<b>BILL TO</b>", styles["Section"]), Paragraph("<b>INVOICE DETAILS</b>", styles["Section"])],
            [
                Paragraph(
                    f"<b>{_text(customer_name)}</b><br/>{'<br/>'.join(address_lines) if address_lines else '-'}<br/>{_text(getattr(user, 'email', None))}<br/>{_text(getattr(address, 'recipient_phone', None) or getattr(user, 'phone', None))}",
                    styles["Normal"],
                ),
                Paragraph(
                    f"Order: {order.id}<br/>Date: {created:%d %b %Y, %H:%M}<br/>Order status: {_text(getattr(getattr(order, 'status', None), 'value', getattr(order, 'status', None))).title()}<br/>Payment: {payment_status}<br/>Currency: {currency}",
                    styles["Normal"],
                ),
            ],
        ],
        colWidths=[92 * mm, 70 * mm],
    )
    info.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [info, Spacer(1, 7 * mm)]

    item_rows = [["Item", "Store", "Qty", "Unit price", "Amount"]]
    for item in list(getattr(order, "items", []) or []):
        product = _text(getattr(item, "product_name", None))
        variant = getattr(item, "variant_name", None)
        if variant:
            product += f" - {variant}"
        store = getattr(item, "store", None)
        amount = getattr(item, "customer_total", None)
        if amount is None:
            amount = getattr(item, "total_price", 0)
        item_rows.append([
            Paragraph(product, styles["Normal"]),
            Paragraph(_text(getattr(store, "store_name", None)), styles["SmallMuted"]),
            str(getattr(item, "quantity", 0)),
            _money(getattr(item, "unit_price", 0), currency),
            _money(amount, currency),
        ])

    items_table = Table(item_rows, colWidths=[55 * mm, 40 * mm, 12 * mm, 27 * mm, 28 * mm], repeatRows=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E5E7EB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [items_table, Spacer(1, 6 * mm)]

    totals = [
        ["Product subtotal", _money(order.subtotal, currency)],
    ]
    promotion = Decimal(str(getattr(order, "promotion_discount_amount", 0) or 0))
    coupon = Decimal(str(getattr(order, "coupon_discount_amount", 0) or 0))
    shipping_discount = Decimal(str(getattr(order, "shipping_discount_amount", 0) or 0))
    if promotion > 0:
        totals.append(["Seller promotion", f"- {_money(promotion, currency)}"])
    if coupon > 0:
        totals.append(["Coupon discount", f"- {_money(coupon, currency)}"])
    if shipping_discount > 0:
        totals.append(["Shipping discount", f"- {_money(shipping_discount, currency)}"])
    totals += [
        ["Delivery", _money(getattr(order, "shipping_amount", 0), currency)],
        ["Tax", _money(getattr(order, "tax_amount", 0), currency)],
        ["GRAND TOTAL", _money(order.total, currency)],
    ]
    totals_table = Table(totals, colWidths=[105 * mm, 57 * mm], hAlign="RIGHT")
    totals_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#111827")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [totals_table, Spacer(1, 7 * mm)]

    delivery_parts = []
    if getattr(order, "delivery_mode", None):
        delivery_parts.append(f"Route: {str(order.delivery_mode).replace('_', ' ').title()}")
    if getattr(order, "shipping_method_name", None):
        delivery_parts.append(f"Service: {order.shipping_method_name}")
    if logistics_company:
        delivery_parts.append(f"Logistics: {logistics_company.name}")
    if delivery_parts:
        story += [Paragraph("<b>Delivery</b><br/>" + "<br/>".join(delivery_parts), styles["Normal"]), Spacer(1, 5 * mm)]

    story += [
        Paragraph(
            "This invoice is generated electronically by Xerin Marketplace from the order snapshot recorded at checkout. A payment receipt is issued separately only after payment is confirmed.",
            styles["SmallMuted"],
        )
    ]

    doc.build(story)
    return buffer.getvalue()
