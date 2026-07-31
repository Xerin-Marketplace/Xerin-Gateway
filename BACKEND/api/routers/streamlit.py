"""XERIN Marketplace Backend — complete Streamlit API tester.

Run:
    pip install streamlit requests
    streamlit run streamlit.py

The app reads FastAPI's OpenAPI schema and automatically exposes every route,
including future routes. It supports JSON bodies, path/query/header parameters,
Bearer authentication, multipart file uploads, request history, and cURL export.
"""

from __future__ import annotations

import json
import mimetypes
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests
import streamlit as st
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="XERIN Backend Tester",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_BASE_URL = "http://169.58.54.110:8081/api/v1"
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head")
METHOD_ORDER = {name: i for i, name in enumerate(HTTP_METHODS)}
METHOD_ICONS = {
    "GET": "🔎",
    "POST": "➕",
    "PUT": "♻️",
    "PATCH": "✏️",
    "DELETE": "🗑️",
    "OPTIONS": "⚙️",
    "HEAD": "📨",
}

# A fallback inventory discovered from the supplied backend. OpenAPI remains
# the source of truth; this list is only displayed when the schema is disabled.
BACKEND_MODULES = {
    "System": ["/", "/health/live", "/health/ready"],
    "Authentication": ["register", "seller registration", "login", "logout", "token refresh", "OTP", "password management"],
    "Users & addresses": ["profile", "addresses", "default address"],
    "Seller onboarding": ["seller profile", "KYC documents", "payout accounts", "approval/rejection"],
    "Stores": ["store profile", "logo/banner", "gallery", "weekly opening hours", "public stores"],
    "Products": ["categories", "brands", "products", "images", "options", "variants", "tags", "submission workflow"],
    "Cart & coupons": ["cart items", "coupon application", "coupon administration"],
    "Orders": ["checkout", "customer orders", "seller fulfilment", "admin order management"],
    "Inventory": ["inventory CRUD", "seller stock", "adjustments", "restocking", "low-stock reporting"],
    "Shipping & delivery": ["zones", "methods", "rates", "quotes", "shipments", "delivery provider integration"],
    "Payments & refunds": ["payment initiation", "callbacks", "payment administration", "refund workflow"],
    "Marketplace finance": ["commissions", "seller wallet", "payouts", "wallet adjustments"],
    "Administration": ["users", "roles", "permissions", "sellers", "products", "catalog data"],
    "Analytics & audit": ["admin analytics", "seller analytics", "reconciliation", "audit logs", "security events"],
}


def init_state() -> None:
    defaults = {
        "base_url": DEFAULT_BASE_URL,
        "access_token": "",
        "refresh_token": "",
        "profile": {},
        "openapi": None,
        "openapi_error": "",
        "history": [],
        "last_response": None,
        "verify_ssl": False,
        "timeout": 30,
        "selected_operation": "",
        "remembered_email": "",
        "remembered_password": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


@dataclass
class Operation:
    method: str
    path: str
    summary: str
    description: str
    tags: list[str]
    operation_id: str
    raw: dict[str, Any]

    @property
    def key(self) -> str:
        return f"{self.method.upper()} {self.path}"

    @property
    def tag(self) -> str:
        return self.tags[0] if self.tags else "Other"


def api_root() -> str:
    """Return server root by removing the configured /api/v1 suffix."""
    base = st.session_state.base_url.rstrip("/")
    for suffix in ("/api/v1", "/api"):
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return base


def openapi_urls() -> list[str]:
    root = api_root()
    base = st.session_state.base_url.rstrip("/")
    return list(dict.fromkeys([f"{root}/openapi.json", f"{base}/openapi.json"]))


def fetch_openapi(show_message: bool = True) -> bool:
    errors: list[str] = []
    for url in openapi_urls():
        try:
            response = requests.get(
                url,
                timeout=st.session_state.timeout,
                verify=st.session_state.verify_ssl,
            )
            if response.ok:
                st.session_state.openapi = response.json()
                st.session_state.openapi_error = ""
                if show_message:
                    st.success(f"Loaded OpenAPI schema from {url}")
                return True
            errors.append(f"{url}: HTTP {response.status_code}")
        except (requests.RequestException, ValueError) as exc:
            errors.append(f"{url}: {exc}")

    st.session_state.openapi = None
    st.session_state.openapi_error = " | ".join(errors)
    if show_message:
        st.error("Could not load OpenAPI schema. " + st.session_state.openapi_error)
    return False


def resolve_ref(schema: Any, document: dict[str, Any] | None = None) -> Any:
    document = document or st.session_state.openapi or {}
    seen: set[str] = set()
    current = schema
    while isinstance(current, dict) and "$ref" in current:
        ref = current["$ref"]
        if ref in seen or not ref.startswith("#/"):
            break
        seen.add(ref)
        current = document
        for part in ref[2:].split("/"):
            current = current.get(part, {})
    return current


def schema_example(schema: Any, depth: int = 0) -> Any:
    if depth > 8:
        return None
    schema = resolve_ref(schema)
    if not isinstance(schema, dict):
        return None
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    for key in ("oneOf", "anyOf", "allOf"):
        if key in schema and schema[key]:
            if key == "allOf":
                merged: dict[str, Any] = {}
                for item in schema[key]:
                    value = schema_example(item, depth + 1)
                    if isinstance(value, dict):
                        merged.update(value)
                return merged
            return schema_example(schema[key][0], depth + 1)

    kind = schema.get("type")
    fmt = schema.get("format")
    if kind == "object" or "properties" in schema:
        result = {}
        required = set(schema.get("required", []))
        for name, child in schema.get("properties", {}).items():
            value = schema_example(child, depth + 1)
            if value is not None or name in required:
                result[name] = value
        return result
    if kind == "array":
        item = schema_example(schema.get("items", {}), depth + 1)
        return [] if item is None else [item]
    if kind == "boolean":
        return False
    if kind == "integer":
        return schema.get("minimum", 0)
    if kind == "number":
        return schema.get("minimum", 0.0)
    if fmt == "email":
        return "user@example.com"
    if fmt == "uuid":
        return "00000000-0000-0000-0000-000000000000"
    if fmt == "date-time":
        return "2026-07-31T10:00:00Z"
    if fmt == "date":
        return "2026-07-31"
    if fmt == "time":
        return "08:00:00"
    if kind == "string" or not kind:
        return "string"
    return None


def operations() -> list[Operation]:
    spec = st.session_state.openapi or {}
    result: list[Operation] = []
    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method in HTTP_METHODS:
            raw = path_item.get(method)
            if not isinstance(raw, dict):
                continue
            result.append(
                Operation(
                    method=method.upper(),
                    path=path,
                    summary=raw.get("summary") or raw.get("operationId") or path,
                    description=raw.get("description") or "",
                    tags=raw.get("tags") or ["Other"],
                    operation_id=raw.get("operationId") or f"{method}_{path}",
                    raw=raw,
                )
            )
    return sorted(result, key=lambda op: (op.tag.lower(), op.path, METHOD_ORDER.get(op.method.lower(), 99)))


def merged_parameters(op: Operation) -> list[dict[str, Any]]:
    spec = st.session_state.openapi or {}
    path_item = spec.get("paths", {}).get(op.path, {})
    params = []
    for item in path_item.get("parameters", []) + op.raw.get("parameters", []):
        params.append(resolve_ref(item))
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in params:
        if isinstance(item, dict):
            unique[(str(item.get("in")), str(item.get("name")))] = item
    return list(unique.values())


def parse_scalar(raw: str, schema: dict[str, Any]) -> Any:
    if raw == "":
        return None
    schema = resolve_ref(schema)
    kind = schema.get("type")
    if kind == "integer":
        return int(raw)
    if kind == "number":
        return float(raw)
    if kind == "boolean":
        return raw.lower() in {"true", "1", "yes", "on"}
    if kind == "array":
        return [x.strip() for x in raw.split(",") if x.strip()]
    return raw


def pretty(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def request_call(
    method: str,
    path: str,
    *,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    header_params: dict[str, Any] | None = None,
    json_body: Any = None,
    form_data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    use_auth: bool = True,
) -> tuple[int | None, Any, dict[str, Any]]:
    rendered_path = path
    for name, value in (path_params or {}).items():
        rendered_path = rendered_path.replace("{" + name + "}", quote(str(value), safe=""))

    url = st.session_state.base_url.rstrip("/") + rendered_path
    headers = {str(k): str(v) for k, v in (header_params or {}).items() if v not in (None, "")}
    if use_auth and st.session_state.access_token:
        headers["Authorization"] = f"Bearer {st.session_state.access_token}"

    clean_query = {k: v for k, v in (query_params or {}).items() if v not in (None, "", [])}
    started = time.perf_counter()
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            params=clean_query or None,
            json=json_body if files is None and form_data is None else None,
            data=form_data or None,
            files=files or None,
            timeout=st.session_state.timeout,
            verify=st.session_state.verify_ssl,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        try:
            body = response.json()
        except ValueError:
            body = response.text
        meta = {
            "method": method,
            "path": rendered_path,
            "url": response.url,
            "status": response.status_code,
            "elapsed_ms": elapsed_ms,
            "request": json_body if json_body is not None else form_data,
            "query": clean_query,
            "response": body,
            "response_headers": dict(response.headers),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        st.session_state.history.insert(0, meta)
        st.session_state.history = st.session_state.history[:100]
        st.session_state.last_response = meta
        return response.status_code, body, meta
    except requests.RequestException as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        meta = {
            "method": method,
            "path": rendered_path,
            "url": url,
            "status": None,
            "elapsed_ms": elapsed_ms,
            "request": json_body if json_body is not None else form_data,
            "query": clean_query,
            "response": str(exc),
            "response_headers": {},
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        st.session_state.history.insert(0, meta)
        st.session_state.last_response = meta
        return None, str(exc), meta


def show_response(status_code: int | None, body: Any, meta: dict[str, Any]) -> None:
    c1, c2, c3 = st.columns(3)
    if status_code is None:
        c1.error("Connection error")
    elif 200 <= status_code < 300:
        c1.success(f"HTTP {status_code}")
    elif status_code < 500:
        c1.warning(f"HTTP {status_code}")
    else:
        c1.error(f"HTTP {status_code}")
    c2.metric("Response time", f"{meta['elapsed_ms']} ms")
    c3.caption(meta["url"])
    if isinstance(body, (dict, list)):
        st.json(body)
    else:
        st.code(str(body), language="text")
    with st.expander("Response headers"):
        st.json(meta.get("response_headers", {}))


def maybe_capture_tokens(body: Any) -> None:
    if not isinstance(body, dict):
        return
    access = body.get("access_token")
    refresh = body.get("refresh_token")
    if access:
        st.session_state.access_token = str(access)
    if refresh:
        st.session_state.refresh_token = str(refresh)
    user = body.get("user")
    if isinstance(user, dict):
        st.session_state.profile = user


def render_endpoint_form(op: Operation) -> None:
    st.subheader(f"{METHOD_ICONS.get(op.method, '🌐')} {op.method} {op.path}")
    st.caption(op.summary)
    if op.description:
        st.markdown(op.description)

    parameters = merged_parameters(op)
    path_values: dict[str, Any] = {}
    query_values: dict[str, Any] = {}
    header_values: dict[str, Any] = {}

    with st.form(f"endpoint_form_{op.operation_id}_{op.method}", clear_on_submit=False):
        if parameters:
            st.markdown("#### Parameters")
        cols = st.columns(2)
        for index, param in enumerate(parameters):
            location = param.get("in", "query")
            name = param.get("name", "parameter")
            required = bool(param.get("required"))
            schema = resolve_ref(param.get("schema", {}))
            label = f"{name} ({location})" + (" *" if required else "")
            help_text = param.get("description") or ""
            enum_values = schema.get("enum")
            key = f"param_{op.operation_id}_{location}_{name}"
            with cols[index % 2]:
                if enum_values:
                    choices = enum_values if required else [""] + enum_values
                    value = st.selectbox(label, choices, key=key, help=help_text)
                elif schema.get("type") == "boolean":
                    choices = ["", "true", "false"] if not required else ["true", "false"]
                    value = st.selectbox(label, choices, key=key, help=help_text)
                else:
                    example = schema.get("example", param.get("example", ""))
                    value = st.text_input(label, value=str(example or ""), key=key, help=help_text)
            try:
                parsed = parse_scalar(str(value), schema)
            except ValueError:
                parsed = value
            if location == "path":
                path_values[name] = parsed
            elif location == "header":
                header_values[name] = parsed
            else:
                query_values[name] = parsed

        body_spec = op.raw.get("requestBody")
        json_body: Any = None
        form_data: dict[str, Any] | None = None
        file_payload: dict[str, Any] | None = None
        body_error = ""

        if body_spec:
            body_spec = resolve_ref(body_spec)
            content = body_spec.get("content", {})
            st.markdown("#### Request body")

            if "application/json" in content:
                media = content["application/json"]
                schema = media.get("schema", {})
                example = media.get("example", schema_example(schema))
                body_text = st.text_area(
                    "JSON body",
                    value=pretty(example if example is not None else {}),
                    height=280,
                    key=f"body_{op.operation_id}",
                )
                try:
                    json_body = json.loads(body_text) if body_text.strip() else None
                except json.JSONDecodeError as exc:
                    body_error = f"Invalid JSON: {exc}"

            else:
                media_type = next(
                    (name for name in content if name in {"multipart/form-data", "application/x-www-form-urlencoded"}),
                    next(iter(content), ""),
                )
                media = content.get(media_type, {})
                schema = resolve_ref(media.get("schema", {}))
                properties = schema.get("properties", {})
                required_fields = set(schema.get("required", []))
                form_data = {}
                file_payload = {}
                for field_name, field_schema_raw in properties.items():
                    field_schema = resolve_ref(field_schema_raw)
                    required = field_name in required_fields
                    label = field_name + (" *" if required else "")
                    widget_key = f"multipart_{op.operation_id}_{field_name}"
                    if field_schema.get("format") == "binary":
                        uploaded = st.file_uploader(label, key=widget_key)
                        if uploaded is not None:
                            content_type = uploaded.type or mimetypes.guess_type(uploaded.name)[0] or "application/octet-stream"
                            file_payload[field_name] = (uploaded.name, uploaded.getvalue(), content_type)
                    elif field_schema.get("type") == "boolean":
                        form_data[field_name] = st.checkbox(label, value=bool(field_schema.get("default", False)), key=widget_key)
                    elif field_schema.get("enum"):
                        choices = field_schema["enum"] if required else [""] + field_schema["enum"]
                        form_data[field_name] = st.selectbox(label, choices, key=widget_key)
                    else:
                        default = schema_example(field_schema)
                        raw_value = st.text_input(label, value="" if default is None else str(default), key=widget_key)
                        if raw_value != "":
                            form_data[field_name] = raw_value
                if not file_payload:
                    file_payload = None
                if not form_data:
                    form_data = None

        use_auth = st.checkbox(
            "Send Bearer token",
            value=True,
            key=f"auth_{op.operation_id}",
            help="Uses the access token stored in the sidebar.",
        )
        submitted = st.form_submit_button("Send request", type="primary", use_container_width=True)

    if submitted:
        missing = [name for name, value in path_values.items() if value in (None, "")]
        if missing:
            st.error("Missing required path parameter(s): " + ", ".join(missing))
            return
        if body_error:
            st.error(body_error)
            return
        status_code, body, meta = request_call(
            op.method,
            op.path,
            path_params=path_values,
            query_params=query_values,
            header_params=header_values,
            json_body=json_body,
            form_data=form_data,
            files=file_payload,
            use_auth=use_auth,
        )
        maybe_capture_tokens(body)
        show_response(status_code, body, meta)


def auth_quick_actions() -> None:
    st.subheader("Authentication quick actions")
    login_tab, profile_tab, refresh_tab, health_tab = st.tabs(["Login", "My profile", "Refresh token", "Health"])

    with login_tab:
        with st.form("quick_login"):
            email = st.text_input("Email", value=st.session_state.remembered_email)
            password = st.text_input("Password", value=st.session_state.remembered_password, type="password")
            submitted = st.form_submit_button("Login", type="primary")
        if submitted:
            status_code, body, meta = request_call(
                "POST", "/auth/login", json_body={"email": email, "password": password}, use_auth=False
            )
            if status_code and status_code < 300:
                st.session_state.remembered_email = email
                st.session_state.remembered_password = password
                maybe_capture_tokens(body)
            show_response(status_code, body, meta)

    with profile_tab:
        if st.button("GET /users/me", use_container_width=True):
            status_code, body, meta = request_call("GET", "/users/me")
            if status_code and status_code < 300 and isinstance(body, dict):
                st.session_state.profile = body
            show_response(status_code, body, meta)

    with refresh_tab:
        refresh_value = st.text_area("Refresh token", value=st.session_state.refresh_token, height=120)
        if st.button("POST /auth/refresh-token", use_container_width=True):
            status_code, body, meta = request_call(
                "POST", "/auth/refresh-token", json_body={"refresh_token": refresh_value}, use_auth=False
            )
            if status_code and status_code < 300:
                maybe_capture_tokens(body)
            show_response(status_code, body, meta)

    with health_tab:
        c1, c2 = st.columns(2)
        if c1.button("Liveness", use_container_width=True):
            root = api_root()
            old = st.session_state.base_url
            st.session_state.base_url = root
            status_code, body, meta = request_call("GET", "/health/live", use_auth=False)
            st.session_state.base_url = old
            show_response(status_code, body, meta)
        if c2.button("Readiness", use_container_width=True):
            root = api_root()
            old = st.session_state.base_url
            st.session_state.base_url = root
            status_code, body, meta = request_call("GET", "/health/ready", use_auth=False)
            st.session_state.base_url = old
            show_response(status_code, body, meta)


def render_history() -> None:
    st.subheader("Request history")
    if not st.session_state.history:
        st.info("No requests have been sent yet.")
        return
    for index, item in enumerate(st.session_state.history):
        code = item.get("status")
        title = f"{item['timestamp']} · {item['method']} {item['path']} · {code or 'ERROR'} · {item['elapsed_ms']} ms"
        with st.expander(title, expanded=index == 0):
            st.caption(item.get("url", ""))
            left, right = st.columns(2)
            with left:
                st.markdown("**Request**")
                st.json({"query": item.get("query"), "body": item.get("request")})
            with right:
                st.markdown("**Response**")
                if isinstance(item.get("response"), (dict, list)):
                    st.json(item["response"])
                else:
                    st.code(str(item.get("response")), language="text")


# ------------------------------ Sidebar ---------------------------------
with st.sidebar:
    st.title("🛒 XERIN Tester")
    st.session_state.base_url = st.text_input(
        "API base URL",
        value=st.session_state.base_url,
        help="Normally http://169.58.54.110:8081/api/v1",
    )
    st.session_state.timeout = st.number_input("Timeout (seconds)", min_value=3, max_value=180, value=int(st.session_state.timeout))
    st.session_state.verify_ssl = st.checkbox("Verify SSL certificate", value=st.session_state.verify_ssl)

    c1, c2 = st.columns(2)
    if c1.button("Load API", use_container_width=True):
        fetch_openapi()
        st.rerun()
    if c2.button("Clear", use_container_width=True):
        st.session_state.openapi = None
        st.session_state.openapi_error = ""
        st.rerun()

    st.divider()
    st.markdown("### Session")
    st.session_state.access_token = st.text_area("Access token", value=st.session_state.access_token, height=110)
    st.session_state.refresh_token = st.text_area("Refresh token", value=st.session_state.refresh_token, height=90)
    if st.button("Clear tokens", use_container_width=True):
        st.session_state.access_token = ""
        st.session_state.refresh_token = ""
        st.session_state.profile = {}
        st.rerun()

    if st.session_state.profile:
        name = " ".join(
            str(st.session_state.profile.get(key, ""))
            for key in ("first_name", "last_name")
        ).strip()
        st.success(name or st.session_state.profile.get("email", "Authenticated user"))
        st.json(st.session_state.profile)

    st.divider()
    st.markdown("### Data")
    st.download_button(
        "Download request history",
        data=pretty(st.session_state.history),
        file_name="xerin_api_test_history.json",
        mime="application/json",
        use_container_width=True,
    )
    if st.button("Clear history", use_container_width=True):
        st.session_state.history = []
        st.session_state.last_response = None
        st.rerun()


# ------------------------------- Main -----------------------------------
st.title("XERIN Marketplace — Complete Backend Tester")
st.caption("A schema-driven test client for every FastAPI endpoint in your marketplace backend.")

if st.session_state.openapi is None and not st.session_state.openapi_error:
    fetch_openapi(show_message=False)

ops = operations()
overview_tab, quick_tab, explorer_tab, history_tab = st.tabs(
    ["📊 Backend overview", "🔐 Quick actions", "🧪 Endpoint explorer", "🕘 History"]
)

with overview_tab:
    if ops:
        tag_count = len({op.tag for op in ops})
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("API operations", len(ops))
        c2.metric("Modules/tags", tag_count)
        c3.metric("GET routes", sum(op.method == "GET" for op in ops))
        c4.metric("Write routes", sum(op.method in {"POST", "PUT", "PATCH", "DELETE"} for op in ops))

        rows = []
        for tag in sorted({op.tag for op in ops}):
            tagged = [op for op in ops if op.tag == tag]
            rows.append(
                {
                    "Module": tag,
                    "Total": len(tagged),
                    "GET": sum(op.method == "GET" for op in tagged),
                    "POST": sum(op.method == "POST" for op in tagged),
                    "PUT/PATCH": sum(op.method in {"PUT", "PATCH"} for op in tagged),
                    "DELETE": sum(op.method == "DELETE" for op in tagged),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
        with st.expander("All discovered operations"):
            st.dataframe(
                [{"Method": op.method, "Path": op.path, "Module": op.tag, "Summary": op.summary} for op in ops],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.warning(
            "OpenAPI is unavailable. In production your backend disables /openapi.json. "
            "Run the backend in development mode or temporarily expose OpenAPI to use the automatic explorer."
        )
        if st.session_state.openapi_error:
            st.code(st.session_state.openapi_error)
        st.markdown("### Features found in the uploaded backend")
        for module, features in BACKEND_MODULES.items():
            with st.expander(module):
                st.write(", ".join(features))

with quick_tab:
    auth_quick_actions()

with explorer_tab:
    if not ops:
        st.error("Load a reachable OpenAPI schema first using the sidebar button.")
    else:
        left, right = st.columns([1, 2.3])
        with left:
            search = st.text_input("Search endpoint", placeholder="products, seller, refund...")
            tags = sorted({op.tag for op in ops})
            selected_tag = st.selectbox("Module", ["All modules"] + tags)
            methods = st.multiselect("Methods", [m.upper() for m in HTTP_METHODS], default=[])

            filtered = [
                op for op in ops
                if (selected_tag == "All modules" or op.tag == selected_tag)
                and (not methods or op.method in methods)
                and (
                    not search
                    or search.lower() in op.path.lower()
                    or search.lower() in op.summary.lower()
                    or search.lower() in op.tag.lower()
                )
            ]
            labels = [op.key for op in filtered]
            if labels:
                current_index = labels.index(st.session_state.selected_operation) if st.session_state.selected_operation in labels else 0
                selected = st.radio("Endpoints", labels, index=current_index, label_visibility="collapsed")
                st.session_state.selected_operation = selected
            else:
                selected = ""
                st.info("No endpoint matches the filters.")

        with right:
            selected_op = next((op for op in filtered if op.key == selected), None)
            if selected_op:
                render_endpoint_form(selected_op)

with history_tab:
    render_history()