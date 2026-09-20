from api.database import SessionLocal
from api.services.escrow_service import release_due_escrow_holds
from api.services.wallet_service import release_eligible_funds


def main():
    db = SessionLocal()
    try:
        escrow_count = release_due_escrow_holds(db)
        legacy_count = release_eligible_funds(db)
        db.commit()
        print(
            f"Released {escrow_count} escrow hold(s) and "
            f"{legacy_count} non-escrow seller earning(s)"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
