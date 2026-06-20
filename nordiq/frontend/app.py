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
    from nordiq.frontend.pages.login import render_login
    render_login()
    st.stop()

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

PAGES = {
    "\U0001f4ca Dashboard":      "nordiq.frontend.pages.dashboard",
    "\U0001f50c Data Sources":   "nordiq.frontend.pages.data_sources",
    "\U0001f4e6 Products":       "nordiq.frontend.pages.products",
    "\U0001f9ee Calculations":   "nordiq.frontend.pages.calculations",
    "\U0001f4e4 Submissions":    "nordiq.frontend.pages.submissions",
}

with st.sidebar:
    st.title("\U0001f331 Uusio")
    st.caption("EPR Compliance Platform")
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
