"""Durable XERIN -> logistics partner webhook worker."""
import argparse
import logging
import time

from api.config import settings
from api.database import SessionLocal
from api.services.partner_webhook_service import process_due_events


logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO), format="%(asctime)s %(levelname)s [partner-webhooks] %(message)s")
logger = logging.getLogger("partner-webhooks")


def run_once() -> dict[str, int]:
    db = SessionLocal()
    try:
        result = process_due_events(db)
        logger.info("Webhook batch result: %s", result)
        return result
    except Exception:
        db.rollback()
        logger.exception("Webhook worker batch failed")
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process one batch and exit")
    args = parser.parse_args()
    if args.once:
        run_once()
        return
    logger.info("Partner webhook worker started")
    while True:
        try:
            run_once()
        except Exception:
            pass
        time.sleep(settings.PARTNER_WEBHOOK_WORKER_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
