"""
Auth / Profile / Admin API Tester — Streamlit app

Exercises every endpoint in your FastAPI auth router (register, register-seller,
login, logout, refresh-token, send-otp, verify-otp, forgot-password,
reset-password), the /users/me profile endpoints, and — only if the logged
in user turns out to be an admin — the full /admin/* router.

How admin detection works:
    After a successful login (or refresh), the app calls GET /users/me with
    the access token. It inspects the returned JSON for role information
    using a few common shapes (is_admin flag, a "role" string, or a "roles"
    list of strings/objects). If any role resolves to "admin" or
    "super_admin", the "Admin Panel" tab is shown. Every logged-in user,
    admin or not, always sees "My Profile".

Run:
    pip install streamlit requests
    streamlit run streamlit_auth_tester.py
"""

import json
import time
import uuid

import requests
import streamlit as st

st.set_page_config(page_title="API Tester", layout="wide")

ADMIN_ROLE_NAMES = {"admin", "super_admin", "superadmin"}

defaults = {
    "base_url": "http://localhost:8000",
    "access_token": "",
    "refresh_token": "",
    "last_email": "",
    "last_phone": "",
    "last_password": "",
    "profile": {},
    "is_admin": False,
    "history": [],  # list of dicts: {method, path, status, body, request}
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def call(method: str, path: str, json_body: dict | None = None, auth: bool = False,
         params: dict | None = None):
    """Make a request and log it to history. Returns (status_code, response_json_or_text)."""
    url = st.session_state.base_url.rstrip("/") + path
    headers = {}
    if auth and st.session_state.access_token:
        headers["Authorization"] = f"Bearer {st.session_state.access_token}"

    # Drop empty-string / None query params so we don't send junk filters.
    clean_params = {k: v for k, v in (params or {}).items() if v not in (None, "")}

    try:
        resp = requests.request(
            method, url, json=json_body, headers=headers,
            params=clean_params or None, timeout=10,
        )
    except requests.exceptions.RequestException as e:
        entry = {
            "method": method, "path": path, "status": "ERROR",
            "body": str(e), "request": json_body, "params": clean_params,
        }
        st.session_state.history.insert(0, entry)
        return None, str(e)

    try:
        body = resp.json()
    except ValueError:
        body = resp.text

    entry = {
        "method": method, "path": path, "status": resp.status_code,
        "body": body, "request": json_body, "params": clean_params,
    }
    st.session_state.history.insert(0, entry)
    return resp.status_code, body


def show_result(status, body):
    if status is None:
        st.error(f"Request failed: {body}")
        return
    if 200 <= status < 300:
        st.success(f"Status {status}")
    elif status == 429:
        st.warning(f"Status {status} — rate limited")
    else:
        st.error(f"Status {status}")
    st.json(body)


def rand_suffix() -> str:
    return uuid.uuid4().hex[:6]


def check_is_admin(profile: dict) -> bool:
    """Best-effort role detection across a few plausible /users/me response shapes."""
    if not isinstance(profile, dict):
        return False

    for key in ("is_admin", "is_superadmin", "super_admin"):
        if profile.get(key):
            return True

    role_val = profile.get("role")
    if isinstance(role_val, str) and role_val.lower() in ADMIN_ROLE_NAMES:
        return True

    roles = profile.get("roles")
    if isinstance(roles, list):
        for r in roles:
            if isinstance(r, str) and r.lower() in ADMIN_ROLE_NAMES:
                return True
            if isinstance(r, dict):
                candidates = []
                if isinstance(r.get("name"), str):
                    candidates.append(r["name"])
                if isinstance(r.get("role_name"), str):
                    candidates.append(r["role_name"])
                if isinstance(r.get("role"), dict) and isinstance(r["role"].get("name"), str):
                    candidates.append(r["role"]["name"])
                if isinstance(r.get("role"), str):
                    candidates.append(r["role"])
                for c in candidates:
                    if c.lower() in ADMIN_ROLE_NAMES:
                        return True
    return False


def fetch_profile(silent: bool = False):
    """Calls GET /users/me, stores it, and re-evaluates is_admin. Returns (status, body)."""
    status, body = call("GET", "/users/me", auth=True)
    if status and status < 300 and isinstance(body, dict):
        st.session_state.profile = body
        st.session_state.is_admin = check_is_admin(body)
    else:
        st.session_state.profile = {}
        st.session_state.is_admin = False
    if not silent:
        show_result(status, body)
    return status, body


with st.sidebar:
    st.header("Connection")
    st.session_state.base_url = st.text_input("Base URL", st.session_state.base_url)

    st.divider()
    st.header("Current tokens")
    st.text_input("Access token", st.session_state.access_token, key="access_token_display", disabled=True)
    st.text_input("Refresh token", st.session_state.refresh_token, key="refresh_token_display", disabled=True)
    if st.button("Clear tokens"):
        st.session_state.access_token = ""
        st.session_state.refresh_token = ""
        st.session_state.profile = {}
        st.session_state.is_admin = False
        st.rerun()

    st.divider()
    st.header("Session identity")
    if st.session_state.access_token:
        if st.session_state.profile:
            name = f"{st.session_state.profile.get('first_name', '')} {st.session_state.profile.get('last_name', '')}".strip()
            st.success(f"Logged in as {name or st.session_state.profile.get('email', '(unknown)')}")
            st.caption(f"Role check: {'🛡️ Admin' if st.session_state.is_admin else '👤 Regular user'}")
        else:
            st.info("Logged in — profile not fetched yet.")
        if st.button("Refresh profile / re-check admin status"):
            fetch_profile()
            st.rerun()
    else:
        st.caption("Not logged in.")

    st.divider()
    st.header("Remembered identity")
    st.caption("Auto-filled into forms below after register/login, editable anytime.")
    st.session_state.last_email = st.text_input("Email", st.session_state.last_email)
    st.session_state.last_phone = st.text_input("Phone", st.session_state.last_phone)
    st.session_state.last_password = st.text_input("Password", st.session_state.last_password, type="password")

    st.divider()
    if st.button("Clear request history"):
        st.session_state.history = []
        st.rerun()

st.title("🔐 Auth / Profile / Admin API Tester")
st.caption("Manual test harness for /auth, /users, and /admin endpoints — happy paths, edge cases, and role-aware navigation.")

tab_names = [
    "Register",
    "Register Seller",
    "Login",
    "Session (logout / refresh)",
    "OTP (send / verify)",
    "Password Reset",
    "My Profile",
]
if st.session_state.is_admin:
    tab_names.append("Admin Panel")
tab_names += ["Stress tests", "Request history"]

tab_map = dict(zip(tab_names, st.tabs(tab_names)))

with tab_map["Register"]:
    st.subheader("POST /auth/register")
    col1, col2 = st.columns(2)
    with col1:
        r_first = st.text_input("First name", "Test", key="r_first")
        r_email = st.text_input("Email", f"user{rand_suffix()}@example.com", key="r_email")
        r_password = st.text_input("Password", "TestPass123!", type="password", key="r_password")
    with col2:
        r_last = st.text_input("Last name", "User", key="r_last")
        r_phone = st.text_input("Phone", f"+2557{rand_suffix()}", key="r_phone")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Register", type="primary"):
            status, body = call("POST", "/auth/register", {
                "first_name": r_first, "last_name": r_last,
                "email": r_email, "phone": r_phone, "password": r_password,
            })
            show_result(status, body)
            if status and status < 300:
                st.session_state.last_email = r_email
                st.session_state.last_phone = r_phone
                st.session_state.last_password = r_password
    with c2:
        st.caption("Edge case: submit twice with the same email/phone to confirm you get 400 'Email or phone already exists'.")
        if st.button("Register again (expect 400 duplicate)"):
            status, body = call("POST", "/auth/register", {
                "first_name": r_first, "last_name": r_last,
                "email": r_email, "phone": r_phone, "password": r_password,
            })
            show_result(status, body)

with tab_map["Register Seller"]:
    st.subheader("POST /auth/register-seller")
    st.caption(
        "Note: business_description/country/region/city/address/product_description/"
        "years_in_business/website_url map to SellerProfile. business_category_ids "
        "must be real BusinessCategory UUIDs from your DB — paste one below."
    )

    col1, col2 = st.columns(2)
    with col1:
        s_first = st.text_input("First name", "Seller", key="s_first")
        s_email = st.text_input("Email", f"seller{rand_suffix()}@example.com", key="s_email")
        s_password = st.text_input("Password", "TestPass123!", type="password", key="s_password")
        s_business_name = st.text_input("Business name", "Test Biz", key="s_business_name")
        s_business_desc = st.text_area("Business description", "A test business", key="s_business_desc")
        s_country = st.text_input("Business country", "Tanzania", key="s_country")
        s_region = st.text_input("Business region", "Dar es Salaam", key="s_region")
    with col2:
        s_last = st.text_input("Last name", "User", key="s_last")
        s_phone = st.text_input("Phone", f"+2557{rand_suffix()}", key="s_phone")
        s_city = st.text_input("Business city", "Dar es Salaam", key="s_city")
        s_address = st.text_input("Business address", "123 Test St", key="s_address")
        s_product_desc = st.text_area("Product description", "Widgets and gadgets", key="s_product_desc")
        s_years = st.text_input("Years in business", "3", key="s_years")
        s_website = st.text_input("Website URL", "https://example.com", key="s_website")

    s_category_ids_raw = st.text_input(
        "Business category IDs (comma-separated UUIDs)",
        "",
        key="s_category_ids",
        help="Query your business_categories table for real UUIDs to paste here.",
    )
    s_agreement = st.checkbox("Agreement accepted", value=True, key="s_agreement")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Register seller", type="primary"):
            category_ids = [c.strip() for c in s_category_ids_raw.split(",") if c.strip()]
            status, body = call("POST", "/auth/register-seller", {
                "first_name": s_first, "last_name": s_last,
                "email": s_email, "phone": s_phone, "password": s_password,
                "business_name": s_business_name,
                "business_description": s_business_desc,
                "business_country": s_country,
                "business_region": s_region,
                "business_city": s_city,
                "business_address": s_address,
                "product_description": s_product_desc,
                "years_in_business": s_years,
                "website_url": s_website,
                "business_category_ids": category_ids,
                "agreement_accepted": s_agreement,
            })
            show_result(status, body)
            if status and status < 300:
                st.session_state.last_email = s_email
                st.session_state.last_phone = s_phone
                st.session_state.last_password = s_password
    with c2:
        st.caption("Edge case: empty category list should return 400 'At least one business category is required'.")
        if st.button("Register seller with NO categories (expect 400)"):
            status, body = call("POST", "/auth/register-seller", {
                "first_name": s_first, "last_name": s_last,
                "email": f"seller{rand_suffix()}@example.com", "phone": f"+2557{rand_suffix()}",
                "password": s_password,
                "business_name": s_business_name,
                "business_description": s_business_desc,
                "business_country": s_country, "business_region": s_region,
                "business_city": s_city, "business_address": s_address,
                "product_description": s_product_desc, "years_in_business": s_years,
                "website_url": s_website,
                "business_category_ids": [],
                "agreement_accepted": s_agreement,
            })
            show_result(status, body)

        st.caption("Edge case: agreement_accepted=False should return 400.")
        if st.button("Register seller WITHOUT agreement (expect 400)"):
            category_ids = [c.strip() for c in s_category_ids_raw.split(",") if c.strip()]
            status, body = call("POST", "/auth/register-seller", {
                "first_name": s_first, "last_name": s_last,
                "email": f"seller{rand_suffix()}@example.com", "phone": f"+2557{rand_suffix()}",
                "password": s_password,
                "business_name": s_business_name,
                "business_description": s_business_desc,
                "business_country": s_country, "business_region": s_region,
                "business_city": s_city, "business_address": s_address,
                "product_description": s_product_desc, "years_in_business": s_years,
                "website_url": s_website,
                "business_category_ids": category_ids,
                "agreement_accepted": False,
            })
            show_result(status, body)

with tab_map["Login"]:
    st.subheader("POST /auth/login")
    l_email = st.text_input("Email", st.session_state.last_email, key="l_email")
    l_password = st.text_input("Password", st.session_state.last_password, type="password", key="l_password")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Login", type="primary"):
            status, body = call("POST", "/auth/login", {"email": l_email, "password": l_password})
            show_result(status, body)
            if status and status < 300 and isinstance(body, dict):
                st.session_state.access_token = body.get("access_token", "")
                st.session_state.refresh_token = body.get("refresh_token", "")
                # Immediately figure out who we are and whether we can see the Admin tab.
                fetch_profile(silent=True)
                st.rerun()
    with c2:
        st.caption("Edge case: expect 401 'Invalid email or password'.")
        if st.button("Login with WRONG password (expect 401)"):
            status, body = call("POST", "/auth/login", {"email": l_email, "password": "definitely-wrong"})
            show_result(status, body)
    with c3:
        st.caption("Edge case: expect 403 if the account hasn't completed OTP verification yet.")
        if st.button("Login unverified account (expect 403)"):
            status, body = call("POST", "/auth/login", {"email": l_email, "password": l_password})
            show_result(status, body)

with tab_map["Session (logout / refresh)"]:
    st.subheader("POST /auth/logout")
    st.caption("Requires a valid access token (sent as Bearer) AND the matching refresh token in the body.")
    if st.button("Logout"):
        status, body = call("POST", "/auth/logout", {"refresh_token": st.session_state.refresh_token}, auth=True)
        show_result(status, body)
        if status and status < 300:
            st.info("Server-side session deleted. Your local refresh_token is now stale — clear it from the sidebar.")
            st.session_state.profile = {}
            st.session_state.is_admin = False

    st.divider()
    st.subheader("POST /auth/refresh-token")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Refresh token", type="primary"):
            status, body = call("POST", "/auth/refresh-token", {"refresh_token": st.session_state.refresh_token})
            show_result(status, body)
            if status and status < 300 and isinstance(body, dict):
                st.session_state.access_token = body.get("access_token", "")
                st.session_state.refresh_token = body.get("refresh_token", "")
                fetch_profile(silent=True)
                st.rerun()
    with c2:
        st.caption("Edge case: garbage token should return 401 'Invalid refresh token'.")
        if st.button("Refresh with GARBAGE token (expect 401)"):
            status, body = call("POST", "/auth/refresh-token", {"refresh_token": "not-a-real-token"})
            show_result(status, body)

with tab_map["OTP (send / verify)"]:
    st.subheader("POST /auth/send-otp")
    otp_phone = st.text_input("Phone", st.session_state.last_phone, key="otp_phone")
    if st.button("Send OTP", type="primary"):
        status, body = call("POST", "/auth/send-otp", {"phone": otp_phone})
        show_result(status, body)
        if isinstance(body, dict) and body.get("dev_otp"):
            st.info(f"DEBUG mode dev_otp: {body['dev_otp']} (only present when settings.DEBUG=True)")

    st.divider()
    st.subheader("POST /auth/verify-otp")
    v_phone = st.text_input("Phone", st.session_state.last_phone, key="v_phone")
    v_code = st.text_input("OTP code", "", key="v_code")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Verify OTP", type="primary"):
            status, body = call("POST", "/auth/verify-otp", {"phone": v_phone, "otp_code": v_code})
            show_result(status, body)
    with c2:
        st.caption("Edge case: wrong code should return 400 'Invalid OTP'.")
        if st.button("Verify with WRONG code (expect 400)"):
            status, body = call("POST", "/auth/verify-otp", {"phone": v_phone, "otp_code": "000000"})
            show_result(status, body)
    with c3:
        st.caption("Edge case: reused/already-verified code should also fail — verify twice in a row.")
        if st.button("Verify SAME code again (expect 400)"):
            status, body = call("POST", "/auth/verify-otp", {"phone": v_phone, "otp_code": v_code})
            show_result(status, body)

with tab_map["Password Reset"]:
    st.subheader("POST /auth/forgot-password")
    fp_email = st.text_input("Email", st.session_state.last_email, key="fp_email")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Forgot password", type="primary"):
            status, body = call("POST", "/auth/forgot-password", {"email": fp_email})
            show_result(status, body)
            if isinstance(body, dict) and body.get("dev_otp"):
                st.info(f"DEBUG mode dev_otp: {body['dev_otp']}")
    with c2:
        st.caption("Edge case: unknown email should still return 200 with a generic message (no account enumeration).")
        if st.button("Forgot password for UNKNOWN email (expect 200, generic message)"):
            status, body = call("POST", "/auth/forgot-password", {"email": f"nobody{rand_suffix()}@example.com"})
            show_result(status, body)

    st.divider()
    st.subheader("POST /auth/reset-password")
    rp_email = st.text_input("Email", st.session_state.last_email, key="rp_email")
    rp_code = st.text_input("OTP code", "", key="rp_code")
    rp_new_password = st.text_input("New password", "NewPass123!", type="password", key="rp_new_password")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Reset password", type="primary"):
            status, body = call("POST", "/auth/reset-password", {
                "email": rp_email, "otp_code": rp_code, "new_password": rp_new_password,
            })
            show_result(status, body)
            if status and status < 300:
                st.session_state.last_password = rp_new_password
                st.success("Remember to log in again with the new password — old sessions were invalidated.")
    with c2:
        st.caption("Edge case: a REGISTER-purpose OTP should NOT work here (purpose isolation). "
                    "Get a code from the Register/Send-OTP tab and try it here — expect 400.")
        if st.button("Reset password with WRONG-purpose code (expect 400)"):
            status, body = call("POST", "/auth/reset-password", {
                "email": rp_email, "otp_code": rp_code, "new_password": rp_new_password,
            })
            show_result(status, body)

with tab_map["My Profile"]:
    st.subheader("GET /users/me")
    if not st.session_state.access_token:
        st.warning("Log in first (Login tab) — this endpoint requires a Bearer token.")
    else:
        if st.button("Fetch my profile", type="primary"):
            fetch_profile()

        if st.session_state.profile:
            st.caption(f"Role check result: {'🛡️ Admin (Admin Panel tab unlocked)' if st.session_state.is_admin else '👤 Regular user'}")
            st.json(st.session_state.profile)

        st.divider()
        st.subheader("PATCH /users/me")
        st.caption("Quick fields for common attributes. Leave a field blank to leave it unchanged.")

        p_first = st.text_input("First name", st.session_state.profile.get("first_name", "") if st.session_state.profile else "", key="p_first")
        p_last = st.text_input("Last name", st.session_state.profile.get("last_name", "") if st.session_state.profile else "", key="p_last")
        p_phone = st.text_input("Phone", "", key="p_phone", placeholder="Leave blank to skip")

        if st.button("Update profile (quick fields)"):
            patch = {}
            if p_first:
                patch["first_name"] = p_first
            if p_last:
                patch["last_name"] = p_last
            if p_phone:
                patch["phone"] = p_phone
            if not patch:
                st.warning("Nothing to update — fill in at least one field.")
            else:
                status, body = call("PATCH", "/users/me", patch, auth=True)
                show_result(status, body)
                if status and status < 300:
                    fetch_profile(silent=True)

        st.caption("Advanced: send an arbitrary JSON body (useful for fields not covered above, e.g. avatar_url).")
        raw_patch = st.text_area("Raw PATCH body (JSON)", "{}", key="raw_patch")
        if st.button("Update profile (raw JSON)"):
            try:
                patch_body = json.loads(raw_patch)
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
            else:
                status, body = call("PATCH", "/users/me", patch_body, auth=True)
                show_result(status, body)
                if status and status < 300:
                    fetch_profile(silent=True)

        st.divider()
        st.subheader("Addresses")
        colA, colB = st.columns(2)
        with colA:
            st.markdown("**GET /addresses**")
            if st.button("List my addresses"):
                status, body = call("GET", "/addresses", auth=True)
                show_result(status, body)
        with colB:
            st.markdown("**POST /addresses**")
            addr_line = st.text_input("Address line", "123 Test St", key="addr_line")
            addr_city = st.text_input("City", "Dar es Salaam", key="addr_city")
            addr_country = st.text_input("Country", "Tanzania", key="addr_country")
            if st.button("Create address"):
                status, body = call("POST", "/addresses", {
                    "address_line": addr_line, "city": addr_city, "country": addr_country,
                }, auth=True)
                show_result(status, body)

        st.markdown("**Update / delete an address**")
        addr_id = st.text_input("Address ID (UUID)", "", key="addr_id")
        c1, c2 = st.columns(2)
        with c1:
            addr_patch_raw = st.text_area("PATCH body (JSON)", '{"city": "New City"}', key="addr_patch_raw")
            if st.button("Update address"):
                if not addr_id:
                    st.warning("Provide an address ID.")
                else:
                    try:
                        addr_patch = json.loads(addr_patch_raw)
                    except json.JSONDecodeError as e:
                        st.error(f"Invalid JSON: {e}")
                    else:
                        status, body = call("PATCH", f"/addresses/{addr_id}", addr_patch, auth=True)
                        show_result(status, body)
        with c2:
            if st.button("Delete address", type="secondary"):
                if not addr_id:
                    st.warning("Provide an address ID.")
                else:
                    status, body = call("DELETE", f"/addresses/{addr_id}", auth=True)
                    show_result(status, body)

if st.session_state.is_admin:
    with tab_map["Admin Panel"]:
        st.info("This tab is only visible because /users/me indicated your account has an admin role.")

        admin_subtabs = st.tabs([
            "Users", "Admins", "Business Categories", "Product Categories",
            "Brands", "Sellers", "Products",
        ])
        
        with admin_subtabs[0]:
            st.markdown("**GET /admin/users**")
            colf1, colf2, colf3, colf4 = st.columns(4)
            with colf1:
                au_page = st.number_input("Page", min_value=1, value=1, key="au_page")
            with colf2:
                au_page_size = st.number_input("Page size", min_value=1, max_value=100, value=10, key="au_page_size")
            with colf3:
                au_search = st.text_input("Search", "", key="au_search")
            with colf4:
                au_status_filter = st.text_input("Status filter", "", key="au_status_filter")
            if st.button("List users", type="primary"):
                status, body = call("GET", "/admin/users", auth=True, params={
                    "page": au_page, "page_size": au_page_size,
                    "search": au_search, "status_filter": au_status_filter,
                })
                show_result(status, body)

            st.divider()
            st.markdown("**POST /admin/users**")
            nc1, nc2 = st.columns(2)
            with nc1:
                nu_first = st.text_input("First name", "New", key="nu_first")
                nu_email = st.text_input("Email", f"admincreated{rand_suffix()}@example.com", key="nu_email")
                nu_password = st.text_input("Password", "TestPass123!", type="password", key="nu_password")
                nu_status = st.text_input("Status", "active", key="nu_status")
            with nc2:
                nu_last = st.text_input("Last name", "User", key="nu_last")
                nu_phone = st.text_input("Phone", f"+2557{rand_suffix()}", key="nu_phone")
                nu_verified = st.checkbox("Is verified", value=True, key="nu_verified")
            if st.button("Create user"):
                status, body = call("POST", "/admin/users", {
                    "first_name": nu_first, "last_name": nu_last, "email": nu_email,
                    "phone": nu_phone, "password": nu_password, "status": nu_status,
                    "is_verified": nu_verified,
                }, auth=True)
                show_result(status, body)

            st.divider()
            st.markdown("**GET / PATCH / DELETE /admin/users/{user_id}**")
            au_id = st.text_input("User ID (UUID)", "", key="au_id")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Get user detail"):
                    if au_id:
                        status, body = call("GET", f"/admin/users/{au_id}", auth=True)
                        show_result(status, body)
                    else:
                        st.warning("Provide a user ID.")
            with c2:
                au_patch_raw = st.text_area("PATCH body (JSON)", '{"status": "active"}', key="au_patch_raw")
                if st.button("Update user"):
                    if not au_id:
                        st.warning("Provide a user ID.")
                    else:
                        try:
                            patch = json.loads(au_patch_raw)
                        except json.JSONDecodeError as e:
                            st.error(f"Invalid JSON: {e}")
                        else:
                            status, body = call("PATCH", f"/admin/users/{au_id}", patch, auth=True)
                            show_result(status, body)
            with c3:
                if st.button("Delete user", type="secondary"):
                    if not au_id:
                        st.warning("Provide a user ID.")
                    else:
                        status, body = call("DELETE", f"/admin/users/{au_id}", auth=True)
                        show_result(status, body)
                        st.caption("Edge case: deleting your own account should return 400.")

        with admin_subtabs[1]:
            st.markdown("**POST /admin/admins** — creates a new user and grants the admin role.")
            ac1, ac2 = st.columns(2)
            with ac1:
                na_first = st.text_input("First name", "New", key="na_first")
                na_email = st.text_input("Email", f"newadmin{rand_suffix()}@example.com", key="na_email")
                na_password = st.text_input("Password", "TestPass123!", type="password", key="na_password")
            with ac2:
                na_last = st.text_input("Last name", "Admin", key="na_last")
                na_phone = st.text_input("Phone", f"+2557{rand_suffix()}", key="na_phone")
            if st.button("Create admin", type="primary"):
                status, body = call("POST", "/admin/admins", {
                    "first_name": na_first, "last_name": na_last, "email": na_email,
                    "phone": na_phone, "password": na_password,
                }, auth=True)
                show_result(status, body)

        with admin_subtabs[2]:
            st.markdown("**GET /admin/business-categories**")
            if st.button("List business categories"):
                status, body = call("GET", "/admin/business-categories", auth=True)
                show_result(status, body)

            st.divider()
            st.markdown("**POST /admin/business-categories**")
            bc_name = st.text_input("Name", "Electronics", key="bc_name")
            bc_slug = st.text_input("Slug", "electronics", key="bc_slug")
            bc_desc = st.text_area("Description", "", key="bc_desc")
            bc_active = st.checkbox("Active", value=True, key="bc_active")
            if st.button("Create business category"):
                status, body = call("POST", "/admin/business-categories", {
                    "name": bc_name, "slug": bc_slug, "description": bc_desc, "active": bc_active,
                }, auth=True)
                show_result(status, body)

            st.divider()
            st.markdown("**PATCH / DELETE /admin/business-categories/{category_id}**")
            bc_id = st.text_input("Category ID (UUID)", "", key="bc_id")
            c1, c2 = st.columns(2)
            with c1:
                bc_patch_raw = st.text_area("PATCH body (JSON)", '{"active": false}', key="bc_patch_raw")
                if st.button("Update business category"):
                    if not bc_id:
                        st.warning("Provide a category ID.")
                    else:
                        try:
                            patch = json.loads(bc_patch_raw)
                        except json.JSONDecodeError as e:
                            st.error(f"Invalid JSON: {e}")
                        else:
                            status, body = call("PATCH", f"/admin/business-categories/{bc_id}", patch, auth=True)
                            show_result(status, body)
            with c2:
                if st.button("Delete business category", type="secondary"):
                    if not bc_id:
                        st.warning("Provide a category ID.")
                    else:
                        status, body = call("DELETE", f"/admin/business-categories/{bc_id}", auth=True)
                        show_result(status, body)

        with admin_subtabs[3]:
            st.markdown("**GET /admin/product-categories**")
            if st.button("List product categories"):
                status, body = call("GET", "/admin/product-categories", auth=True)
                show_result(status, body)

            st.divider()
            st.markdown("**POST /admin/product-categories**")
            pc_name = st.text_input("Name", "Phones", key="pc_name")
            pc_slug = st.text_input("Slug", "phones", key="pc_slug")
            pc_parent = st.text_input("Parent ID (UUID, optional)", "", key="pc_parent")
            if st.button("Create product category"):
                status, body = call("POST", "/admin/product-categories", {
                    "name": pc_name, "slug": pc_slug,
                    "parent_id": pc_parent or None,
                }, auth=True)
                show_result(status, body)

            st.divider()
            st.markdown("**DELETE /admin/product-categories/{category_id}**")
            pc_id = st.text_input("Category ID (UUID)", "", key="pc_id")
            if st.button("Delete product category", type="secondary"):
                if not pc_id:
                    st.warning("Provide a category ID.")
                else:
                    status, body = call("DELETE", f"/admin/product-categories/{pc_id}", auth=True)
                    show_result(status, body)

        with admin_subtabs[4]:
            st.markdown("**GET /admin/brands**")
            if st.button("List brands"):
                status, body = call("GET", "/admin/brands", auth=True)
                show_result(status, body)

            st.divider()
            st.markdown("**POST /admin/brands**")
            br_name = st.text_input("Name", "Acme", key="br_name")
            br_slug = st.text_input("Slug", "acme", key="br_slug")
            if st.button("Create brand"):
                status, body = call("POST", "/admin/brands", {"name": br_name, "slug": br_slug}, auth=True)
                show_result(status, body)

            st.divider()
            st.markdown("**DELETE /admin/brands/{brand_id}**")
            br_id = st.text_input("Brand ID (UUID)", "", key="br_id")
            if st.button("Delete brand", type="secondary"):
                if not br_id:
                    st.warning("Provide a brand ID.")
                else:
                    status, body = call("DELETE", f"/admin/brands/{br_id}", auth=True)
                    show_result(status, body)

        with admin_subtabs[5]:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**GET /admin/sellers**")
                if st.button("List all sellers"):
                    status, body = call("GET", "/admin/sellers", auth=True)
                    show_result(status, body)
            with c2:
                st.markdown("**GET /admin/sellers/pending**")
                if st.button("List pending sellers"):
                    status, body = call("GET", "/admin/sellers/pending", auth=True)
                    show_result(status, body)

            st.divider()
            sl_id = st.text_input("Seller ID (UUID)", "", key="sl_id")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("Get seller detail"):
                    if sl_id:
                        status, body = call("GET", f"/admin/sellers/{sl_id}", auth=True)
                        show_result(status, body)
                    else:
                        st.warning("Provide a seller ID.")
            with c2:
                if st.button("Get seller documents"):
                    if sl_id:
                        status, body = call("GET", f"/admin/sellers/{sl_id}/documents", auth=True)
                        show_result(status, body)
                    else:
                        st.warning("Provide a seller ID.")
            with c3:
                if st.button("Approve seller", type="primary"):
                    if sl_id:
                        status, body = call("POST", f"/admin/sellers/{sl_id}/approve", auth=True)
                        show_result(status, body)
                        st.caption("Edge case: missing required KYC docs (tin, business_profile, business_registration) should return 400.")
                    else:
                        st.warning("Provide a seller ID.")
            with c4:
                sl_reject_reason = st.text_input("Rejection reason", "Incomplete documents", key="sl_reject_reason")
                if st.button("Reject seller", type="secondary"):
                    if sl_id:
                        url = f"/admin/sellers/{sl_id}/reject"
                        headers_note = "Sent as form data (reason=...)."
                        # This endpoint expects Form(...) not JSON — send as form data directly.
                        try:
                            full_url = st.session_state.base_url.rstrip("/") + url
                            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                            resp = requests.post(full_url, data={"reason": sl_reject_reason}, headers=headers, timeout=10)
                            try:
                                body = resp.json()
                            except ValueError:
                                body = resp.text
                            st.session_state.history.insert(0, {
                                "method": "POST", "path": url, "status": resp.status_code,
                                "body": body, "request": {"reason": sl_reject_reason}, "params": None,
                            })
                            show_result(resp.status_code, body)
                        except requests.exceptions.RequestException as e:
                            st.error(f"Request failed: {e}")
                    else:
                        st.warning("Provide a seller ID.")

        with admin_subtabs[6]:
            st.markdown("**GET /admin/products/pending**")
            if st.button("List pending products"):
                status, body = call("GET", "/admin/products/pending", auth=True)
                show_result(status, body)

            st.divider()
            pr_id = st.text_input("Product ID (UUID)", "", key="pr_id")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Approve product", type="primary"):
                    if pr_id:
                        status, body = call("POST", f"/admin/products/{pr_id}/approve", auth=True)
                        show_result(status, body)
                    else:
                        st.warning("Provide a product ID.")
            with c2:
                pr_reject_reason = st.text_input("Rejection reason", "Does not meet guidelines", key="pr_reject_reason")
                if st.button("Reject product", type="secondary"):
                    if pr_id:
                        url = f"/admin/products/{pr_id}/reject"
                        try:
                            full_url = st.session_state.base_url.rstrip("/") + url
                            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                            resp = requests.post(full_url, data={"reason": pr_reject_reason}, headers=headers, timeout=10)
                            try:
                                body = resp.json()
                            except ValueError:
                                body = resp.text
                            st.session_state.history.insert(0, {
                                "method": "POST", "path": url, "status": resp.status_code,
                                "body": body, "request": {"reason": pr_reject_reason}, "params": None,
                            })
                            show_result(resp.status_code, body)
                        except requests.exceptions.RequestException as e:
                            st.error(f"Request failed: {e}")
                    else:
                        st.warning("Provide a product ID.")

with tab_map["Stress tests"]:
    st.subheader("Rate limiting")
    st.caption("Fires N rapid login requests with a wrong password. You should see the last few come back as 429.")

    if "stress_email" not in st.session_state:
        st.session_state.stress_email = ""

    stress_email = st.text_input("Email to hammer", key="stress_email")
    n_calls = st.slider("Number of requests", 1, 30, 15)

    if st.button("Fire requests", type="primary"):
        results = []
        progress = st.progress(0)
        for i in range(n_calls):
            status, _ = call("POST", "/auth/login", {"email": stress_email, "password": "wrong"})
            results.append(status)
            progress.progress((i + 1) / n_calls)
        counts = {}
        for s in results:
            counts[s] = counts.get(s, 0) + 1
        st.write("Status code counts:", counts)
        if 429 in counts:
            st.success(f"Rate limiting confirmed — {counts[429]} requests were throttled with 429.")
        else:
            st.warning("No 429s seen. Either the limit threshold is higher than n_calls, or the limiter isn't triggering.")

    st.divider()
    st.subheader("OTP brute-force lockout")
    st.caption("Fires wrong OTP codes at a phone number repeatedly. Should lock out after OTP_MAX_ATTEMPTS (default 5).")
    lockout_phone = st.text_input("Phone to hammer", st.session_state.last_phone, key="lockout_phone")
    n_otp_calls = st.slider("Number of wrong OTP attempts", 1, 15, 7, key="n_otp_calls")

    if st.button("Fire wrong OTP attempts", type="primary"):
        results = []
        progress = st.progress(0)
        for i in range(n_otp_calls):
            status, _ = call("POST", "/auth/verify-otp", {"phone": lockout_phone, "otp_code": "000000"})
            results.append(status)
            progress.progress((i + 1) / n_otp_calls)
        counts = {}
        for s in results:
            counts[s] = counts.get(s, 0) + 1
        st.write("Status code counts:", counts)
        if 429 in counts:
            st.success(f"OTP lockout confirmed — {counts[429]} attempts were blocked with 429.")
        else:
            st.warning("No 429s seen. Try more attempts, or check OTP_MAX_ATTEMPTS in auth.py.")
            
with tab_map["Request history"]:
    st.subheader("Request history (most recent first)")
    if not st.session_state.history:
        st.info("No requests made yet.")
    for entry in st.session_state.history:
        status = entry["status"]
        color = "🟢" if isinstance(status, int) and status < 300 else ("🟡" if status == 429 else "🔴")
        with st.expander(f"{color} {entry['method']} {entry['path']} → {status}"):
            if entry.get("params"):
                st.markdown("**Query params:**")
                st.code(json.dumps(entry["params"], indent=2), language="json")
            if entry.get("request") is not None:
                st.markdown("**Request body:**")
                st.code(json.dumps(entry["request"], indent=2), language="json")
            st.markdown("**Response:**")
            if isinstance(entry["body"], (dict, list)):
                st.code(json.dumps(entry["body"], indent=2), language="json")
            else:
                st.code(str(entry["body"]))