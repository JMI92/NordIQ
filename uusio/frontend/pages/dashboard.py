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
    "critical": ("\U0001f534", "#3a0a0a", "#ff4444"),
    "warning":  ("\U0001f7e1", "#2a2200", "#F5C430"),
    "ok":       ("\U0001f7e2", "#0a2a0a", "#4caf50"),
}

OBL_ICON = {
    "draft":     ("\U0001f4dd", "Draft"),
    "finalised": ("\U0001f512", "Finalised"),
    "submitted": ("\U00002705", "Submitted"),
    None:        ("⚪", "Not calculated"),
}

SUB_ICON = {"success": "\U0001f7e2", "failed": "\U0001f534", "pending": "\U0001f7e1", "acknowledged": "\U0001f535"}


def render() -> None:
    st.title("\U0001f4ca Dashboard")

    # ── Summary metrics ──────────────────────────────────────────────────────
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

    st.divider()

    # ── Reporting calendar ───────────────────────────────────────────────────
    st.subheader("\U0001f4c5 Reporting Calendar")

    calendar: list = []
    try:
        calendar = api_client.reporting_calendar()
    except Exception:
        pass

    if not calendar:
        st.info(
            "No upcoming reporting deadlines. "
            "Add PRO registrations in the Admin panel and ensure Reporting Deadlines are configured."
        )
    else:
        for item in calendar:
            urgency = item.get("urgency", "ok")
            icon, bg, border = URGENCY.get(urgency, URGENCY["ok"])
            country = item["country_code"]
            flag = FLAGS.get(country, "\U0001f310")
            days = item["days_until_deadline"]
            obl_status = item.get("obligation_status")
            obl_icon, obl_label = OBL_ICON.get(obl_status, OBL_ICON[None])
            days_label = "TODAY" if days == 0 else (f"{days}d" if days > 0 else "OVERDUE")

            title = f"{icon} {flag} **{item['pro_name']}** — {item['product_category']} — due {item['submission_deadline']} ({days_label})"
            with st.expander(title, expanded=(urgency == "critical")):
                col1, col2, col3 = st.columns(3)
                col1.markdown(f"**Reporting period**  \n{item['reporting_period_start']} – {item['reporting_period_end']}")
                col2.markdown(f"**Obligation status**  \n{obl_icon} {obl_label}")
                col3.markdown(f"**Deadline**  \n`{item['submission_deadline']}`")
                if item.get("pro_portal_url"):
                    st.markdown(f"[Open PRO portal ↗]({item['pro_portal_url']})")
                if item.get("notes"):
                    st.caption(item["notes"])
                if obl_status is None:
                    st.warning("Obligation not yet calculated for this period. Go to **Calculations**.")
                elif obl_status == "draft":
                    st.warning("Draft obligation — finalise before submitting.")
                elif obl_status == "finalised":
                    st.info("Obligation finalised — ready to submit.")
                elif obl_status == "submitted":
                    st.success("Submitted!")

    st.divider()

    # ── Active PROs + Recent submissions ─────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("\U0001f5c4️ Active PRO Registrations")
        try:
            regs = [r for r in api_client.my_registrations() if r["status"] == "active"]
            if not regs:
                st.info("No active PRO registrations.")
            else:
                for r in regs:
                    pro = r.get("pro") or {}
                    country = pro.get("country_code", "")
                    flag = FLAGS.get(country, "\U0001f310")
                    reg_num = f"  `{r['registration_number']}`" if r.get("registration_number") else ""
                    st.markdown(f"{flag} **{pro.get('name', '?')}** — {pro.get('category', '')}{reg_num}")
        except Exception:
            st.info("Could not load PRO registrations.")

    with col_right:
        st.subheader("\U0001f4c4 Recent Submissions")
        try:
            reports = api_client.my_reports()[:6]
            if not reports:
                st.info("No submissions yet.")
            else:
                for r in reports:
                    obl = r.get("obligation") or {}
                    s_icon = SUB_ICON.get(r["status"], "⚪")
                    country = obl.get("country_code", "")
                    flag = FLAGS.get(country, "")
                    period = obl.get("period_start", "")[:7] if obl.get("period_start") else ""
                    st.markdown(f"{s_icon} {flag} {r['pro_id']}  —  {period}  —  {r['submitted_at'][:10]}")
        except Exception:
            st.info("Could not load submissions.")
