"""Uusio Streamlit multi-page app entry point."""

import streamlit as st

st.set_page_config(
    page_title="Uusio — EPR Compliance",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background-color: #0A1A0A; }
[data-testid="stSidebar"] { background-color: #0d1f0d; border-right: 1px solid #1e3a1e; }
[data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] label { color: #d4e8d4 !important; }
[data-testid="stSidebar"] h1 { color: #F5C430 !important; font-size: 1.6rem !important; font-weight: 700 !important; letter-spacing: -0.5px; }
h1 { color: #F5C430 !important; font-weight: 700; letter-spacing: -0.5px; }
h2 { color: #e8f0e8 !important; font-weight: 600; }
h3 { color: #c8dcc8 !important; font-weight: 600; }
[data-testid="stMetric"] { background: #142014; border: 1px solid #1e3a1e; border-radius: 12px; padding: 16px 20px; }
[data-testid="stMetricLabel"] { color: #8aaa8a !important; font-size: 0.78rem !important; text-transform: uppercase; letter-spacing: 0.5px; }
[data-testid="stMetricValue"] { color: #F5C430 !important; font-weight: 700; }
.stButton > button { background-color: #F5C430; color: #0A1A0A; border: none; border-radius: 8px; font-weight: 600; transition: background 0.2s, transform 0.1s; }
.stButton > button:hover { background-color: #f0b800; transform: translateY(-1px); }
.stButton > button[kind="secondary"] { background-color: transparent; border: 1px solid #F5C430; color: #F5C430; }
[data-testid="stExpander"] { background: #142014; border: 1px solid #1e3a1e; border-radius: 10px; margin-bottom: 6px; }
[data-testid="stExpander"] summary { color: #e8f0e8; font-weight: 500; }
[data-testid="stExpander"] summary:hover { color: #F5C430; }
[data-testid="stTabs"] [data-testid="stTab"] { color: #8aaa8a; border-bottom: 2px solid transparent; }
[data-testid="stTabs"] [aria-selected="true"] { color: #F5C430 !important; border-bottom: 2px solid #F5C430 !important; }
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stTextArea"] textarea { background-color: #142014 !important; border: 1px solid #2a4a2a !important; border-radius: 8px !important; color: #e8f0e8 !important; }
[data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus { border-color: #F5C430 !important; box-shadow: 0 0 0 2px rgba(245,196,48,0.15) !important; }
[data-testid="stDataFrame"] { border: 1px solid #1e3a1e; border-radius: 10px; overflow: hidden; }
[data-testid="stForm"] { background: #142014; border: 1px solid #1e3a1e; border-radius: 12px; padding: 20px; }
hr { border-color: #1e3a1e !important; }
.stCaption, [data-testid="stCaptionContainer"] { color: #8aaa8a !important; }
code { background: #1e3a1e !important; color: #F5C430 !important; border-radius: 4px; padding: 1px 6px; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0A1A0A; }
::-webkit-scrollbar-thumb { background: #2a4a2a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #F5C430; }
[data-testid="stSidebar"] .stButton > button { background: transparent; border: 1px solid #2a4a2a; color: #8aaa8a; width: 100%; }
[data-testid="stSidebar"] .stButton > button:hover { border-color: #F5C430; color: #F5C430; transform: none; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { color: #9ab89a !important; font-size: 0.9rem; letter-spacing: 0.2px; padding: 4px 0; transition: color 0.15s; }
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { color: #F5C430 !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"] + div label,
[data-testid="stSidebar"] [data-testid="stRadio"] input:checked ~ label { color: #F5C430 !important; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

if "token" not in st.session_state:
    from uusio.frontend.pages.login import render_login
    render_login()
    st.stop()

if "is_admin" not in st.session_state:
    from uusio.frontend import api_client
    try:
        me = api_client.get_me()
        st.session_state["is_admin"] = me.get("is_admin", False)
        st.session_state["user_email"] = me.get("email", "")
    except Exception:
        st.session_state["is_admin"] = False
        st.session_state["user_email"] = ""

PAGES: dict[str, str] = {
    "◈  Dashboard":       "uusio.frontend.pages.dashboard",
    "◉  My Portal":       "uusio.frontend.pages.portal",
    "≡  Regulations":     "uusio.frontend.pages.regulations",
    "⇌  Data Sources":    "uusio.frontend.pages.data_sources",
    "⬡  Products":        "uusio.frontend.pages.products",
    "∑  Calculations":    "uusio.frontend.pages.calculations",
    "↑  Submissions":     "uusio.frontend.pages.submissions",
}

if st.session_state.get("is_admin"):
    PAGES["⊞  Admin"]   = "uusio.frontend.pages.admin"
    PAGES["◧  Billing"] = "uusio.frontend.pages.billing"

with st.sidebar:
    st.markdown(
        "<h1 style='margin-bottom:0;padding-bottom:0'>UusiO</h1>"
        "<p style='color:#8aaa8a;font-size:0.72rem;margin-top:2px;letter-spacing:1.5px'>SIMPLIFYING EPR COMPLIANCE</p>",
        unsafe_allow_html=True,
    )
    if st.session_state.get("user_email"):
        st.caption(f"\U0001f464 {st.session_state['user_email']}")
    st.divider()
    selection = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    if st.button("Log out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

import importlib  # noqa: E402
module = importlib.import_module(PAGES[selection])
module.render()
