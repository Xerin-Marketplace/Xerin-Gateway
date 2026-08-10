from api.database import SessionLocal
from api.services.wallet_service import release_eligible_funds
def main():
    db=SessionLocal()
    try:
        count=release_eligible_funds(db); db.commit(); print(f"Released {count} seller earning(s)")
    except Exception:
        db.rollback(); raise
    finally: db.close()
if __name__=="__main__": main()
