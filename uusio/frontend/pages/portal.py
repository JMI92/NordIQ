"""Customer self-service portal — PRO registrations, report archive, documents."""

import streamlit as st
from uusio.frontend import api_client

FLAGS = {
    "FI": "\U0001f1eb\U0001f1ee", "SE": "\U0001f1f8\U0001f1ea",
    "NO": "\U0001f1f3\U0001f1f4", "DK": "\U0001f1e9\U0001f1f0",
    "DE": "\U0001f1e9\U0001f1ea", "FR": "\U0001f1eb\U0001f1f7",
    "NL": "\U0001f1f3\U0001f1f1", "BE": "\U0001f1e7\U0001f1ea",
    "EU": "\U0001f1ea\U0001f1fa",
}
STATUS_ICON = {"active": "\U0001f7e2", "pending": "\U0001f7e1", "expired": "\U0001f534", "suspended": "⚪"}
SUB_ICON = {"success": "\U0001f7e2", "pending": "\U0001f7e1", "failed": "\U0001f534", "acknowledged": "\U0001f535"}
FOLDER_LABELS = {"contracts": "\U0001f4c4 Contracts", "reports": "\U0001f4ca Reports",
                 "invoices": "\U0001f4b3 Invoices", "audits": "\U0001f50d Audits"}


def render() -> None:
    st.title("\U0001f3e2 My Portal")

    summary: dict = {}
    try:
        summary = api_client.portal_summary()
    except Exception:
        pass

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active PROs",   summary.get("active_pro_count", 0))
    c2.metric("Countries",     len(summary.get("active_countries", [])))
    c3.metric("Obligations",   summary.get("total_obligations", 0))
    c4.metric("Reports sent",  summary.get("successful_submissions", 0))

    if summary.get("active_countries"):
        flags = "  ".join(FLAGS.get(c, c) for c in summary["active_countries"])
        st.caption(f"Active markets: {flags}")

    st.divider()

    tab_pros, tab_reports, tab_files = st.tabs([
        "\U0001f4cb PRO Registrations",
        "\U0001f4c4 Report Archive",
        "\U0001f4c1 Documents",
    ])

    with tab_pros:
        try:
            regs = api_client.my_registrations()
        except Exception as e:
            st.error(str(e))
            regs = []
        if not regs:
            st.info("No PRO registrations yet. Contact your Uusio account manager.")
        else:
            for reg in regs:
                pro = reg.get("pro") or {}
                country = pro.get("country_code", "")
                flag = FLAGS.get(country, "\U0001f310")
                icon = STATUS_ICON.get(reg["status"], "")
                with st.expander(f"{flag} **{pro.get('name', '?')}** — {pro.get('category', '')} {icon}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Country:** {country}")
                        st.markdown(f"**Status:** {reg['status']}")
                        if reg.get("registration_number"):
                            st.markdown(f"**Member #:** `{reg['registration_number']}`")
                        if reg.get("contract_start"):
                            st.markdown(f"**Contract:** {reg['contract_start']} – {reg.get('contract_end', '')}")
                    with col2:
                        if pro.get("portal_url"):
                            st.markdown(f"[Open PRO portal ↗]({pro['portal_url']})")
                        if pro.get("contact_email"):
                            st.markdown(f"**Contact:** {pro.get('contact_name', '')} / {pro['contact_email']}")
                        if pro.get("reporting_deadline_notes"):
                            st.info(pro["reporting_deadline_notes"])

    with tab_reports:
        try:
            reports = api_client.my_reports()
        except Exception as e:
            st.error(str(e))
            reports = []
        if not reports:
            st.info("No reports yet.")
        else:
            import pandas as pd
            rows = []
            for r in reports:
                obl = r.get("obligation") or {}
                rows.append({
                    "Date": r["submitted_at"][:10],
                    "PRO": r["pro_id"],
                    "Country": obl.get("country_code", ""),
                    "Category": obl.get("product_category", ""),
                    "Period": f"{obl.get('period_start','')[:7]} – {obl.get('period_end','')[:7]}" if obl.get("period_start") else "",
                    "Weight (kg)": obl.get("total_weight_kg"),
                    "Fee": f"{obl.get('fee_amount','')} {obl.get('currency','')}" if obl.get("fee_amount") else "",
                    "Status": f"{SUB_ICON.get(r['status'],'')} {r['status']}",
                    "_id": r["id"], "_url": r.get("download_url"),
                })
            df = pd.DataFrame(rows)
            st.dataframe(df[[c for c in df.columns if not c.startswith("_")]], use_container_width=True, hide_index=True)
            st.divider()
            st.subheader("Download report")
            rep_labels = {f"{r['submitted_at'][:10]} — {r['pro_id']} [{r['status']}]": r for r in reports}
            sel = st.selectbox("Select report", list(rep_labels.keys()))
            sel_rep = rep_labels[sel]
            if sel_rep.get("download_url"):
                st.link_button("\U0001f4e5 Download PDF / report", sel_rep["download_url"])
            else:
                st.info("No report file available for this submission.")

    with tab_files:
        folder = st.selectbox("Folder", ["contracts", "reports", "invoices", "audits"],
                               format_func=lambda x: FOLDER_LABELS.get(x, x))
        try:
            files = api_client.list_my_files(folder)
        except Exception as e:
            st.error(str(e))
            files = []
        if not files:
            st.info("This folder is empty.")
        else:
            for f in files:
                col_a, col_b, col_c = st.columns([4, 1, 1])
                col_a.markdown(f"\U0001f4ce {f['filename']}")
                col_b.caption(f"{f['size'] // 1024} KB" if f["size"] >= 1024 else f"{f['size']} B")
                if f.get("download_url"):
                    col_c.link_button("Download", f["download_url"])
        st.divider()
        st.subheader("Upload file")
        uploaded = st.file_uploader("Choose file", key=f"upload_{folder}")
        if uploaded and st.button("Upload"):
            result = api_client.upload_my_file(uploaded.read(), uploaded.name, folder)
            st.success(f"Uploaded: {result.get('filename')}")
            st.rerun()
