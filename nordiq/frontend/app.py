"""Streamlit multi-page app entry point — implemented in build steps 7/8/11."""

import streamlit as st

st.set_page_config(
    page_title="NordIQ EPR Compliance",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("NordIQ EPR Compliance Platform")
st.info("Frontend implementation begins in build step 7. API is running at /health.")
