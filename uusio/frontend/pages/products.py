"""Products, material composition and monthly sales volumes."""

from __future__ import annotations

import io
from datetime import date

import streamlit as st
from uusio.frontend import api_client

MATERIAL_ICONS = {
    "plastic":             "\U0001f9f4",
    "rigid_plastic":       "\U0001f4e6",
    "flexible_plastic":    "\U0001f6cd️",
    "single_use_plastic":  "\U0001f964",
    "paper":               "\U0001f4f0",
    "glass":               "\U0001fab9",
    "metal":               "⚙️",
    "wood":                "\U0001fab5",
    "beverage_carton":     "\U0001f9c3",
    "composite":           "♻️",
    "electronics":         "\U0001f4bb",
    "battery":             "\U0001f50b",
    "other":               "\U0001f4e6",
}

MATERIALS = list(MATERIAL_ICONS.keys())
MONTH_NAMES = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]


def mat_label(m: str) -> str:
    return f"{MATERIAL_ICONS.get(m, '\U0001f4e6')} {m.replace('_', ' ').title()}"


def render() -> None:
    st.title("\U0001f4e6 Products & Volumes")

    tab_products, tab_volumes, tab_upload = st.tabs([
        "\U0001f4cb Products & Materials",
        "\U0001f4c8 Monthly Volumes",
        "\U0001f4e4 CSV / Excel Upload",
    ])

    products = api_client.list_products(limit=1000)
    product_map = {f"{p['external_product_id']} — {p['description']}": p for p in products}

    # ============================================================ Products
    with tab_products:
        st.subheader("Product catalogue")
        if not products:
            st.info("No products yet. Add them via API or CSV upload.")
        else:
            import pandas as pd
            df = pd.DataFrame(products)[["external_product_id", "description", "product_category", "unit_of_measure"]]
            df.columns = ["SKU", "Description", "Category", "Unit"]
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("\U0001f9ea Material composition")
        st.caption("Define how much of each material a single unit contains (kg / unit). This is stable master data.")

        if not products:
            st.info("Add products first.")
        else:
            sel_label = st.selectbox("Select product", list(product_map.keys()), key="comp_prod")
            sel_prod = product_map[sel_label]

            try:
                compositions = api_client.get_composition(sel_prod["id"])
            except Exception:
                compositions = []

            import pandas as pd
            if compositions:
                df_comp = pd.DataFrame(compositions)[["material_type", "is_packaging", "weight_per_unit_kg", "packaging_stream"]]
            else:
                df_comp = pd.DataFrame(columns=["material_type", "is_packaging", "weight_per_unit_kg", "packaging_stream"])

            st.caption("Edit the table and save. `is_packaging = True` = packaging material, `False` = the product itself.")
            edited = st.data_editor(
                df_comp,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "material_type": st.column_config.SelectboxColumn(
                        "Material",
                        options=MATERIALS,
                        required=True,
                        help="Select waste stream",
                    ),
                    "is_packaging": st.column_config.CheckboxColumn("Packaging?"),
                    "weight_per_unit_kg": st.column_config.NumberColumn("kg / unit", min_value=0.0, format="%.6f"),
                    "packaging_stream": st.column_config.SelectboxColumn("Stream", options=[None, "household", "commercial"]),
                },
                key=f"comp_editor_{sel_prod['id']}",
            )

            # Show icon legend
            with st.expander("Material icons legend"):
                cols = st.columns(4)
                for i, (mat, icon) in enumerate(MATERIAL_ICONS.items()):
                    cols[i % 4].markdown(f"{icon} {mat.replace('_', ' ').title()}")

            if st.button("\U0001f4be Save material composition", key="save_comp"):
                rows = edited.dropna(subset=["material_type", "weight_per_unit_kg"]).to_dict("records")
                payload = [{"material_type": r["material_type"], "is_packaging": bool(r.get("is_packaging", True)),
                            "weight_per_unit_kg": float(r["weight_per_unit_kg"]),
                            "packaging_stream": r.get("packaging_stream") or None} for r in rows]
                api_client.save_composition(sel_prod["id"], payload)
                st.success("Composition saved.")
                st.rerun()

    # ============================================================ Volumes
    with tab_volumes:
        st.subheader("Monthly sales volumes")
        st.caption("Enter units sold per product per month. The system calculates total material weights automatically.")

        col1, col2 = st.columns(2)
        sel_year = col1.number_input("Year", value=date.today().year, min_value=2020, max_value=2030, step=1)
        sel_month = col2.selectbox("Month", list(range(1, 13)),
                                    format_func=lambda m: MONTH_NAMES[m - 1],
                                    index=date.today().month - 2 if date.today().month > 1 else 0)

        try:
            existing_vols = api_client.list_volumes(year=int(sel_year), month=sel_month)
        except Exception:
            existing_vols = []

        vol_by_pid = {v["product_id"]: v["units_sold"] for v in existing_vols}

        if not products:
            st.info("No products.")
        else:
            import pandas as pd
            rows = []
            for p in products:
                rows.append({
                    "SKU": p["external_product_id"],
                    "Description": p["description"][:50],
                    "Category": p["product_category"],
                    "Units sold": float(vol_by_pid.get(p["id"], 0)),
                    "_id": p["id"],
                })
            df_vol = pd.DataFrame(rows)
            edited_vol = st.data_editor(
                df_vol[["SKU", "Description", "Category", "Units sold"]],
                num_rows="fixed",
                use_container_width=True,
                column_config={"Units sold": st.column_config.NumberColumn(min_value=0, format="%.2f")},
                key=f"vol_editor_{sel_year}_{sel_month}",
            )

            if st.button(f"\U0001f4be Save {int(sel_year)}-{sel_month:02d} volumes"):
                saved = 0
                for i, row in edited_vol.iterrows():
                    prod = products[i]
                    units = float(row["Units sold"])
                    if units > 0:
                        api_client.upsert_volume(prod["id"], int(sel_year), sel_month, units)
                        saved += 1
                st.success(f"{saved} product(s) saved.")

            st.divider()
            st.subheader("\U0001f9ee Calculate material totals")
            if st.button(f"Calculate totals for {int(sel_year)}-{sel_month:02d}", type="primary"):
                result = api_client.calculate_from_volumes(int(sel_year), sel_month)
                if result.get("totals"):
                    import pandas as pd
                    df_res = pd.DataFrame(result["totals"])
                    df_res["material"] = df_res["material_type"].apply(mat_label)
                    df_res = df_res.rename(columns={"product_category": "Category", "is_packaging": "Packaging", "total_kg": "Total (kg)"})
                    df_res["Total (kg)"] = df_res["Total (kg)"].round(3)
                    st.dataframe(df_res[["Category", "material", "Packaging", "Total (kg)"]], use_container_width=True, hide_index=True)
                    st.info("Go to **Calculations** to create obligations from these numbers.")
                else:
                    st.warning(result.get("message", "No results."))

    # ============================================================ Upload
    with tab_upload:
        st.subheader("CSV / Excel volume upload")
        st.markdown("""
        Upload a file with these columns:

        | sku | year | month | units_sold |
        |-----|------|-------|------------|
        | SKU123 | 2026 | 6 | 5000 |

        Supported formats: `.csv`, `.xlsx`
        """)

        uploaded = st.file_uploader("Choose file", type=["csv", "xlsx", "xls"], key="vol_upload")
        if uploaded and st.button("Upload & process", type="primary"):
            result = api_client.upload_volumes_csv(uploaded.read(), uploaded.name)
            if result:
                st.success(f"✅ Processed: {result.get('processed', 0)} rows. Skipped (unknown SKU): {result.get('skipped_unknown_sku', 0)}.")
            st.rerun()

        st.divider()
        st.subheader("Download template")
        if products:
            import pandas as pd
            template = pd.DataFrame([
                {"sku": p["external_product_id"], "year": date.today().year, "month": date.today().month, "units_sold": 0}
                for p in products
            ])
            buf = io.BytesIO()
            template.to_csv(buf, index=False)
            st.download_button(
                "\U0001f4e5 Download CSV template",
                data=buf.getvalue(),
                file_name=f"volumes_template_{date.today().year}_{date.today().month:02d}.csv",
                mime="text/csv",
            )
        else:
            st.info("Add products first to generate a template.")
