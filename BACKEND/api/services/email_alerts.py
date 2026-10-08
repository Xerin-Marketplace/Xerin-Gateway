from __future__ import annotations

import html as _html
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.config import settings
from api.models import AlertNotification, WeeklyReport
from api.routers.email import send_email

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


_SEV_COLORS = {
    "info": "#2563eb",
    "notice": "#d97706",
    "warning": "#ea580c",
    "critical": "#dc2626",
}


def _shell(*, title: str, subtitle: str, body: str) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <div style="max-width:560px;margin:24px auto;padding:0 16px;">
    <div style="background:#111827;border-radius:14px 14px 0 0;padding:20px 24px;">
      <div style="color:#fff;font-size:18px;font-weight:700;letter-spacing:.5px;">XERIN MART</div>
      <div style="color:#9ca3af;font-size:12px;margin-top:2px;">{_html.escape(subtitle)}</div>
    </div>
    <div style="background:#fff;padding:24px;border-radius:0 0 14px 14px;">
      <div style="font-size:16px;font-weight:600;color:#111827;margin-bottom:16px;">{_html.escape(title)}</div>
      {body}
    </div>
    <div style="text-align:center;color:#9ca3af;font-size:11px;padding:16px 0;">
      Automated message from Xerin Mart monitoring &middot; {_now().date()}
    </div>
  </div>
</body></html>"""


def _alert_html(n: AlertNotification) -> str:
    color = _SEV_COLORS.get((n.severity or "").lower(), "#6b7280")
    body = f"""
      <div style="display:inline-block;background:{color};color:#fff;font-size:11px;font-weight:700;
                  letter-spacing:1px;text-transform:uppercase;padding:4px 10px;border-radius:999px;margin-bottom:14px;">
        {_html.escape(n.severity or "alert")}
      </div>
      <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px;
                  font-size:13px;color:#374151;white-space:pre-wrap;line-height:1.55;">{_html.escape(n.body_text)}</div>
      <div style="margin-top:14px;font-size:12px;color:#9ca3af;">Event: {_html.escape(n.event_type or "-")}</div>
    """
    return _shell(title=n.subject.replace("[Xerin ", "").replace("] ", " — ", 1).rstrip("]"),
                  subtitle="Monitoring alert", body=body)


def _weekly_html(report: WeeklyReport) -> str:
    body = f"""
      <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px;
                  font-size:13px;color:#374151;white-space:pre-wrap;line-height:1.6;">{_html.escape(report.body_text)}</div>
      <div style="margin-top:16px;padding:12px 16px;background:#fff7ed;border:1px solid #fed7aa;
                  border-radius:10px;font-size:13px;color:#9a3412;">
        Full report attached as PDF.
      </div>
    """
    return _shell(title=report.subject, subtitle="Weekly operations report", body=body)


def _weekly_pdf(report: WeeklyReport) -> bytes:
    """Branded PDF version of the weekly report (reportlab)."""
    from io import BytesIO
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    margin, y = 18 * mm, H - 18 * mm

    # Header band
    c.setFillColor(HexColor("#111827"))
    c.rect(0, H - 34 * mm, W, 34 * mm, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(margin, H - 15 * mm, "XERIN MART")
    c.setFont("Helvetica", 11)
    c.setFillColor(HexColor("#9ca3af"))
    c.drawString(margin, H - 22 * mm, "Weekly Operations Report")
    c.setFont("Helvetica", 9)
    period = f"{report.period_start.date()}  \u2192  {report.period_end.date()}" if report.period_start else ""
    c.drawString(margin, H - 28 * mm, f"Period: {period}    Generated: {_now().date()}")
    y = H - 44 * mm

    stats = report.stats or {}

    def section(title: str) -> None:
        nonlocal y
        if y < 30 * mm:
            c.showPage()
            y = H - 20 * mm
        c.setFillColor(HexColor("#111827"))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, title)
        y -= 2 * mm
        c.setStrokeColor(HexColor("#e5e7eb"))
        c.setLineWidth(0.6)
        c.line(margin, y, W - margin, y)
        y -= 6 * mm

    def row(label: str, value) -> None:
        nonlocal y
        if y < 20 * mm:
            c.showPage()
            y = H - 20 * mm
        c.setFillColor(HexColor("#6b7280"))
        c.setFont("Helvetica", 10)
        c.drawString(margin + 2 * mm, y, label)
        c.setFillColor(HexColor("#111827"))
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(W - margin - 2 * mm, y, str(value))
        y -= 6.5 * mm

    def kv_lines(lines: list[tuple[str, object]]) -> None:
        for label, value in lines:
            row(label, value)

    section("Users")
    kv_lines([
        ("Total registered users", stats.get("users", {}).get("total", "-")),
        ("New signups this week", stats.get("users", {}).get("new", 0)),
    ])

    section("Marketplace")
    kv_lines([
        ("New sellers", stats.get("sellers", {}).get("new", 0)),
        ("New orders", stats.get("orders", {}).get("new", 0)),
        ("Payment records", stats.get("payments", {}).get("new", 0)),
    ])

    section("Security")
    kv_lines([
        ("Security events", stats.get("security", {}).get("total", 0)),
        ("Unresolved", stats.get("security", {}).get("unresolved", 0)),
    ])
    for kind, n in (stats.get("security", {}).get("by_type") or {}).items():
        row(f"   {kind.replace('_', ' ').title()}", n)

    section("Audit & Alerts")
    kv_lines([
        ("Audit events", stats.get("audit", {}).get("total", 0)),
        ("Alert emails sent", stats.get("alerts", {}).get("sent", 0)),
        ("Alert emails failed", stats.get("alerts", {}).get("failed", 0)),
    ])
    top_actions = stats.get("audit", {}).get("top_actions") or []
    if top_actions:
        section("Top actions")
        for action, n in top_actions[:10]:
            row(f"   {action}", n)

    migrations = stats.get("migrations") or []
    if migrations:
        section("Migrations")
        for m in migrations[:15]:
            row(f"   {(m.get('name') or 'unknown')[:55]}", m.get("status", "-"))

    # Footer
    c.setFillColor(HexColor("#9ca3af"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(W / 2, 12 * mm, "Xerin Mart \u00b7 Automated weekly report \u00b7 Confidential")
    c.showPage()
    c.save()
    return buf.getvalue()


def deliver_alert(db: Session, notification: AlertNotification) -> AlertNotification:
    """Attempt SMTP delivery; records outcome without raising.

    Audit events are never tied to email success — a failed send only
    updates this notification row.
    """
    notification.attempts = (notification.attempts or 0) + 1
    try:
        send_email(
            to=notification.recipient,
            subject=notification.subject,
            body=notification.body_text,
            html=_alert_html(notification),
        )
        notification.status = "sent"
        notification.sent_at = _now()
        notification.next_retry_at = None
        notification.last_error = None
    except Exception as exc:
        logger.warning(
            "Alert email %s failed (attempt %s): %s",
            notification.id, notification.attempts, type(exc).__name__,
        )
        notification.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
        if notification.attempts >= settings.ALERT_EMAIL_MAX_ATTEMPTS:
            notification.status = "failed"
            notification.next_retry_at = None
        else:
            notification.status = "pending"
            delay = settings.ALERT_EMAIL_RETRY_BASE_SECONDS * (2 ** (notification.attempts - 1))
            notification.next_retry_at = _now() + timedelta(seconds=delay)
    db.flush()
    return notification


def process_pending_alerts(db: Session, *, batch_size: int = 20) -> int:
    """Deliver due notifications. Called by the scheduler loop."""
    now = _now()
    due = (
        db.query(AlertNotification)
        .filter(
            AlertNotification.status == "pending",
            (AlertNotification.next_retry_at.is_(None)) | (AlertNotification.next_retry_at <= now),
        )
        .order_by(AlertNotification.created_at.asc())
        .limit(batch_size)
        .all()
    )
    delivered = 0
    for notification in due:
        deliver_alert(db, notification)
        if notification.status == "sent":
            delivered += 1
    db.commit()
    return delivered


def send_weekly_report(db: Session, report: WeeklyReport) -> WeeklyReport:
    try:
        pdf = _weekly_pdf(report)
        attachments = [(
            f"xerin-weekly-report-{report.period_start.date() if report.period_start else ''}.pdf",
            pdf,
            "application/pdf",
        )]
    except Exception:
        logger.exception("Weekly report PDF generation failed — sending without attachment")
        attachments = []
    try:
        send_email(
            to=report.recipient,
            subject=report.subject,
            body=report.body_text,
            html=_weekly_html(report),
            attachments=attachments,
        )
        report.status = "sent"
        report.sent_at = _now()
    except Exception as exc:
        report.status = "failed"
        logger.warning("Weekly report send failed: %s", type(exc).__name__)
    db.flush()
    return report
