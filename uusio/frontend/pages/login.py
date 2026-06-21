"""Login page."""

import os

import streamlit as st
from uusio.frontend import api_client

_DEFAULT_API_URL = os.getenv("API_URL", "http://localhost:8000")


def render_login() -> None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("\U0001f331 Uusio")
        st.subheader("EPR Compliance Platform")
        st.divider()

        api_url = st.text_input(
            "API URL",
            value=st.session_state.get("api_url", _DEFAULT_API_URL),
        )
        username = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Log in", use_container_width=True, type="primary"):
            if not username or not password:
                st.warning("Please enter your email and password.")
                return
            st.session_state["api_url"] = api_url
            try:
                token_data = api_client.login(username, password)
                st.session_state["token"] = token_data["access_token"]
                st.success("Logged in!")
                st.rerun()
            except Exception as exc:
                st.error(f"Login failed: {exc}")

        st.divider()
        h = api_client.health()
        status_icon = "\U0001f7e2" if h.get("status") == "ok" else "\U0001f534"
        st.caption(f"{status_icon} API: {h.get('status', 'unreachable')}")
