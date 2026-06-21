"""Uusio Streamlit multi-page app entry point."""

import streamlit as st

st.set_page_config(
    page_title="Uusio EPR Compliance",
    page_icon="\U0001f331",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------

if "token" not in st.session_state:
    from uusio.frontend.pages.login import render_login
    render_login()
    st.stop()

# Fetch current user info once per session
if "is_admin" not in st.session_state:
    from uusio.frontend import api_client
    try:
        me = api_client.get_me()
        st.session_state["is_admin"] = me.get("is_admin", False)
        st.session_state["user_email"] = me.get("email", "")
    except Exception:
        st.session_state["is_admin"] = False
        st.session_state["user_email"] = ""

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

PAGES: dict[str, str] = {
    "\U0001f4ca Dashboard":         "uusio.frontend.pages.dashboard",
    "\U0001f3e2 Oma portaali":      "uusio.frontend.pages.portal",
    "\U0001f4d6 Säännöskirjasto":  "uusio.frontend.pages.regulations",
    "\U0001f50c Data Sources":      "uusio.frontend.pages.data_sources",
    "\U0001f4e6 Products":          "uusio.frontend.pages.products",
    "\U0001f9ee Calculations":      "uusio.frontend.pages.calculations",
    "\U0001f4e4 Submissions":       "uusio.frontend.pages.submissions",
}

if st.session_state.get("is_admin"):
    PAGES["\U0001f6e1️ Admin"] = "uusio.frontend.pages.admin"
    PAGES["\U0001f4b3 Billing"]     = "uusio.frontend.pages.billing"

with st.sidebar:
    st.title("\U0001f331 Uusio")
    st.caption("EPR Compliance Platform")
    if st.session_state.get("user_email"):
        st.caption(f"\U0001f464 {st.session_state['user_email']}")
    st.divider()
    selection = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    if st.button("Log out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ---------------------------------------------------------------------------
# Render selected page
# ---------------------------------------------------------------------------
import importlib  # noqa: E402

module = importlib.import_module(PAGES[selection])
module.render()
