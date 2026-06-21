"""Billing / invoicing dashboard — admin only."""

import streamlit as st
from uusio.frontend import api_client

STATUS_ICON = {"draft": "\U0001f7e4", "sent": "\U0001f535", "paid": "\U0001f7e2", "overdue": "\U0001f534", "cancelled": "⚪"}


def render() -> None:
    st.title("\U0001f4b3 Billing")

    if not st.session_state.get("is_admin"):
        st.error("Access denied.")
        return

    try:
        invoices = api_client.list_invoices()
    except Exception as e:
        st.error(str(e))
        return

    outstanding = sum(i["amount"] for i in invoices if i["status"] in ("sent", "overdue"))
    overdue_amt = sum(i["amount"] for i in invoices if i["status"] == "overdue")
    paid_count = sum(1 for i in invoices if i["status"] == "paid")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total invoices", len(invoices))
    c2.metric("Outstanding", f"{outstanding:,.2f} €")
    c3.metric("Overdue", f"{overdue_amt:,.2f} €")
    c4.metric("Paid", paid_count)

    st.divider()

    f1, f2 = st.columns(2)
    status_filter = f1.selectbox("Status", ["All", "draft", "sent", "paid", "overdue", "cancelled"])
    search = f2.text_input("Search by invoice number")

    filtered = invoices
    if status_filter != "All":
        filtered = [i for i in filtered if i["status"] == status_filter]
    if search:
        filtered = [i for i in filtered if search.lower() in i["invoice_number"].lower()]

    if not filtered:
        st.info("No invoices match the current filters.")
    else:
        import pandas as pd
        df = pd.DataFrame(filtered)[["invoice_number", "customer_id", "amount", "currency", "status", "due_date", "paid_at", "created_at"]]
        df.columns = ["Invoice #", "Customer ID", "Amount", "Currency", "Status", "Due date", "Paid at", "Created"]
        df["Status"] = df["Status"].apply(lambda s: f"{STATUS_ICON.get(s, '')} {s}")
        df["Created"] = pd.to_datetime(df["Created"]).dt.strftime("%d %b %Y")
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    tab_edit, tab_new = st.tabs(["Edit invoice", "New invoice"])

    with tab_edit:
        if not invoices:
            st.info("No invoices yet.")
        else:
            inv_map = {i["invoice_number"]: i for i in invoices}
            sel_num = st.selectbox("Select invoice", list(inv_map.keys()), key="edit_inv")
            inv = inv_map[sel_num]
            st.markdown(f"**Amount:** {inv['amount']} {inv['currency']}  |  **Status:** {inv['status']}")
            statuses = ["draft", "sent", "paid", "overdue", "cancelled"]
            new_status = st.selectbox("Change status", statuses, index=statuses.index(inv["status"]), key="status_sel")
            new_notes = st.text_area("Notes", value=inv.get("notes") or "", key="notes_area")
            if st.button("Save changes", key="save_inv"):
                api_client.update_invoice(inv["id"], {"status": new_status, "notes": new_notes or None})
                st.success("Saved.")
                st.rerun()

    with tab_new:
        try:
            customers = api_client.admin_list_customers()
        except Exception:
            customers = []
        cust_map = {c["name"]: c["id"] for c in customers}
        with st.form("new_invoice_form"):
            sel_cust = st.selectbox("Customer", list(cust_map.keys()))
            inv_num = st.text_input("Invoice number", placeholder="INV-2026-001")
            amount = st.number_input("Amount (€)", min_value=0.0, step=10.0)
            due_date = st.date_input("Due date")
            notes = st.text_area("Notes")
            form_sub = st.form_submit_button("Create invoice")
        if form_sub:
            if not inv_num:
                st.error("Invoice number is required.")
            else:
                api_client.create_invoice({"customer_id": cust_map[sel_cust], "invoice_number": inv_num,
                                           "amount": amount, "currency": "EUR",
                                           "due_date": due_date.isoformat(), "notes": notes or None})
                st.success(f"Invoice {inv_num} created.")
                st.rerun()
