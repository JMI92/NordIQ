"""Login page — matches Uusio brand."""

import os

import streamlit as st

from uusio.frontend import api_client


def render_login() -> None:
    st.markdown("""
    <style>
    .login-container {
        max-width: 400px;
        margin: 80px auto 0;
        padding: 40px;
        background: #142014;
        border: 1px solid #1e3a1e;
        border-radius: 16px;
    }
    .login-logo {
        text-align: center;
        margin-bottom: 8px;
    }
    .login-logo h1 {
        color: #F5C430 !important;
        font-size: 2.5rem !important;
        font-weight: 800 !important;
        letter-spacing: -1px;
    }
    .login-tagline {
        text-align: center;
        color: #8aaa8a;
        font-size: 0.75rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-bottom: 32px;
    }
    </style>
    <div class="login-container">
        <div class="login-logo"><h1>UusiO</h1></div>
        <div class="login-tagline">Simplifying EPR Compliance</div>
    </div>
    """, unsafe_allow_html=True)

    # Centre the form
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login_form"):
            email = st.text_input("Sähköposti", placeholder="you@company.com")
            password = st.text_input("Salasana", type="password")
            submitted = st.form_submit_button("Kirjaudu", use_container_width=True, type="primary")

        if submitted:
            if not email or not password:
                st.error("Anna sähköposti ja salasana.")
                return
            try:
                token_data = api_client.login(email, password)
                st.session_state["token"] = token_data["access_token"]
                api_url = os.getenv("API_URL", "http://localhost:8000")
                st.session_state["api_url"] = api_url
                st.rerun()
            except api_client.APIError as e:
                if e.status_code == 401:
                    st.error("Väärä sähköposti tai salasana.")
                else:
                    st.error(f"Kirjautuminen epäonnistui: {e.detail}")
            except Exception as e:
                st.error(f"Yhteysvirhe: {e}")
