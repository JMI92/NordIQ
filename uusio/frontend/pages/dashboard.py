"""Raportointikaienteri + tuoteportaali — asiakkaan päänäkymä."""

from __future__ import annotations

import streamlit as st

from uusio.frontend import api_client

FLAGS = {
    "FI": "\U0001f1eb\U0001f1ee", "SE": "\U0001f1f8\U0001f1ea",
    "NO": "\U0001f1f3\U0001f1f4", "DK": "\U0001f1e9\U0001f1f0",
    "DE": "\U0001f1e9\U0001f1ea", "FR": "\U0001f1eb\U0001f1f7",
    "NL": "\U0001f1f3\U0001f1f1", "BE": "\U0001f1e7\U0001f1ea",
    "PL": "\U0001f1f5\U0001f1f1", "EU": "\U0001f1ea\U0001f1fa",
}

URGENCY_CONFIG = {
    "critical": ("\U0001f534", "error"),
    "warning":  ("\U0001f7e1", "warning"),
    "ok":       ("\U0001f7e2", "success"),
}

OBL_STATUS_ICON = {
    "draft":     "\U0001f4dd",
    "finalised": "\U0001f512",
    "submitted": "\U00002705",
    None:        "⚪",
}


def render() -> None:
    st.title("\U0001f4ca Dashboard")

    # ---------- Summary metrics ----------
    try:
        summary = api_client.portal_summary()
    except Exception:
        summary = {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aktiiviset PRO:t", summary.get("active_pro_count", 0))
    c2.metric("Maat", len(summary.get("active_countries", [])))
    c3.metric("Velvoitteet", summary.get("total_obligations", 0))
    c4.metric("Onnist. lähetykset", summary.get("successful_submissions", 0))

    if summary.get("active_countries"):
        flags = " ".join(FLAGS.get(c, c) for c in summary["active_countries"])
        st.caption(f"Aktiiviset maat: {flags}")

    st.divider()

    # ---------- Reporting calendar ----------
    st.subheader("\U0001f4c5 Raportointiaikataulu")
    try:
        calendar = api_client.reporting_calendar()
    except Exception as e:
        st.warning(f"Kalenteria ei saatu: {e}")
        calendar = []

    if not calendar:
        st.info("Ei tulevia raportointipäiväyksiä. Lisää PRO-rekisteröinnit Admin-osiosta ja varmista että ReportingDeadlines on täytetty.")
    else:
        for item in calendar:
            urgency = item.get("urgency", "ok")
            icon, alert_type = URGENCY_CONFIG.get(urgency, ("\U0001f7e2", "success"))
            country = item["country_code"]
            flag = FLAGS.get(country, "\U0001f310")
            days = item["days_until_deadline"]
            obl_status = item.get("obligation_status")
            obl_icon = OBL_STATUS_ICON.get(obl_status, OBL_STATUS_ICON[None])

            days_label = f"{days} pv" if days > 0 else "TÄNÄÄN"
            title = f"{icon} {flag} **{item['pro_name']}** — {item['product_category']} — deadline {item['submission_deadline']} ({days_label})"

            with st.expander(title, expanded=(urgency == "critical")):
                col1, col2, col3 = st.columns(3)
                col1.markdown(f"**Raportointijakso**  \n{item['reporting_period_start']} – {item['reporting_period_end']}")
                col2.markdown(f"**Velvoite**  \n{obl_icon} {obl_status or 'ei laskettu'}")
                col3.markdown(f"**Deadline**  \n{item['submission_deadline']}")

                if item.get("pro_portal_url"):
                    st.markdown(f"[Avaa PRO-portaali ↗]({item['pro_portal_url']})")
                if item.get("notes"):
                    st.caption(item["notes"])

                if obl_status is None:
                    st.warning("⚠️ Velvoitetta ei ole vielä laskettu tälle jaksolle. Siirry Calculations-sivulle.")
                elif obl_status == "draft":
                    st.warning("📝 Velvoite on luonnoksena — viimeistele ennen lähettämistä.")
                elif obl_status == "finalised":
                    st.info("🔒 Velvoite on viimeistelty — valmis lähetettäväksi.")
                elif obl_status == "submitted":
                    st.success("✅ Lähetetty!")

    st.divider()

    # ---------- Active PRO overview ----------
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("\U0001f5c4️ Aktiiviset PRO-rekisteröinnit")
        try:
            regs = api_client.my_registrations()
        except Exception:
            regs = []

        if not regs:
            st.info("Ei aktiivisia rekisteröintejä.")
        else:
            active = [r for r in regs if r["status"] == "active"]
            for r in active:
                pro = r.get("pro") or {}
                country = pro.get("country_code", "")
                flag = FLAGS.get(country, "\U0001f310")
                reg_num = f" `{r['registration_number']}`" if r.get("registration_number") else ""
                st.markdown(f"{flag} **{pro.get('name', '?')}** — {pro.get('category', '')}{reg_num}")

    with col_right:
        st.subheader("\U0001f4c4 Viimeisimmät lähetykset")
        try:
            reports = api_client.my_reports()[:5]
        except Exception:
            reports = []

        if not reports:
            st.info("Ei lähetyksiä vielä.")
        else:
            for r in reports:
                obl = r.get("obligation") or {}
                status_icon = {"success": "\U0001f7e2", "failed": "\U0001f534", "pending": "\U0001f7e1"}.get(r["status"], "⚪")
                country = obl.get("country_code", "")
                flag = FLAGS.get(country, "")
                st.markdown(f"{status_icon} {flag} {r['pro_id']} — {r['submitted_at'][:10]}")
