"""Invoice / receipt PDF generation for orders (reportlab)."""
from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from api.models import Order, Payment


ORANGE = colors.HexColor("#F56A02")
INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#6b7280")
LINE = colors.HexColor("#e5e7eb")


def _money(amount, currency="TZS") -> str:
    try:
        return f"{float(amount):,.0f} {currency}"
    except (TypeError, ValueError):
        return f"{amount} {currency}"


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=22, textColor=INK, fontName="Helvetica-Bold"),
        "muted": ParagraphStyle("muted", parent=base["Normal"], fontSize=9, textColor=MUTED),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=10, textColor=INK, leading=14),
        "h": ParagraphStyle("h", parent=base["Heading2"], fontSize=12, textColor=INK, fontName="Helvetica-Bold", spaceBefore=14),
        "right": ParagraphStyle("right", parent=base["Normal"], fontSize=10, alignment=2),
    }


def _header(story, s, doc_title: str, order: Order):
    story.append(
        Table(
            [[Paragraph(f'<font color="#F56A02"><b>XERIN MART</b></font>', s["title"]),
              Paragraph(f'<font size="18"><b>{doc_title}</b></font>', s["right"])]],
            colWidths=[None, None],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]),
        )
    )
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            f'Order <b>{order.order_number or str(order.id)[:8].upper()}</b> · '
            f'{order.created_at.strftime("%d %b %Y, %H:%M") if order.created_at else ""}',
            s["muted"],
        )
    )
    story.append(Spacer(1, 10))
    story.append(Table([[""]], colWidths=[180 * mm], style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, ORANGE)])))
    story.append(Spacer(1, 10))


def _address_block(story, s, order: Order):
    addr = order.shipping_address
    if not addr:
        return
    lines = ", ".join(filter(None, [addr.street, addr.ward, addr.district or addr.city, addr.region, addr.country]))
    story.append(Paragraph("Deliver to", s["h"]))
    name = addr.recipient_name or ""
    phone = addr.recipient_phone or ""
    story.append(Paragraph(f"<b>{name}</b>{' · ' + phone if phone else ''}<br/>{lines}" + (f"<br/>Landmark: {addr.landmark}" if addr.landmark else ""), s["body"]))


def _items_table(story, s, order: Order):
    story.append(Paragraph("Items", s["h"]))
    data = [["Product", "Qty", "Unit price", "Total"]]
    for item in order.items:
        data.append([
            Paragraph(item.product_name + (f" · {item.variant_name}" if getattr(item, "variant_name", None) else ""), s["body"]),
            str(item.quantity),
            _money(item.unit_price, order.currency),
            _money(item.total_price, order.currency),
        ])
    table = Table(data, colWidths=[90 * mm, 15 * mm, 37 * mm, 38 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(table)


def _totals(story, s, order: Order):
    rows = [["Subtotal", _money(order.subtotal, order.currency)]]
    if float(order.discount_amount or 0) > 0:
        rows.append(["Discount", f"-{_money(order.discount_amount, order.currency)}"])
    rows.append(["Delivery", _money(order.shipping_amount, order.currency)])
    if float(order.tax_amount or 0) > 0:
        rows.append(["Tax", _money(order.tax_amount, order.currency)])
    rows.append(["Total", _money(order.total, order.currency)])
    table = Table(rows, colWidths=[140 * mm, 40 * mm])
    table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("TEXTCOLOR", (0, -1), (-1, -1), ORANGE),
        ("LINEABOVE", (0, -1), (-1, -1), 1, ORANGE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(Spacer(1, 8))
    story.append(table)


def build_invoice_pdf(order: Order) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title="Xerin Invoice")
    s = _styles()
    story = []
    _header(story, s, "INVOICE", order)
    _address_block(story, s, order)
    _items_table(story, s, order)
    _totals(story, s, order)
    story.append(Spacer(1, 20))
    story.append(Paragraph("Thank you for shopping with Xerin Mart.", s["muted"]))
    doc.build(story)
    return buf.getvalue()


def build_receipt_pdf(order: Order, payment: Payment) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title="Xerin Payment Receipt")
    s = _styles()
    story = []
    _header(story, s, "PAYMENT RECEIPT", order)
    rows = [
        ["Payment status", (payment.status.value if payment.status else "").upper()],
        ["Amount paid", _money(payment.amount, payment.currency)],
        ["Method", (payment.method.value if payment.method else "").replace("_", " ").title()],
        ["Provider", payment.provider or "—"],
        ["Reference", payment.provider_transaction_id or "—"],
        ["Paid at", payment.paid_at.strftime("%d %b %Y, %H:%M") if payment.paid_at else "—"],
    ]
    table = Table(rows, colWidths=[60 * mm, 120 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(table)
    _items_table(story, s, order)
    _totals(story, s, order)
    story.append(Spacer(1, 20))
    story.append(Paragraph("This receipt was generated by Xerin Mart for a verified payment.", s["muted"]))
    doc.build(story)
    return buf.getvalue()
