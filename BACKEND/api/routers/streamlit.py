import streamlit as st
import requests

BASE_URL = "http://127.0.0.1:8000"
AUTH_URL = f"{BASE_URL}/auth"
ADMIN_URL = f"{BASE_URL}/admin"

st.set_page_config(page_title="XERIM Admin Dashboard", layout="wide")

st.title("XERIM Admin Dashboard")

if "access_token" not in st.session_state:
    st.session_state["access_token"] = None


def auth_headers():
    return {
        "Authorization": f"Bearer {st.session_state['access_token']}"
    }


# ================= LOGIN =================

if not st.session_state["access_token"]:
    st.header("Admin Login")

    email = st.text_input("Admin Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        payload = {
            "email": email,
            "password": password
        }

        res = requests.post(f"{AUTH_URL}/login", json=payload)

        if res.status_code == 200:
            data = res.json()
            st.session_state["access_token"] = data["access_token"]
            st.success("Login successful")
            st.rerun()
        else:
            st.error(res.text)

else:
    menu = st.sidebar.selectbox(
        "Admin Actions",
        [
            "Dashboard",
            "All Users",
            "Create User",
            "Create Admin",
            "Pending Sellers",
            "Business Categories",
            "Logout"
        ]
    )

    # ================= DASHBOARD =================

    if menu == "Dashboard":
        st.header("Admin Dashboard")

        res = requests.get(f"{ADMIN_URL}/users", headers=auth_headers())

        if res.status_code == 200:
            data = res.json()
            st.metric("Total Users", data["total"])
        else:
            st.error(res.text)

    # ================= ALL USERS =================

    elif menu == "All Users":
        st.header("All Users")

        search = st.text_input("Search")
        page = st.number_input("Page", min_value=1, value=1)
        page_size = st.number_input("Page Size", min_value=1, max_value=100, value=10)

        params = {
            "page": page,
            "page_size": page_size,
            "search": search if search else None
        }

        res = requests.get(
            f"{ADMIN_URL}/users",
            headers=auth_headers(),
            params=params
        )

        if res.status_code == 200:
            data = res.json()
            st.write(f"Total Users: {data['total']}")

            for user in data["results"]:
                with st.expander(f"{user['email']} - {user['status']}"):
                    st.json(user)

                    col1, col2 = st.columns(2)

                    with col1:
                        new_status = st.selectbox(
                            "Status",
                            ["active", "inactive", "suspended", "pending_verification"],
                            key=f"status_{user['id']}"
                        )

                        if st.button("Update Status", key=f"update_{user['id']}"):
                            update_res = requests.patch(
                                f"{ADMIN_URL}/users/{user['id']}",
                                headers=auth_headers(),
                                json={"status": new_status}
                            )

                            if update_res.status_code == 200:
                                st.success("User updated")
                                st.rerun()
                            else:
                                st.error(update_res.text)

                    with col2:
                        if st.button("Delete User", key=f"delete_{user['id']}"):
                            delete_res = requests.delete(
                                f"{ADMIN_URL}/users/{user['id']}",
                                headers=auth_headers()
                            )

                            if delete_res.status_code == 200:
                                st.success("User deleted")
                                st.rerun()
                            else:
                                st.error(delete_res.text)
        else:
            st.error(res.text)

    # ================= CREATE USER =================

    elif menu == "Create User":
        st.header("Create Normal User")

        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        password = st.text_input("Password", type="password")

        if st.button("Create User"):
            payload = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "password": password,
                "status": "active",
                "is_verified": True
            }

            res = requests.post(
                f"{ADMIN_URL}/users",
                headers=auth_headers(),
                json=payload
            )

            if res.status_code in [200, 201]:
                st.success("User created")
                st.json(res.json())
            else:
                st.error(res.text)

    # ================= CREATE ADMIN =================

    elif menu == "Create Admin":
        st.header("Create Admin User")

        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")
        email = st.text_input("Admin Email")
        phone = st.text_input("Phone")
        password = st.text_input("Password", type="password")

        if st.button("Create Admin"):
            payload = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "password": password,
                "status": "active",
                "is_verified": True
            }

            res = requests.post(
                f"{ADMIN_URL}/admins",
                headers=auth_headers(),
                json=payload
            )

            if res.status_code in [200, 201]:
                st.success("Admin created successfully")
                st.json(res.json())
            else:
                st.error(res.text)

    # ================= PENDING SELLERS =================

    elif menu == "Pending Sellers":
        st.header("Pending Seller Verification")

        res = requests.get(
            f"{ADMIN_URL}/sellers/pending",
            headers=auth_headers()
        )

        if res.status_code == 200:
            sellers = res.json()

            if not sellers:
                st.info("No pending sellers")
            else:
                for seller in sellers:
                    with st.expander(f"{seller['business_name']} - {seller['status']}"):
                        st.json(seller)

                        docs_res = requests.get(
                            f"{ADMIN_URL}/sellers/{seller['id']}/documents",
                            headers=auth_headers()
                        )

                        if docs_res.status_code == 200:
                            st.subheader("KYC Documents")
                            st.json(docs_res.json())

                        col1, col2 = st.columns(2)

                        with col1:
                            if st.button("Approve Seller", key=f"approve_{seller['id']}"):
                                approve_res = requests.post(
                                    f"{ADMIN_URL}/sellers/{seller['id']}/approve",
                                    headers=auth_headers()
                                )

                                if approve_res.status_code == 200:
                                    st.success("Seller approved")
                                    st.rerun()
                                else:
                                    st.error(approve_res.text)

                        with col2:
                            reason = st.text_input(
                                "Reject Reason",
                                key=f"reason_{seller['id']}"
                            )

                            if st.button("Reject Seller", key=f"reject_{seller['id']}"):
                                reject_res = requests.post(
                                    f"{ADMIN_URL}/sellers/{seller['id']}/reject",
                                    headers=auth_headers(),
                                    data={"reason": reason}
                                )

                                if reject_res.status_code == 200:
                                    st.success("Seller rejected")
                                    st.rerun()
                                else:
                                    st.error(reject_res.text)
        else:
            st.error(res.text)

    # ================= BUSINESS CATEGORIES =================

    elif menu == "Business Categories":
        st.header("Business Categories")

        name = st.text_input("Category Name")
        slug = st.text_input("Slug")
        description = st.text_area("Description")
        active = st.checkbox("Active", value=True)

        if st.button("Create Category"):
            payload = {
                "name": name,
                "slug": slug,
                "description": description,
                "active": active
            }

            res = requests.post(
                f"{ADMIN_URL}/business-categories",
                headers=auth_headers(),
                json=payload
            )

            if res.status_code in [200, 201]:
                st.success("Business category created")
                st.rerun()
            else:
                st.error(res.text)

        st.subheader("Existing Categories")

        res = requests.get(
            f"{ADMIN_URL}/business-categories",
            headers=auth_headers()
        )

        if res.status_code == 200:
            for category in res.json():
                with st.expander(category["name"]):
                    st.json(category)

                    if st.button("Delete", key=f"cat_{category['id']}"):
                        delete_res = requests.delete(
                            f"{ADMIN_URL}/business-categories/{category['id']}",
                            headers=auth_headers()
                        )

                        if delete_res.status_code == 200:
                            st.success("Deleted")
                            st.rerun()
                        else:
                            st.error(delete_res.text)
        else:
            st.error(res.text)

    # ================= LOGOUT =================

    elif menu == "Logout":
        st.session_state["access_token"] = None
        st.success("Logged out")
        st.rerun()