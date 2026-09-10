from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _money(value, currency: str) -> str:
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    return f"{(currency or 'TZS').upper()} {amount:,.2f}"


def _value(value) -> str:
    if value is None:
        return "-"
    raw = getattr(value, "value", value)
    return str(raw).strip() or "-"


def build_payment_receipt_pdf(order, payment) -> bytes:
    """Build proof-of-payment PDF from a verified completed Payment row."""
    status = _value(getattr(payment, "status", None)).lower()
    if status != "completed":
        raise ValueError("A receipt can only be generated for a completed payment")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title=f"Xerin Payment Receipt {payment.id}",
        author="Xerin Marketplace",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReceiptMuted",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#64748B"),
    ))
    styles.add(ParagraphStyle(
        name="ReceiptRight",
        parent=styles["Normal"],
        alignment=TA_RIGHT,
        fontSize=9.5,
        leading=12,
    ))
    styles.add(ParagraphStyle(
        name="ReceiptCenter",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        leading=13,
    ))

    paid_at = payment.paid_at or payment.updated_at or payment.created_at
    receipt_number = f"RCT-{paid_at:%Y%m%d}-{str(payment.id)[:8].upper()}"
    currency = (payment.currency or order.currency or "TZS").upper()
    transaction_reference = (
        payment.provider_transaction_id
        or str(payment.id)
    )

    user = getattr(order, "user", None)
    address = getattr(order, "shipping_address", None)
    customer_name = " ".join(
        filter(None, [
            getattr(user, "first_name", None),
            getattr(user, "last_name", None),
        ])
    ) or getattr(address, "recipient_name", None) or "Customer"

    story = []
    header = Table(
        [[
            Paragraph(
                '<font size="20"><b>XERIN</b></font><br/><font size="8">MARKETPLACE</font>',
                styles["Normal"],
            ),
            Paragraph(
                f'<font size="18"><b>PAYMENT RECEIPT</b></font><br/><font size="9">{receipt_number}</font>',
                styles["ReceiptRight"],
            ),
        ]],
        colWidths=[98 * mm, 64 * mm],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [header, Spacer(1, 8 * mm)]

    paid_banner = Table(
        [[Paragraph(
            "<b>PAYMENT SUCCESSFUL</b><br/><font size='9'>This payment was verified by Xerin before this receipt was issued.</font>",
            styles["ReceiptCenter"],
        )]],
        colWidths=[162 * mm],
    )
    paid_banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ECFDF5")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#047857")),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#A7F3D0")),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story += [paid_banner, Spacer(1, 7 * mm)]

    details = [
        ["Customer", customer_name],
        ["Order number", str(order.id)],
        ["Receipt number", receipt_number],
        ["Payment reference", str(payment.id)],
        ["Provider transaction reference", transaction_reference],
        ["Payment method", _value(payment.method).replace("_", " ").title()],
        ["Payment provider", _value(payment.provider).title()],
        ["Payment date", paid_at.strftime("%d %b %Y, %H:%M:%S %Z")],
        ["Payment status", "PAID"],
        ["Amount paid", _money(payment.amount, currency)],
    ]
    table = Table(details, colWidths=[58 * mm, 104 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5E7EB")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [table, Spacer(1, 8 * mm)]

    totals = Table(
        [
            ["Order total", _money(order.total, order.currency)],
            ["Amount received", _money(payment.amount, currency)],
        ],
        colWidths=[100 * mm, 62 * mm],
        hAlign="RIGHT",
    )
    totals.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.HexColor("#111827")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [totals, Spacer(1, 8 * mm)]

    story += [
        Paragraph(
            "This receipt is proof that Xerin Marketplace recorded a verified successful payment for the order above. "
            "It is different from the invoice, which records what was charged.",
            styles["ReceiptMuted"],
        ),
        Spacer(1, 3 * mm),
        Paragraph(
            "If a refund is later processed, the payment and order history in Xerin remains the authoritative current record.",
            styles["ReceiptMuted"],
        ),
    ]

    doc.build(story)
    return buffer.getvalue()
