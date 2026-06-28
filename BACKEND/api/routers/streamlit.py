import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000/auth"

st.set_page_config(page_title="TISEZA Auth Test", layout="centered")

st.title("TISEZA Authentication System")

menu = st.sidebar.selectbox(
    "Choose Action",
    ["Register", "Verify OTP", "Login"]
)

# ---------------- REGISTER ----------------
if menu == "Register":
    st.header("User Registration")

    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")
    email = st.text_input("Email")
    phone = st.text_input("Phone")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "password": password
        }

        res = requests.post(f"{API_URL}/register", json=payload)

        if res.status_code == 200:
            st.success("Registered successfully! Check OTP in SMS/Email")
        else:
            st.error(res.text)


# ---------------- VERIFY OTP ----------------
elif menu == "Verify OTP":
    st.header("Verify OTP")

    phone = st.text_input("Phone")
    otp = st.text_input("OTP Code")

    if st.button("Verify"):
        payload = {
            "phone": phone,
            "otp_code": otp
        }

        res = requests.post(f"{API_URL}/verify-otp", json=payload)

        if res.status_code == 200:
            st.success("OTP Verified Successfully! You can now login.")
        else:
            st.error(res.text)


# ---------------- LOGIN ----------------
elif menu == "Login":
    st.header("Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        payload = {
            "email": email,
            "password": password
        }

        res = requests.post(f"{API_URL}/login", json=payload)

        if res.status_code == 200:
            data = res.json()
            st.success("Login successful!")
            st.json(data)

            st.session_state["access_token"] = data["access_token"]
            st.session_state["refresh_token"] = data["refresh_token"]

        else:
            st.error(res.text)