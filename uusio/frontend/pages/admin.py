"""Admin panel — admin-only."""

import streamlit as st
from uusio.frontend import api_client

ACTIVE_ICON = "\U0001f7e2"
INACTIVE_ICON = "\U0001f534"


def render() -> None:
    st.title("\U0001f6e1️ Admin")

    if not st.session_state.get("is_admin"):
        st.error("Access denied.")
        return

    tab_overview, tab_customers, tab_pros, tab_registrations = st.tabs([
        "\U0001f4ca Overview",
        "\U0001f3e2 Customers",
        "\U0001f5c4️ PRO Registry",
        "\U0001f517 PRO Registrations",
    ])

    with tab_overview:
        try:
            stats = api_client.admin_get_stats()
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Customers", stats["total_customers"])
            c2.metric("Active", stats["active_customers"])
            c3.metric("Users", stats["total_users"])
            c4.metric("Obligations", stats["total_obligations"])
            c5.metric("Submissions", stats["total_submissions"])
        except Exception as e:
            st.warning(f"Could not load stats: {e}")

    with tab_customers:
        try:
            customers = api_client.admin_list_customers()
        except Exception as e:
            st.error(str(e))
            return

        if not customers:
            st.info("No customers yet.")
        else:
            import pandas as pd
            df = pd.DataFrame(customers)[["name", "country_code", "vat_number", "is_active", "user_count", "created_at"]]
            df.columns = ["Name", "Country", "VAT", "Active", "Users", "Created"]
            df["Created"] = pd.to_datetime(df["Created"]).dt.strftime("%d %b %Y")
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.divider()
            customer_names = {c["name"]: c for c in customers}
            selected_name = st.selectbox("Select customer", list(customer_names.keys()), key="cust_sel")
            selected = customer_names[selected_name]

            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown(f"**ID:** `{selected['id']}`")
                st.markdown(f"**Country:** {selected['country_code']}  |  **VAT:** {selected['vat_number']}")
                new_active = st.toggle("Active", value=selected["is_active"], key="cust_active")
                if new_active != selected["is_active"]:
                    api_client.admin_update_customer(selected["id"], {"is_active": new_active})
                    st.rerun()

            with col_right:
                st.markdown("**Users**")
                try:
                    users = api_client.admin_list_users(selected["id"])
                except Exception:
                    users = []
                for u in users:
                    status_icon = ACTIVE_ICON if u["is_active"] else INACTIVE_ICON
                    with st.expander(f"{u['email']} {status_icon}"):
                        st.markdown(f"**Name:** {u['full_name']}  |  **Admin:** {'Yes' if u['is_admin'] else 'No'}")
                        if st.button("Reset password", key=f"reset_{u['id']}"):
                            result = api_client.admin_reset_password(u["id"])
                            st.success(f"⚠️ Temporary password: `{result['temporary_password']}`  — share securely.")
                        ua, ub = st.columns(2)
                        with ua:
                            label = "Deactivate" if u["is_active"] else "Activate"
                            if st.button(label, key=f"toggle_{u['id']}"):
                                api_client.admin_update_user(u["id"], {"is_active": not u["is_active"]})
                                st.rerun()
                        with ub:
                            if not u["is_admin"]:
                                if st.button("Make admin", key=f"mkadmin_{u['id']}"):
                                    api_client.admin_update_user(u["id"], {"is_admin": True})
                                    st.rerun()

    with tab_pros:
        try:
            pros = api_client.list_pros(active_only=False)
        except Exception as e:
            st.error(str(e))
            pros = []

        if pros:
            import pandas as pd
            df_pros = pd.DataFrame(pros)[["name", "country_code", "category", "pro_key", "contact_name", "contact_email", "is_active"]]
            df_pros.columns = ["Name", "Country", "Category", "Key", "Contact", "Email", "Active"]
            st.dataframe(df_pros, use_container_width=True, hide_index=True)
        else:
            st.info("No PROs in the registry yet.")

        st.divider()
        st.subheader("Add PRO")
        with st.form("new_pro_form"):
            p1, p2, p3 = st.columns(3)
            name = p1.text_input("Name *")
            country = p2.text_input("Country code (FI, SE…) *")
            category = p3.selectbox("Category *", ["Packaging", "Electronics", "Batteries", "Textiles", "Tyres", "Other"])
            pro_key = st.text_input("Key (unique, e.g. rinki-fi) *")
            q1, q2 = st.columns(2)
            website = q1.text_input("Website")
            portal_url = q2.text_input("Portal URL")
            r1, r2, r3 = st.columns(3)
            contact_name = r1.text_input("Contact person")
            contact_email = r2.text_input("Contact email")
            contact_phone = r3.text_input("Contact phone")
            deadline_notes = st.text_area("Reporting schedule notes (visible to customer)")
            notes = st.text_area("Internal notes")
            submitted = st.form_submit_button("Save PRO")

        if submitted:
            if not name or not country or not pro_key:
                st.error("Name, country code and key are required.")
            else:
                try:
                    api_client.create_pro({"name": name, "country_code": country, "category": category,
                                           "pro_key": pro_key, "website": website or None,
                                           "portal_url": portal_url or None, "contact_name": contact_name or None,
                                           "contact_email": contact_email or None, "contact_phone": contact_phone or None,
                                           "reporting_deadline_notes": deadline_notes or None, "notes": notes or None})
                    st.success(f"PRO {name} added.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab_registrations:
        try:
            customers = api_client.admin_list_customers()
            pros = api_client.list_pros(active_only=False)
        except Exception as e:
            st.error(str(e))
            return

        if not customers:
            st.info("No customers.")
            return

        cust_map = {c["name"]: c for c in customers}
        sel_cust_name = st.selectbox("Customer", list(cust_map.keys()), key="reg_cust")
        sel_cust = cust_map[sel_cust_name]

        try:
            regs = api_client.list_registrations(customer_id=sel_cust["id"])
        except Exception:
            regs = []

        if regs:
            for reg in regs:
                pro_name = (reg.get("pro") or {}).get("name", reg["pro_id"])
                country = (reg.get("pro") or {}).get("country_code", "")
                with st.expander(f"{country} — {pro_name}  [{reg['status']}]"):
                    st.markdown(f"**Member number:** {reg.get('registration_number') or '(not set)'}")
                    st.markdown(f"**Contract:** {reg.get('contract_start', '')} – {reg.get('contract_end', '')}")
                    new_status = st.selectbox("Status",
                        ["active", "pending", "expired", "suspended"],
                        index=["active", "pending", "expired", "suspended"].index(reg["status"]),
                        key=f"reg_status_{reg['id']}")
                    sa, sb = st.columns(2)
                    with sa:
                        if st.button("Update status", key=f"upd_reg_{reg['id']}"):
                            api_client.update_registration(reg["id"], {"status": new_status})
                            st.rerun()
                    with sb:
                        if st.button("Remove", key=f"del_reg_{reg['id']}"):
                            api_client.delete_registration(reg["id"])
                            st.rerun()
        else:
            st.info("No PRO registrations for this customer.")

        st.divider()
        st.subheader("Add registration")
        if not pros:
            st.info("Add PROs in the PRO Registry tab first.")
        else:
            pro_map = {f"{p['name']} ({p['country_code']})": p for p in pros}
            with st.form("add_reg_form"):
                sel_pro_label = st.selectbox("PRO", list(pro_map.keys()))
                reg_num = st.text_input("Member number")
                r1, r2 = st.columns(2)
                c_start = r1.date_input("Contract start", value=None)
                c_end = r2.date_input("Contract end", value=None)
                reg_notes = st.text_area("Notes")
                reg_submitted = st.form_submit_button("Add registration")

            if reg_submitted:
                sel_pro = pro_map[sel_pro_label]
                try:
                    api_client.create_registration({"customer_id": sel_cust["id"], "pro_id": sel_pro["id"],
                                                    "registration_number": reg_num or None,
                                                    "contract_start": c_start.isoformat() if c_start else None,
                                                    "contract_end": c_end.isoformat() if c_end else None,
                                                    "notes": reg_notes or None})
                    st.success("Registration added.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
