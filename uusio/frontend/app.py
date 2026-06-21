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

/* ── Hide Streamlit's auto-generated page navigation ── */
section[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stSidebarNavItems"] { display: none !important; }
[data-testid="stSidebarNavSeparator"] { display: none !important; }

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background-color: #0d1f0d;
  border-right: 1px solid #1a301a;
}
[data-testid="stSidebar"] h1 {
  color: #F5C430 !important;
  font-size: 1.5rem !important;
  font-weight: 700 !important;
  letter-spacing: -0.5px;
}

/* Nav radio — hide the default circle indicator */
[data-testid="stSidebar"] [data-testid="stRadio"] > div > label > div:first-child {
  display: none !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] > div > label {
  display: flex !important;
  align-items: center !important;
  padding: 9px 14px !important;
  margin: 1px 0 !important;
  border-radius: 8px !important;
  border-left: 2px solid transparent !important;
  cursor: pointer !important;
  transition: all 0.15s ease !important;
  color: #6a8a6a !important;
  font-size: 0.875rem !important;
  font-weight: 400 !important;
  letter-spacing: 0.1px !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] > div > label:hover {
  background: rgba(245,196,48,0.07) !important;
  color: #d4c090 !important;
  border-left-color: rgba(245,196,48,0.25) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] > div > label:has(input:checked) {
  background: rgba(245,196,48,0.10) !important;
  color: #F5C430 !important;
  border-left-color: #F5C430 !important;
  font-weight: 600 !important;
}

[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
  color: #4a6a4a !important;
  font-size: 0.75rem !important;
}
[data-testid="stSidebar"] .stButton > button {
  background: transparent;
  border: 1px solid #1e361e;
  color: #4a6a4a;
  width: 100%;
  border-radius: 8px;
  font-size: 0.8rem;
  letter-spacing: 0.3px;
  transition: all 0.15s;
}
[data-testid="stSidebar"] .stButton > button:hover {
  border-color: #F5C430;
  color: #F5C430;
  transform: none;
}

/* ── Typography ──────────────────────────────────────────────────── */
h1 { color: #F5C430 !important; font-weight: 700; letter-spacing: -0.5px; }
h2 { color: #e8f0e8 !important; font-weight: 600; }
h3 { color: #c8dcc8 !important; font-weight: 600; }

/* ── Metric cards ───────────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: #0f1f0f;
  border: 1px solid #1a301a;
  border-radius: 12px;
  padding: 20px 24px;
  transition: border-color 0.2s;
}
[data-testid="stMetric"]:hover { border-color: rgba(245,196,48,0.3); }
[data-testid="stMetricLabel"] {
  color: #4a6a4a !important;
  font-size: 0.72rem !important;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}
[data-testid="stMetricValue"] { color: #F5C430 !important; font-weight: 700; font-size: 2rem !important; }

/* ── Buttons ──────────────────────────────────────────────────────── */
.stButton > button {
  background-color: #F5C430;
  color: #0A1A0A;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  letter-spacing: 0.2px;
  transition: background 0.2s, transform 0.1s;
}
.stButton > button:hover { background-color: #f0b800; transform: translateY(-1px); }
.stButton > button[kind="secondary"] {
  background-color: transparent;
  border: 1px solid #1e3a1e;
  color: #8aaa8a;
}
.stButton > button[kind="secondary"]:hover { border-color: #F5C430; color: #F5C430; }

/* ── Expanders ────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  background: #0f1f0f;
  border: 1px solid #1a301a;
  border-radius: 10px;
  margin-bottom: 4px;
}
[data-testid="stExpander"] summary { color: #c8dcc8; font-weight: 500; }
[data-testid="stExpander"] summary:hover { color: #F5C430; }

/* ── Tabs ─────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-testid="stTab"] {
  color: #4a6a4a;
  border-bottom: 2px solid transparent;
  font-weight: 500;
}
[data-testid="stTabs"] [aria-selected="true"] {
  color: #F5C430 !important;
  border-bottom: 2px solid #F5C430 !important;
}

/* ── Inputs ───────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] > div > div {
  background-color: #0f1f0f !important;
  border: 1px solid #1a301a !important;
  border-radius: 8px !important;
  color: #e8f0e8 !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: rgba(245,196,48,0.5) !important;
  box-shadow: 0 0 0 2px rgba(245,196,48,0.08) !important;
}

/* ── Misc ─────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] { border: 1px solid #1a301a; border-radius: 10px; overflow: hidden; }
[data-testid="stForm"] { background: #0f1f0f; border: 1px solid #1a301a; border-radius: 12px; padding: 20px; }
hr { border-color: #1a301a !important; }
.stCaption, [data-testid="stCaptionContainer"] { color: #4a6a4a !important; }
code { background: #1a301a !important; color: #F5C430 !important; border-radius: 4px; padding: 1px 6px; }
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0A1A0A; }
::-webkit-scrollbar-thumb { background: #1a301a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #F5C430; }
[data-testid="stAlert"] { border-radius: 10px !important; border-left-width: 3px !important; }
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
    "Dashboard":     "uusio.frontend.pages.dashboard",
    "My Portal":     "uusio.frontend.pages.portal",
    "Regulations":   "uusio.frontend.pages.regulations",
    "Data Sources":  "uusio.frontend.pages.data_sources",
    "Products":      "uusio.frontend.pages.products",
    "Calculations":  "uusio.frontend.pages.calculations",
    "Submissions":   "uusio.frontend.pages.submissions",
}

if st.session_state.get("is_admin"):
    PAGES["Admin"]   = "uusio.frontend.pages.admin"
    PAGES["Billing"] = "uusio.frontend.pages.billing"

with st.sidebar:
    st.markdown(
        "<h1 style='margin-bottom:0;padding-bottom:0;margin-top:8px'>"
        "Uusi<span style='color:#F5C430'>O</span></h1>"
        "<p style='color:#3a5a3a;font-size:0.68rem;margin-top:4px;letter-spacing:1.8px;"
        "text-transform:uppercase'>Simplifying EPR Compliance</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if st.session_state.get("user_email"):
        st.caption(st.session_state["user_email"])
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    selection = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

import importlib  # noqa: E402
module = importlib.import_module(PAGES[selection])
module.render()
