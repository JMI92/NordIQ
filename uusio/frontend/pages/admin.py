"""Admin panel — visible only to is_admin users."""

import streamlit as st

from uusio.frontend import api_client


def render() -> None:
    st.title("\U0001f6e1️ Admin")

    if not st.session_state.get("is_admin"):
        st.error("Ei käyttöoikeutta.")
        return

    # ----- Stats row -----
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

    st.divider()

    # ----- Customer list -----
    st.subheader("Asiakkaat")
    try:
        customers = api_client.admin_list_customers()
    except Exception as e:
        st.error(f"Asiakkaita ei saatu: {e}")
        return

    if not customers:
        st.info("Ei asiakkaita.")
        return

    # Build display table
    import pandas as pd
    df = pd.DataFrame(customers)[[
        "name", "country_code", "vat_number", "is_active", "user_count", "created_at"
    ]].rename(columns={
        "name": "Nimi",
        "country_code": "Maa",
        "vat_number": "ALV-tunnus",
        "is_active": "Aktiivinen",
        "user_count": "Käyttäjiä",
        "created_at": "Luotu",
    })
    df["Luotu"] = pd.to_datetime(df["Luotu"]).dt.strftime("%d.%m.%Y")

    st.dataframe(df, use_container_width=True, hide_index=True)

    # ----- Customer detail / actions -----
    st.divider()
    st.subheader("Asiakkaan hallinta")

    customer_names = {c["name"]: c for c in customers}
    selected_name = st.selectbox("Valitse asiakas", list(customer_names.keys()))
    selected = customer_names[selected_name]

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown(f"**ID:** `{selected['id']}`")
        st.markdown(f"**Maa:** {selected['country_code']}")
        st.markdown(f"**ALV:** {selected['vat_number']}")
        new_active = st.toggle("Aktiivinen", value=selected["is_active"], key="cust_active")
        if new_active != selected["is_active"]:
            api_client.admin_update_customer(selected["id"], {"is_active": new_active})
            st.success("Tila päivitetty.")
            st.rerun()

    with col_right:
        st.markdown("**Käyttäjät**")
        try:
            users = api_client.admin_list_users(selected["id"])
        except Exception:
            users = []

        if not users:
            st.info("Ei käyttäjiä.")
        else:
            for u in users:
                with st.expander(f"{u['email']} {'\U0001f7e2' if u['is_active'] else '\U0001f534'}"):
                    st.markdown(f"**Nimi:** {u['full_name']}")
                    st.markdown(f"**Admin:** {'Kyllä' if u['is_admin'] else 'Ei'}")
                    st.markdown(f"**Luotu:** {u['created_at'][:10]}")
                    if st.button("Reset salasana", key=f"reset_{u['id']}"):
                        result = api_client.admin_reset_password(u["id"])
                        st.success(f"⚠️ Väliaikainen salasana: `{result['temporary_password']}`")
                        st.caption("Jaa tämä käyttäjälle turvallisesti.")
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
