"""Billing / invoicing dashboard — admin only."""

import streamlit as st

from uusio.frontend import api_client

STATUS_COLORS = {
    "draft":     "\U0001f7e4",
    "sent":      "\U0001f535",
    "paid":      "\U0001f7e2",
    "overdue":   "\U0001f534",
    "cancelled": "⚪",
}


def render() -> None:
    st.title("\U0001f4b3 Laskutus")

    if not st.session_state.get("is_admin"):
        st.error("Ei käyttöoikeutta.")
        return

    invoices = api_client.list_invoices()

    # ----- Summary metrics -----
    total = sum(i["amount"] for i in invoices)
    outstanding = sum(i["amount"] for i in invoices if i["status"] in ("sent", "overdue"))
    overdue = sum(i["amount"] for i in invoices if i["status"] == "overdue")
    paid_count = sum(1 for i in invoices if i["status"] == "paid")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Laskuja yhteensä", len(invoices))
    c2.metric("Avoin saldo", f"{outstanding:,.2f} €")
    c3.metric("Erääntynyt", f"{overdue:,.2f} €")
    c4.metric("Maksettu", paid_count)

    st.divider()

    # ----- Filters -----
    col_f1, col_f2 = st.columns(2)
    status_filter = col_f1.selectbox("Status", ["Käikki", "draft", "sent", "paid", "overdue", "cancelled"])
    search = col_f2.text_input("Hae laskunumerolla tai asiakkaalla")

    filtered = invoices
    if status_filter != "Käikki":
        filtered = [i for i in filtered if i["status"] == status_filter]
    if search:
        s = search.lower()
        filtered = [i for i in filtered if s in i["invoice_number"].lower() or s in i["customer_id"].lower()]

    # ----- Invoice table -----
    if not filtered:
        st.info("Ei laskuja valituilla suodattimilla.")
    else:
        import pandas as pd
        df = pd.DataFrame(filtered)[[
            "invoice_number", "customer_id", "amount", "currency", "status", "due_date", "paid_at", "created_at"
        ]].rename(columns={
            "invoice_number": "Laskunro",
            "customer_id": "Asiakas ID",
            "amount": "Summa",
            "currency": "Valuutta",
            "status": "Status",
            "due_date": "Eräpäivä",
            "paid_at": "Maksettu",
            "created_at": "Luotu",
        })
        df["Status"] = df["Status"].apply(lambda s: f"{STATUS_COLORS.get(s, '')} {s}")
        df["Luotu"] = pd.to_datetime(df["Luotu"]).dt.strftime("%d.%m.%Y")
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # ----- Actions on existing invoice -----
    tab_edit, tab_new = st.tabs(["Muokkaa laskua", "Uusi lasku"])

    with tab_edit:
        if not invoices:
            st.info("Ei laskuja.")
        else:
            inv_numbers = {i["invoice_number"]: i for i in invoices}
            sel_num = st.selectbox("Valitse lasku", list(inv_numbers.keys()), key="edit_inv")
            inv = inv_numbers[sel_num]
            st.markdown(f"**Summa:** {inv['amount']} {inv['currency']}  |  **Status:** {inv['status']}")
            new_status = st.selectbox("Muuta status", ["draft", "sent", "paid", "overdue", "cancelled"], index=["draft", "sent", "paid", "overdue", "cancelled"].index(inv["status"]), key="status_sel")
            new_notes = st.text_area("Muistiinpanot", value=inv.get("notes") or "", key="notes_area")
            if st.button("Tallenna muutokset", key="save_inv"):
                api_client.update_invoice(inv["id"], {"status": new_status, "notes": new_notes or None})
                st.success("Tallennettu.")
                st.rerun()

    with tab_new:
        customers = api_client.admin_list_customers()
        cust_map = {c["name"]: c["id"] for c in customers}
        with st.form("new_invoice_form"):
            sel_cust = st.selectbox("Asiakas", list(cust_map.keys()))
            inv_num = st.text_input("Laskunumero", placeholder="INV-2026-001")
            amount = st.number_input("Summa (€)", min_value=0.0, step=1.0)
            due_date = st.date_input("Eräpäivä")
            notes = st.text_area("Muistiinpanot")
            submitted = st.form_submit_button("Luo lasku")
        if submitted:
            if not inv_num:
                st.error("Laskunumero on pakollinen.")
            else:
                api_client.create_invoice({
                    "customer_id": cust_map[sel_cust],
                    "invoice_number": inv_num,
                    "amount": amount,
                    "currency": "EUR",
                    "due_date": due_date.isoformat(),
                    "notes": notes or None,
                })
                st.success(f"Lasku {inv_num} luotu.")
                st.rerun()
