"""Admin panel — visible only to is_admin users."""

import streamlit as st

from uusio.frontend import api_client


def render() -> None:
    st.title("\U0001f6e1️ Admin")

    if not st.session_state.get("is_admin"):
        st.error("Ei käyttöoikeutta.")
        return

    tab_overview, tab_customers, tab_pros, tab_registrations = st.tabs([
        "\U0001f4ca Yhteenveto",
        "\U0001f3e2 Asiakkaat",
        "\U0001f5c4️ PRO-rekisteri",
        "\U0001f517 PRO-rekisteröinnit",
    ])

    # ================================================================ Overview
    with tab_overview:
        try:
            stats = api_client.admin_get_stats()
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Asiakkaat", stats["total_customers"])
            c2.metric("Aktiiviset", stats["active_customers"])
            c3.metric("Käyttäjät", stats["total_users"])
            c4.metric("Velvoitteet", stats["total_obligations"])
            c5.metric("Lähetykset", stats["total_submissions"])
        except Exception as e:
            st.warning(f"Tilastoja ei saatu: {e}")

    # ============================================================== Customers
    with tab_customers:
        try:
            customers = api_client.admin_list_customers()
        except Exception as e:
            st.error(str(e))
            return

        if not customers:
            st.info("Ei asiakkaita.")
        else:
            import pandas as pd
            df = pd.DataFrame(customers)[[
                "name", "country_code", "vat_number", "is_active", "user_count", "created_at"
            ]].rename(columns={
                "name": "Nimi", "country_code": "Maa", "vat_number": "ALV-tunnus",
                "is_active": "Aktiivinen", "user_count": "Käyttäjiä", "created_at": "Luotu",
            })
            df["Luotu"] = pd.to_datetime(df["Luotu"]).dt.strftime("%d.%m.%Y")
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.divider()
            customer_names = {c["name"]: c for c in customers}
            selected_name = st.selectbox("Valitse asiakas", list(customer_names.keys()), key="cust_sel")
            selected = customer_names[selected_name]

            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown(f"**ID:** `{selected['id']}`")
                new_active = st.toggle("Aktiivinen", value=selected["is_active"], key="cust_active")
                if new_active != selected["is_active"]:
                    api_client.admin_update_customer(selected["id"], {"is_active": new_active})
                    st.rerun()

            with col_right:
                st.markdown("**Käyttäjät**")
                try:
                    users = api_client.admin_list_users(selected["id"])
                except Exception:
                    users = []
                for u in users:
                    with st.expander(f"{u['email']} {'\U0001f7e2' if u['is_active'] else '\U0001f534'}"):
                        st.markdown(f"**Nimi:** {u['full_name']}")
                        if st.button("Reset salasana", key=f"reset_{u['id']}"):
                            result = api_client.admin_reset_password(u["id"])
                            st.success(f"⚠️ Väliaikainen salasana: `{result['temporary_password']}`")
                        ua, ub = st.columns(2)
                        with ua:
                            if st.button("Aktivoi/Poista", key=f"toggle_{u['id']}"):
                                api_client.admin_update_user(u["id"], {"is_active": not u["is_active"]})
                                st.rerun()
                        with ub:
                            if not u["is_admin"]:
                                if st.button("Tee admin", key=f"mkadmin_{u['id']}"):
                                    api_client.admin_update_user(u["id"], {"is_admin": True})
                                    st.rerun()

    # ============================================================ PRO Registry
    with tab_pros:
        pros = api_client.list_pros(active_only=False)

        if pros:
            import pandas as pd
            df_pros = pd.DataFrame(pros)[[
                "name", "country_code", "category", "pro_key",
                "contact_name", "contact_email", "is_active"
            ]].rename(columns={
                "name": "Nimi", "country_code": "Maa", "category": "Kategoria",
                "pro_key": "Avain", "contact_name": "Yhteyshenkilö",
                "contact_email": "Sähköposti", "is_active": "Aktiivinen",
            })
            st.dataframe(df_pros, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Lisää / muokkaa PRO")

        with st.form("new_pro_form"):
            p1, p2, p3 = st.columns(3)
            name = p1.text_input("Nimi *")
            country = p2.text_input("Maakoodi (FI, SE...)  *")
            category = p3.selectbox("Kategoria *", ["Packaging", "Electronics", "Batteries", "Textiles", "Tyres", "Other"])
            pro_key = st.text_input("Avain (uniikki, esim. rinki-fi) *")
            q1, q2 = st.columns(2)
            website = q1.text_input("Verkkosivusto")
            portal_url = q2.text_input("Portaali URL")
            r1, r2, r3 = st.columns(3)
            contact_name = r1.text_input("Yhteyshenkilö")
            contact_email = r2.text_input("Sähköposti")
            contact_phone = r3.text_input("Puhelin")
            deadline_notes = st.text_area("Raportointiaikataulu (näkyy asiakkaalle)")
            notes = st.text_area("Sisäiset muistiinpanot")
            submitted = st.form_submit_button("Tallenna PRO")

        if submitted:
            if not name or not country or not pro_key:
                st.error("Nimi, maakoodi ja avain ovat pakollisia.")
            else:
                api_client.create_pro({
                    "name": name, "country_code": country, "category": category,
                    "pro_key": pro_key, "website": website or None,
                    "portal_url": portal_url or None,
                    "contact_name": contact_name or None,
                    "contact_email": contact_email or None,
                    "contact_phone": contact_phone or None,
                    "reporting_deadline_notes": deadline_notes or None,
                    "notes": notes or None,
                })
                st.success(f"PRO {name} lisätty.")
                st.rerun()

    # ======================================================= PRO Registrations
    with tab_registrations:
        try:
            customers = api_client.admin_list_customers()
            pros = api_client.list_pros(active_only=False)
        except Exception as e:
            st.error(str(e))
            return

        cust_map = {c["name"]: c for c in customers}
        sel_cust_name = st.selectbox("Asiakas", list(cust_map.keys()), key="reg_cust")
        sel_cust = cust_map[sel_cust_name]

        try:
            regs = api_client.list_registrations(customer_id=sel_cust["id"])
        except Exception:
            regs = []

        if regs:
            for reg in regs:
                pro_name = reg.get("pro", {}).get("name", reg["pro_id"])
                country = reg.get("pro", {}).get("country_code", "")
                with st.expander(f"{country} — {pro_name} [{reg['status']}]"):
                    st.markdown(f"**Jäsennumero:** {reg.get('registration_number') or '(ei asetettu)'}")
                    st.markdown(f"**Sopimus:** {reg.get('contract_start','')} – {reg.get('contract_end','')}")
                    new_status = st.selectbox("Status", ["active", "pending", "expired", "suspended"],
                                              index=["active", "pending", "expired", "suspended"].index(reg["status"]),
                                              key=f"reg_status_{reg['id']}")
                    if st.button("Päivitä status", key=f"upd_reg_{reg['id']}"):
                        api_client.update_registration(reg["id"], {"status": new_status})
                        st.rerun()
                    if st.button("Poista", key=f"del_reg_{reg['id']}"):
                        api_client.delete_registration(reg["id"])
                        st.rerun()
        else:
            st.info("Ei PRO-rekisteröintejä tälle asiakkaalle.")

        st.divider()
        st.subheader("Lisää rekisteröinti")
        pro_map = {f"{p['name']} ({p['country_code']})": p for p in pros}
        with st.form("add_reg_form"):
            sel_pro_label = st.selectbox("PRO", list(pro_map.keys()))
            reg_num = st.text_input("Jäsennumero")
            r1, r2 = st.columns(2)
            c_start = r1.date_input("Sopimus alkaen", value=None)
            c_end = r2.date_input("Sopimus päättyy", value=None)
            reg_notes = st.text_area("Muistiinpanot")
            reg_submitted = st.form_submit_button("Lisää")

        if reg_submitted:
            sel_pro = pro_map[sel_pro_label]
            api_client.create_registration({
                "customer_id": sel_cust["id"],
                "pro_id": sel_pro["id"],
                "registration_number": reg_num or None,
                "contract_start": c_start.isoformat() if c_start else None,
                "contract_end": c_end.isoformat() if c_end else None,
                "notes": reg_notes or None,
            })
            st.success("Rekisteröinti lisätty.")
            st.rerun()
