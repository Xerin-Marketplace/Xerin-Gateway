from __future__ import annotations

from api.database import SessionLocal
from api.services.unpaid_order_expiry import run_unpaid_order_expiry


def main() -> None:
    db = SessionLocal()
    try:
        result = run_unpaid_order_expiry(db)
        print(
            "Unpaid-order expiry: "
            f"cancelled={result['cancelled_orders']} "
            f"reservations_released={result['released_reservations']} "
            f"paid_skipped={result['skipped_paid_orders']} "
            f"emails_sent={result['emails_sent']} "
            f"email_failures={result['email_failures']}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
