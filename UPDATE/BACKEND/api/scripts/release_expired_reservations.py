from api.database import SessionLocal
from api.services.inventory_reservations import release_expired_reservations


def main() -> None:
    db = SessionLocal()
    try:
        count = release_expired_reservations(db)
        db.commit()
        print(f"Released {count} expired inventory reservation(s)")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
