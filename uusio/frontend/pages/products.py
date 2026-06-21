"""Tuotteiden hallinta: tuotekatalogi, materiaalikoostumus ja kuukausittaiset myöntimäärät."""

from __future__ import annotations

import io
from datetime import date

import streamlit as st

from uusio.frontend import api_client

MATERIALS = [
    "plastic", "rigid_plastic", "flexible_plastic", "single_use_plastic",
    "paper", "glass", "metal", "wood", "beverage_carton", "composite",
    "electronics", "battery", "other",
]


def render() -> None:
    st.title("\U0001f4e6 Tuotteet & Volyymit")

    tab_products, tab_volumes, tab_upload = st.tabs([
        "\U0001f4cb Tuotteet & materiaalit",
        "\U0001f4c8 Kuukausittaiset määrät",
        "\U0001f4e4 CSV/Excel-lataus",
    ])

    products = api_client.list_products(limit=1000)
    product_map = {f"{p['external_product_id']} — {p['description']}": p for p in products}

    # ============================================================ Products tab
    with tab_products:
        st.subheader("Tuotekatalogi")

        if not products:
            st.info("Ei tuotteita. Lisää ensin tuotteet API:n kautta tai CSV-latauksella.")
        else:
            import pandas as pd
            df = pd.DataFrame(products)[["external_product_id", "description", "product_category", "unit_of_measure"]].rename(columns={
                "external_product_id": "SKU", "description": "Kuvaus",
                "product_category": "Kategoria", "unit_of_measure": "Yksikkö",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("\U0001f9ea Materiaalikoostumus")
        st.caption("Määritellä kuinka paljon kutakin materiaalia yksi tuoteyksikkö sisältää (kg/yksikkö). Tämä on pysyvä tieto.")

        if not products:
            st.info("Lisää ensin tuotteet.")
        else:
            sel_label = st.selectbox("Valitse tuote", list(product_map.keys()), key="comp_prod")
            sel_prod = product_map[sel_label]

            try:
                compositions = api_client.get_composition(sel_prod["id"])
            except Exception:
                compositions = []

            # Build editable dataframe
            import pandas as pd
            if compositions:
                df_comp = pd.DataFrame(compositions)[["material_type", "is_packaging", "weight_per_unit_kg", "packaging_stream"]]
            else:
                df_comp = pd.DataFrame(columns=["material_type", "is_packaging", "weight_per_unit_kg", "packaging_stream"])

            st.caption("Muokkaa alla olevaa taulukkoa ja tallenna. `is_packaging=True` = pakkausmateriaali, `False` = itse tuote.")

            edited = st.data_editor(
                df_comp,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "material_type": st.column_config.SelectboxColumn("Materiaali", options=MATERIALS, required=True),
                    "is_packaging": st.column_config.CheckboxColumn("Pakkaus?"),
                    "weight_per_unit_kg": st.column_config.NumberColumn("Paino kg/yksikkö", min_value=0.0, format="%.6f"),
                    "packaging_stream": st.column_config.SelectboxColumn("Virta", options=[None, "household", "commercial"]),
                },
                key=f"comp_editor_{sel_prod['id']}",
            )

            if st.button("\U0001f4be Tallenna materiaalikoostumus", key="save_comp"):
                rows = edited.dropna(subset=["material_type", "weight_per_unit_kg"]).to_dict("records")
                payload = [
                    {
                        "material_type": r["material_type"],
                        "is_packaging": bool(r.get("is_packaging", True)),
                        "weight_per_unit_kg": float(r["weight_per_unit_kg"]),
                        "packaging_stream": r.get("packaging_stream") or None,
                    }
                    for r in rows
                ]
                api_client.save_composition(sel_prod["id"], payload)
                st.success("Materiaalikoostumus tallennettu.")
                st.rerun()

    # ========================================================== Volumes tab
    with tab_volumes:
        st.subheader("Kuukausittaiset myöntimäärät")
        st.caption("Syötä montako yksikköä kustakin tuotteesta myytiin kunakin kuukautena. Järjestelmä laskee kokonaispainot automaattisesti.")

        col1, col2 = st.columns(2)
        sel_year = col1.number_input("Vuosi", value=date.today().year, min_value=2020, max_value=2030, step=1)
        sel_month = col2.selectbox("Kuukausi", list(range(1, 13)),
                                    format_func=lambda m: ["Tammikuu","Helmikuu","Maaliskuu","Huhtikuu","Toukokuu","Kesäkuu","Heinäkuu","Elokuu","Syyskuu","Lokakuu","Marraskuu","Joulukuu"][m-1],
                                    index=date.today().month - 2 if date.today().month > 1 else 0)

        try:
            existing_vols = api_client.list_volumes(year=int(sel_year), month=sel_month)
        except Exception:
            existing_vols = []

        vol_by_pid = {v["product_id"]: v["units_sold"] for v in existing_vols}

        if not products:
            st.info("Ei tuotteita.")
        else:
            import pandas as pd
            rows = []
            for p in products:
                rows.append({
                    "SKU": p["external_product_id"],
                    "Kuvaus": p["description"][:50],
                    "Kategoria": p["product_category"],
                    "Yksiköitä myyty": float(vol_by_pid.get(p["id"], 0)),
                    "_id": p["id"],
                })
            df_vol = pd.DataFrame(rows)
            edited_vol = st.data_editor(
                df_vol[["SKU", "Kuvaus", "Kategoria", "Yksiköitä myyty"]],
                num_rows="fixed",
                use_container_width=True,
                column_config={
                    "Yksiköitä myyty": st.column_config.NumberColumn(min_value=0, format="%.2f"),
                },
                key=f"vol_editor_{sel_year}_{sel_month}",
            )

            if st.button(f"\U0001f4be Tallenna {int(sel_year)}-{sel_month:02d} volyymit"):
                saved = 0
                for i, row in edited_vol.iterrows():
                    prod = products[i]
                    units = float(row["Yksiköitä myyty"])
                    if units > 0:
                        api_client.upsert_volume(prod["id"], int(sel_year), sel_month, units)
                        saved += 1
                st.success(f"{saved} tuotteen volyymit tallennettu.")

            st.divider()
            st.subheader("\U0001f9ee Laske materiaalimäärät")
            if st.button(f"Laske kokonaispainot {int(sel_year)}-{sel_month:02d}", type="primary"):
                result = api_client.calculate_from_volumes(int(sel_year), sel_month)
                if result.get("totals"):
                    import pandas as pd
                    df_res = pd.DataFrame(result["totals"]).rename(columns={
                        "product_category": "Kategoria",
                        "material_type": "Materiaali",
                        "is_packaging": "Pakkaus",
                        "total_kg": "Yhteensä (kg)",
                    })
                    df_res["Yhteensä (kg)"] = df_res["Yhteensä (kg)"].round(3)
                    st.dataframe(df_res, use_container_width=True, hide_index=True)
                    st.info("Siirry Calculations-sivulle luodaksesi velvoitteet näistä luvuista.")
                else:
                    st.warning(result.get("message", "Ei tuloksia."))

    # ========================================================== Upload tab
    with tab_upload:
        st.subheader("CSV/Excel-lataus")
        st.markdown("""
        Lataa tiedosto, jossa sarakkeet:
        | sku | year | month | units_sold |
        |-----|------|-------|------------|
        | SKU123 | 2026 | 1 | 5000 |

        Tiedostomuodot: `.csv` tai `.xlsx`
        """)

        uploaded = st.file_uploader("Valitse tiedosto", type=["csv", "xlsx", "xls"], key="vol_upload")
        if uploaded and st.button("Lataa ja käsittele", type="primary"):
            result = api_client.upload_volumes_csv(uploaded.read(), uploaded.name)
            if result:
                st.success(f"✅ Käsitelty: {result.get('processed', 0)} riviä. Ohitettu (tuntematon SKU): {result.get('skipped_unknown_sku', 0)}.")
            st.rerun()

        st.divider()
        st.subheader("Lataa malli")
        if products:
            import pandas as pd
            template = pd.DataFrame([
                {"sku": p["external_product_id"], "year": date.today().year, "month": date.today().month, "units_sold": 0}
                for p in products
            ])
            buf = io.BytesIO()
            template.to_csv(buf, index=False)
            st.download_button(
                "\U0001f4e5 Lataa CSV-malli",
                data=buf.getvalue(),
                file_name=f"volyymit_malli_{date.today().year}_{date.today().month:02d}.csv",
                mime="text/csv",
            )
