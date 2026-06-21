"""Login page."""

import os
import streamlit as st
from uusio.frontend import api_client


def render_login() -> None:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown(
            "<div style='text-align:center;padding:48px 0 32px'>"
            "<h1 style='color:#F5C430;font-size:3rem;font-weight:800;letter-spacing:-2px;margin-bottom:4px'>UusiO</h1>"
            "<p style='color:#8aaa8a;font-size:0.72rem;letter-spacing:2px;text-transform:uppercase'>Simplifying EPR Compliance</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@company.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")

        if submitted:
            if not email or not password:
                st.error("Please enter your email and password.")
                return
            try:
                token_data = api_client.login(email, password)
                st.session_state["token"] = token_data["access_token"]
                st.session_state["api_url"] = os.getenv("API_URL", "http://localhost:8000")
                st.rerun()
            except api_client.APIError as e:
                st.error("Incorrect email or password." if e.status_code == 401 else f"Login failed: {e.detail}")
            except Exception as e:
                st.error(f"Connection error: {e}")
