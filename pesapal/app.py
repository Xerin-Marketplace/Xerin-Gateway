import os
import sqlite3
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone

import streamlit as st
from dotenv import load_dotenv

from pesapal_client import base_url as pesapal_base_url, token as pesapal_token, get_transaction_status

load_dotenv()

st.set_page_config(page_title="CloudPay Tanzania", page_icon="☁️", layout="centered")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.getenv("CLOUDPAY_DB_FILE", os.path.join(BASE_DIR, "cloudpay.db"))

PACKAGES = {
    "Starter": {
        "price": 10000,
        "cpu": "1 vCPU",
        "ram": "1 GB RAM",
        "storage": "20 GB SSD",
    },
    "Business": {
        "price": 25000,
        "cpu": "2 vCPU",
        "ram": "4 GB RAM",
        "storage": "80 GB SSD",
    },
    "Pro": {
        "price": 50000,
        "cpu": "4 vCPU",
        "ram": "8 GB RAM",
        "storage": "160 GB SSD",
    },
}


def db():
    con = sqlite3.connect(DB_FILE, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        merchant_reference TEXT NOT NULL UNIQUE,
        package_name TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT 'TZS',
        tracking_id TEXT,
        redirect_url TEXT,
        payment_status TEXT NOT NULL DEFAULT 'CREATED',
        confirmation_code TEXT,
        payment_method TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    con.commit()
    con.close()


def hash_password(password: str, salt_hex: str | None = None):
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, stored_hash: str):
    _, candidate = hash_password(password, salt_hex)
    return hmac.compare_digest(candidate, stored_hash)


def register_user(full_name, email, phone, password):
    email = email.strip().lower()
    salt, pwd_hash = hash_password(password)
    con = db()
    try:
        con.execute(
            """INSERT INTO users(full_name,email,phone,salt,password_hash,created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                full_name.strip(),
                email,
                phone.strip(),
                salt,
                pwd_hash,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        con.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "An account with that email already exists."
    finally:
        con.close()


def login_user(email, password):
    con = db()
    row = con.execute(
        "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
    ).fetchone()
    con.close()

    if not row or not verify_password(password, row["salt"], row["password_hash"]):
        return None
    return dict(row)



def submit_order(user, package_name):
    import requests
    package = PACKAGES[package_name]
    token = pesapal_token()

    notification_id = os.getenv("PESAPAL_IPN_ID", "").strip()
    callback_url = os.getenv("PESAPAL_CALLBACK_URL", "").strip()

    if not notification_id:
        raise RuntimeError(
            "Missing PESAPAL_IPN_ID. Register your IPN URL first and place the returned ID in .env."
        )
    if not callback_url:
        raise RuntimeError("Missing PESAPAL_CALLBACK_URL in .env.")

    merchant_reference = f"CLOUD-{uuid.uuid4().hex[:20].upper()}"

    payload = {
        "id": merchant_reference,
        "currency": "TZS",
        "amount": float(package["price"]),
        "description": f"{package_name} cloud computing package",
        "callback_url": callback_url,
        "redirect_mode": "",
        "notification_id": notification_id,
        "branch": "CloudPay Tanzania",
        "billing_address": {
            "email_address": user["email"],
            "phone_number": user["phone"],
            "country_code": "TZ",
            "first_name": user["full_name"].split()[0],
            "middle_name": "",
            "last_name": (
                user["full_name"].split()[-1]
                if len(user["full_name"].split()) > 1
                else ""
            ),
            "line_1": "",
            "line_2": "",
            "city": "Dar es Salaam",
            "state": "",
            "postal_code": "",
            "zip_code": "",
        },
    }

    response = requests.post(
        f"{pesapal_base_url()}/api/Transactions/SubmitOrderRequest",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()

    if not result.get("redirect_url"):
        raise RuntimeError(result.get("message") or f"Order submission failed: {result}")

    now = datetime.now(timezone.utc).isoformat()
    con = db()
    con.execute(
        """INSERT INTO orders
           (user_id, merchant_reference, package_name, amount, currency,
            tracking_id, redirect_url, payment_status, created_at, updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (
            user["id"],
            merchant_reference,
            package_name,
            package["price"],
            "TZS",
            result.get("order_tracking_id"),
            result.get("redirect_url"),
            "PENDING",
            now,
            now,
        ),
    )
    con.commit()
    con.close()

    return result, merchant_reference


def verify_transaction(tracking_id: str):
    result = get_transaction_status(tracking_id)

    merchant_reference = result.get("merchant_reference")
    if merchant_reference:
        con = db()
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
        con.close()

    return result

def user_orders(user_id):
    con = db()
    rows = con.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (user_id,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def logout():
    st.session_state.user = None
    st.session_state.page = "Login"
    st.rerun()


init_db()

if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "Login"

st.title("☁️ CloudPay Tanzania")
st.caption("Streamlit + Pesapal API 3.0 demo")

# Handle Pesapal redirect back to this Streamlit URL.
params = st.query_params
tracking_from_callback = params.get("OrderTrackingId")

if tracking_from_callback:
    st.info("Pesapal returned you to the app. Verifying the payment with Pesapal...")
    try:
        status = verify_transaction(tracking_from_callback)
        payment_status = (status.get("payment_status_description") or "UNKNOWN").upper()

        if payment_status == "COMPLETED":
            st.success("✅ Payment verified successfully. Your package is active.")
            st.balloons()
        elif payment_status == "FAILED":
            st.error("Payment failed.")
        elif payment_status == "REVERSED":
            st.warning("Payment was reversed.")
        else:
            st.warning(f"Current payment status: {payment_status}")

        with st.expander("Payment details"):
            st.write("Reference:", status.get("merchant_reference"))
            st.write("Amount:", status.get("amount"), status.get("currency"))
            st.write("Method:", status.get("payment_method"))
            st.write("Confirmation:", status.get("confirmation_code"))
    except Exception as exc:
        st.error(f"Could not verify payment: {exc}")

    if st.button("Clear payment result"):
        st.query_params.clear()
        st.rerun()

if not st.session_state.user:
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            user = login_user(email, password)
            if user:
                st.session_state.user = user
                st.session_state.page = "Packages"
                st.rerun()
            else:
                st.error("Invalid email or password.")

    with tab_register:
        with st.form("register_form"):
            full_name = st.text_input("Full name")
            email = st.text_input("Email address")
            phone = st.text_input("Phone number", placeholder="2557XXXXXXXX")
            password = st.text_input("Create password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account", use_container_width=True)

        if submitted:
            if not all([full_name.strip(), email.strip(), phone.strip(), password]):
                st.error("Please complete all fields.")
            elif len(password) < 8:
                st.error("Password must contain at least 8 characters.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                ok, msg = register_user(full_name, email, phone, password)
                if ok:
                    st.success(msg + " You can now log in.")
                else:
                    st.error(msg)

else:
    user = st.session_state.user

    with st.sidebar:
        st.write(f"### 👤 {user['full_name']}")
        st.caption(user["email"])
        page = st.radio("Menu", ["Packages", "My payments"])
        st.divider()
        if st.button("Logout", use_container_width=True):
            logout()

    if page == "Packages":
        st.subheader("Choose your cloud package")
        st.write("Select a package, create a Pesapal order, then pay on Pesapal's secure checkout.")

        package_name = st.selectbox("Package", list(PACKAGES.keys()))
        p = PACKAGES[package_name]

        st.metric("Price", f"TZS {p['price']:,.0f} / month")
        st.write(f"**CPU:** {p['cpu']}")
        st.write(f"**Memory:** {p['ram']}")
        st.write(f"**Storage:** {p['storage']}")

        if st.button("Pay securely with Pesapal", type="primary", use_container_width=True):
            try:
                with st.spinner("Creating secure Pesapal checkout..."):
                    result, ref = submit_order(user, package_name)

                st.session_state.checkout_url = result["redirect_url"]
                st.session_state.checkout_ref = ref
                st.success("Checkout created.")
            except Exception as exc:
                st.error(str(exc))

        if st.session_state.get("checkout_url"):
            st.link_button(
                "Continue to card / payment checkout →",
                st.session_state.checkout_url,
                use_container_width=True,
                type="primary",
            )
            st.caption(f"Order reference: {st.session_state.get('checkout_ref')}")

    else:
        st.subheader("My payments")
        orders = user_orders(user["id"])

        if not orders:
            st.info("You have no payment orders yet.")
        else:
            for order in orders:
                with st.container(border=True):
                    left, right = st.columns([2, 1])
                    with left:
                        st.write(f"**{order['package_name']}**")
                        st.caption(order["merchant_reference"])
                        st.write(
                            f"TZS {order['amount']:,.0f} • "
                            f"{order['payment_status']}"
                        )
                    with right:
                        if order.get("tracking_id") and st.button(
                            "Verify", key=f"verify-{order['id']}"
                        ):
                            try:
                                result = verify_transaction(order["tracking_id"])
                                st.success(
                                    result.get("payment_status_description", "Checked")
                                )
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

        st.caption(
            "Only a server-side Pesapal verification result marked COMPLETED "
            "should activate real cloud resources."
        )
