"""Dashboard — reporting calendar + compliance overview."""

from __future__ import annotations

import streamlit as st
from uusio.frontend import api_client

FLAGS = {
    "FI": "\U0001f1eb\U0001f1ee", "SE": "\U0001f1f8\U0001f1ea",
    "NO": "\U0001f1f3\U0001f1f4", "DK": "\U0001f1e9\U0001f1f0",
    "DE": "\U0001f1e9\U0001f1ea", "FR": "\U0001f1eb\U0001f1f7",
    "NL": "\U0001f1f3\U0001f1f1", "BE": "\U0001f1e7\U0001f1ea",
    "PL": "\U0001f1f5\U0001f1f1", "EU": "\U0001f1ea\U0001f1fa",
    "AT": "\U0001f1e6\U0001f1f9", "ES": "\U0001f1ea\U0001f1f8",
    "IT": "\U0001f1ee\U0001f1f9",
}

URGENCY = {
    "critical": ("#ff4444", "#2a0808"),
    "warning":  ("#F5C430", "#221a00"),
    "ok":       ("#4caf50", "#0a1f0a"),
}

OBL_STATUS = {
    "draft":     ("○", "Draft",       "#6a8a6a"),
    "finalised": ("◆", "Finalised",   "#F5C430"),
    "submitted": ("✓", "Submitted",   "#4caf50"),
    None:        ("—", "Not started",  "#3a5a3a"),
}

SUB_STATUS = {
    "success":      ("✓", "#4caf50"),
    "failed":       ("✗", "#ff4444"),
    "pending":      ("○", "#F5C430"),
    "acknowledged": ("◆", "#6aabff"),
}

# Inline SVG icons — gold stroke, no fill
_CAL_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="#F5C430" stroke-width="1.5" '
    'width="22" height="22" style="flex-shrink:0">'
    '<rect x="3" y="4" width="18" height="18" rx="2"/>'
    '<path d="M16 2v4M8 2v4M3 10h18"/>'
    '</svg>'
)
_PRO_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="#F5C430" stroke-width="1.5" '
    'width="22" height="22" style="flex-shrink:0">'
    '<circle cx="12" cy="8" r="4"/>'
    '<path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>'
    '</svg>'
)
_SUB_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="#F5C430" stroke-width="1.5" '
    'width="22" height="22" style="flex-shrink:0">'
    '<path d="M12 19V5M5 12l7-7 7 7"/>'
    '</svg>'
)


def _section(svg_icon: str, title: str) -> None:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin:28px 0 14px">'
        f'{svg_icon}'
        f'<span style="color:#e8f0e8;font-size:1.15rem;font-weight:600">{title}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render() -> None:
    st.markdown(
        '<h1 style="color:#F5C430;font-weight:700;letter-spacing:-0.5px;margin-bottom:4px">Dashboard</h1>'
        '<p style="color:#3a5a3a;margin-top:0;font-size:0.85rem">Your EPR compliance overview</p>',
        unsafe_allow_html=True,
    )

    # ── Summary metrics ─────────────────────────────────────────────────────
    summary: dict = {}
    try:
        summary = api_client.portal_summary()
    except Exception:
        pass

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active PROs",        summary.get("active_pro_count", 0))
    c2.metric("Countries covered",  len(summary.get("active_countries", [])))
    c3.metric("Total obligations",  summary.get("total_obligations", 0))
    c4.metric("Successful reports", summary.get("successful_submissions", 0))

    if summary.get("active_countries"):
        flags = "  ".join(FLAGS.get(c, c) for c in summary["active_countries"])
        st.caption(f"Active markets: {flags}")

    st.markdown("<hr style='border-color:#1a301a;margin:24px 0'>", unsafe_allow_html=True)

    # ── Reporting calendar ──────────────────────────────────────────────────
    _section(_CAL_ICON, "Reporting Calendar")

    calendar: list = []
    try:
        calendar = api_client.reporting_calendar()
    except Exception:
        pass

    if not calendar:
        st.markdown(
            '<div style="background:#0f1f0f;border:1px solid #1a301a;border-radius:10px;'
            'padding:20px 24px;color:#4a6a4a;font-size:0.875rem">'
            'No upcoming reporting deadlines. Add PRO registrations in Admin and configure Reporting Deadlines.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        for item in calendar:
            urgency = item.get("urgency", "ok")
            accent, bg = URGENCY.get(urgency, URGENCY["ok"])
            country = item["country_code"]
            flag = FLAGS.get(country, "\U0001f310")
            days = item["days_until_deadline"]
            obl_status = item.get("obligation_status")
            obl_sym, obl_label, obl_color = OBL_STATUS.get(obl_status, OBL_STATUS[None])
            if days == 0:
                days_label = "TODAY"
            elif days > 0:
                days_label = f"{days}d"
            else:
                days_label = "OVERDUE"

            title = f"{flag} **{item['pro_name']}** — {item['product_category']} — {item['submission_deadline']} ({days_label})"
            with st.expander(title, expanded=(urgency == "critical")):
                st.markdown(
                    f'<div style="display:flex;gap:8px;align-items:center;margin-bottom:12px">'
                    f'<span style="background:{bg};color:{accent};border:1px solid {accent}40;'
                    f'border-radius:6px;padding:2px 10px;font-size:0.75rem;font-weight:600;letter-spacing:0.5px">'
                    f'{urgency.upper()}</span>'
                    f'<span style="color:#3a5a3a;font-size:0.8rem">{days_label} remaining</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                col1, col2, col3 = st.columns(3)
                col1.markdown(f"**Period**  \n{item['reporting_period_start']} – {item['reporting_period_end']}")
                col2.markdown(
                    f"**Obligation**  \n"
                    f"<span style='color:{obl_color}'>{obl_sym} {obl_label}</span>",
                    unsafe_allow_html=True,
                )
                col3.markdown(f"**Deadline**  \n`{item['submission_deadline']}`")
                if item.get("pro_portal_url"):
                    st.markdown(
                        f'<a href="{item["pro_portal_url"]}" target="_blank" '
                        f'style="color:#F5C430;font-size:0.875rem;text-decoration:none">'
                        f'Open PRO portal ↗</a>',
                        unsafe_allow_html=True,
                    )
                if obl_status is None:
                    st.warning("Obligation not yet calculated. Go to **Calculations**.")
                elif obl_status == "draft":
                    st.warning("Draft obligation — finalise before submitting.")
                elif obl_status == "finalised":
                    st.info("Obligation finalised — ready to submit.")
                elif obl_status == "submitted":
                    st.success("Submitted.")

    st.markdown("<hr style='border-color:#1a301a;margin:24px 0'>", unsafe_allow_html=True)

    # ── Active PROs + Recent submissions ────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        _section(_PRO_ICON, "Active PRO Registrations")
        try:
            regs = [r for r in api_client.my_registrations() if r["status"] == "active"]
            if not regs:
                st.caption("No active PRO registrations.")
            else:
                for r in regs:
                    pro = r.get("pro") or {}
                    country = pro.get("country_code", "")
                    flag = FLAGS.get(country, "\U0001f310")
                    reg_num = r.get("registration_number", "")
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;'
                        f'padding:10px 14px;border-radius:8px;border:1px solid #1a301a;'
                        f'margin-bottom:4px;background:#0f1f0f">'
                        f'<span style="font-size:1.1rem">{flag}</span>'
                        f'<div>'
                        f'<div style="color:#e8f0e8;font-size:0.875rem;font-weight:500">{pro.get("name", "?")}</div>'
                        f'<div style="color:#4a6a4a;font-size:0.75rem">{pro.get("category", "")}'
                        f'{ " · " + reg_num if reg_num else ""}</div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
        except Exception:
            st.caption("Could not load PRO registrations.")

    with col_right:
        _section(_SUB_ICON, "Recent Submissions")
        try:
            reports = api_client.my_reports()[:6]
            if not reports:
                st.caption("No submissions yet.")
            else:
                for r in reports:
                    obl = r.get("obligation") or {}
                    sym, color = SUB_STATUS.get(r["status"], ("—", "#3a5a3a"))
                    country = obl.get("country_code", "")
                    flag = FLAGS.get(country, "")
                    period = obl.get("period_start", "")[:7] if obl.get("period_start") else ""
                    submitted = r.get("submitted_at", "")[:10]
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;'
                        f'padding:10px 14px;border-radius:8px;border:1px solid #1a301a;'
                        f'margin-bottom:4px;background:#0f1f0f">'
                        f'<span style="color:{color};font-size:1rem;font-weight:600;width:16px;text-align:center">{sym}</span>'
                        f'<div>'
                        f'<div style="color:#e8f0e8;font-size:0.875rem">{flag} {r.get("pro_id", "")} — {period}</div>'
                        f'<div style="color:#4a6a4a;font-size:0.75rem">{submitted}</div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
        except Exception:
            st.caption("Could not load submissions.")
