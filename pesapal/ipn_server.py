"""Standalone Pesapal IPN receiver for the CloudPay simulation.

Public route (behind reverse proxy):
    https://api.xerinmarketplace.com/pesapal-demo/ipn

The IPN does not trust the notification as proof of payment. It calls Pesapal
GetTransactionStatus using OrderTrackingId and updates the simulation SQLite DB.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from pesapal_client import get_transaction_status

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = Path(os.getenv("CLOUDPAY_DB_FILE", str(BASE_DIR / "cloudpay.db")))
BASE_PATH = os.getenv("DEMO_BASE_PATH", "pesapal-demo").strip("/") or "pesapal-demo"
IPN_ROUTE = f"/{BASE_PATH}/ipn"

app = FastAPI(title="CloudPay Pesapal IPN", docs_url=None, redoc_url=None)


def update_order_from_pesapal(tracking_id: str) -> dict:
    result = get_transaction_status(tracking_id)
    merchant_reference = result.get("merchant_reference")

    if merchant_reference:
        con = sqlite3.connect(DB_FILE)
        try:
            con.execute(
                """UPDATE orders
                   SET payment_status=?, confirmation_code=?, payment_method=?,
                       tracking_id=?, updated_at=?
                   WHERE merchant_reference=?""",
                (
                    (result.get("payment_status_description") or "UNKNOWN").upper(),
                    result.get("confirmation_code"),
                    result.get("payment_method"),
                    tracking_id,
                    datetime.now(timezone.utc).isoformat(),
                    merchant_reference,
                ),
            )
            con.commit()
        finally:
            con.close()

    return result


@app.get(f"/{BASE_PATH}/ipn/health")
def health():
    return {"status": "ok", "service": "cloudpay-pesapal-ipn"}


@app.get(IPN_ROUTE)
def pesapal_ipn(
    OrderTrackingId: str | None = Query(default=None),
    OrderMerchantReference: str | None = Query(default=None),
    OrderNotificationType: str | None = Query(default=None),
):
    if not OrderTrackingId:
        return JSONResponse(
            {
                "orderNotificationType": OrderNotificationType,
                "orderTrackingId": OrderTrackingId,
                "orderMerchantReference": OrderMerchantReference,
                "status": 400,
            },
            status_code=400,
        )

    try:
        update_order_from_pesapal(OrderTrackingId)
    except Exception as exc:
        print(f"Pesapal IPN verification failed for {OrderTrackingId}: {exc}")
        return JSONResponse(
            {
                "orderNotificationType": OrderNotificationType,
                "orderTrackingId": OrderTrackingId,
                "orderMerchantReference": OrderMerchantReference,
                "status": 500,
            },
            status_code=500,
        )

    return JSONResponse(
        {
            "orderNotificationType": OrderNotificationType,
            "orderTrackingId": OrderTrackingId,
            "orderMerchantReference": OrderMerchantReference,
            "status": 200,
        }
    )
