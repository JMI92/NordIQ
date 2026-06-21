"""Customer self-service portal — PRO registrations + reporting archive + documents."""

import streamlit as st

from uusio.frontend import api_client

STATUS_ICON = {
    "active": "\U0001f7e2",
    "pending": "\U0001f7e1",
    "expired": "\U0001f534",
    "suspended": "⚪",
}

SUB_STATUS_ICON = {
    "success": "\U0001f7e2",
    "pending": "\U0001f7e1",
    "failed": "\U0001f534",
    "acknowledged": "\U0001f535",
}

FLAGS = {
    "FI": "\U0001f1eb\U0001f1ee", "SE": "\U0001f1f8\U0001f1ea",
    "NO": "\U0001f1f3\U0001f1f4", "DK": "\U0001f1e9\U0001f1f0",
    "DE": "\U0001f1e9\U0001f1ea", "FR": "\U0001f1eb\U0001f1f7",
    "NL": "\U0001f1f3\U0001f1f1", "BE": "\U0001f1e7\U0001f1ea",
}


def render() -> None:
    st.title("\U0001f3e2 Oma portaali")

    try:
        summary = api_client.portal_summary()
    except Exception as e:
        st.error(f"Yhteenveto ei saatavilla: {e}")
        summary = {}

    # ----- Summary metrics -----
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aktiiviset PRO:t", summary.get("active_pro_count", 0))
    c2.metric("Maat", len(summary.get("active_countries", [])))
    c3.metric("Velvoitteet yhteensä", summary.get("total_obligations", 0))
    c4.metric("Onnistuneet lähetykset", summary.get("successful_submissions", 0))

    if summary.get("active_countries"):
        flags = " ".join(FLAGS.get(c, c) for c in summary["active_countries"])
        st.caption(f"Aktiiviset maat: {flags}")

    st.divider()

    tab_pros, tab_reports, tab_files = st.tabs([
        "\U0001f4cb PRO-rekisteröinnit",
        "\U0001f4c4 Raportointiarkisto",
        "\U0001f4c1 Dokumentit",
    ])

    # ------------------------------------------------------------------ PROs
    with tab_pros:
        try:
            regs = api_client.my_registrations()
        except Exception as e:
            st.error(str(e))
            regs = []

        if not regs:
            st.info("Ei PRO-rekisteröintejä. Ota yhteyttä Uusio-tiimiisi.")
        else:
            for reg in regs:
                pro = reg.get("pro") or {}
                country = pro.get("country_code", "")
                flag = FLAGS.get(country, "\U0001f310")
                icon = STATUS_ICON.get(reg["status"], "")
                label = f"{flag} {pro.get('name', '?')} — {pro.get('category', '')} {icon}"
                with st.expander(label):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Maa:** {country}")
                        st.markdown(f"**Status:** {reg['status']}")
                        if reg.get("registration_number"):
                            st.markdown(f"**Jäsennumero:** `{reg['registration_number']}`")
                        if reg.get("contract_start"):
                            st.markdown(f"**Sopimus alkaen:** {reg['contract_start']}")
                        if reg.get("contract_end"):
                            st.markdown(f"**Sopimus päättyy:** {reg['contract_end']}")
                    with col2:
                        if pro.get("portal_url"):
                            st.markdown(f"[Avaa PRO-portaali]({pro['portal_url']})")
                        if pro.get("contact_email"):
                            st.markdown(f"**Yhteyshenkilö:** {pro.get('contact_name', '')} / {pro['contact_email']}")
                        if pro.get("reporting_deadline_notes"):
                            st.info(pro["reporting_deadline_notes"])
                    if reg.get("notes"):
                        st.caption(reg["notes"])

    # ---------------------------------------------------------- Report archive
    with tab_reports:
        try:
            reports = api_client.my_reports()
        except Exception as e:
            st.error(str(e))
            reports = []

        if not reports:
            st.info("Ei raportteja vielä.")
        else:
            import pandas as pd
            rows = []
            for r in reports:
                obl = r.get("obligation") or {}
                rows.append({
                    "Pvm": r["submitted_at"][:10],
                    "PRO": r["pro_id"],
                    "Maa": obl.get("country_code", ""),
                    "Kategoria": obl.get("product_category", ""),
                    "Jakso": f"{obl.get('period_start','')[:7]} – {obl.get('period_end','')[:7]}" if obl.get("period_start") else "",
                    "Paino (kg)": obl.get("total_weight_kg"),
                    "Maksu": f"{obl.get('fee_amount','')} {obl.get('currency','')}".strip() if obl.get("fee_amount") else "",
                    "Status": f"{SUB_STATUS_ICON.get(r['status'],'')} {r['status']}",
                    "_id": r["id"],
                    "_url": r.get("download_url"),
                })
            df = pd.DataFrame(rows)
            display_cols = [c for c in df.columns if not c.startswith("_")]
            st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Lataa raportti")
            report_labels = {f"{r['submitted_at'][:10]} — {r['pro_id']} [{r['status']}]": r for r in reports}
            sel = st.selectbox("Valitse raportti", list(report_labels.keys()))
            selected_report = report_labels[sel]
            if selected_report.get("download_url"):
                st.link_button("\U0001f4e5 Lataa PDF/raportti", selected_report["download_url"])
            else:
                st.info("Raporttitiedosto ei saatavilla tälle lähetykselle.")

    # ---------------------------------------------------------- Documents
    with tab_files:
        folder = st.selectbox(
            "Kansio",
            ["contracts", "reports", "invoices", "audits"],
            format_func=lambda x: {"contracts": "\U0001f4c4 Sopimukset", "reports": "\U0001f4ca Raportit", "invoices": "\U0001f4b3 Laskut", "audits": "\U0001f50d Auditoinnit"}.get(x, x),
        )
        try:
            files = api_client.list_my_files(folder)
        except Exception as e:
            st.error(str(e))
            files = []

        if not files:
            st.info("Kansio on tyhjä.")
        else:
            for f in files:
                col_a, col_b, col_c = st.columns([4, 1, 1])
                col_a.markdown(f"\U0001f4ce {f['filename']}")
                col_b.caption(f"{f['size'] // 1024} KB" if f['size'] >= 1024 else f"{f['size']} B")
                if f.get("download_url"):
                    col_c.link_button("Lataa", f["download_url"])

        st.divider()
        st.subheader("Lataa tiedosto")
        uploaded = st.file_uploader("Valitse tiedosto", key=f"upload_{folder}")
        if uploaded and st.button("Lataa palvelimelle"):
            result = api_client.upload_my_file(uploaded.read(), uploaded.name, folder)
            st.success(f"Tallennettu: {result.get('filename')}")
            st.rerun()
