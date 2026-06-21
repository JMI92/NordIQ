"""Products page — list products, upload CSV, inspect weight records."""

from __future__ import annotations

import io
from textwrap import dedent

import streamlit as st

from uusio.frontend import api_client

# Template CSV for download
TEMPLATE_CSV = dedent("""\
    external_product_id,description,product_category,weight_kg,material_type,reporting_period_start,reporting_period_end
    SKU-001,Example Plastic Bottle 0.5L,packaging,0.025,plastic,2024-01-01,2024-12-31
    SKU-002,Example Cardboard Box,packaging,0.150,paper,2024-01-01,2024-12-31
    SKU-003,Example Glass Jar 1L,packaging,0.320,glass,2024-01-01,2024-12-31
""")


def render() -> None:
    st.title("\U0001f4e6 Products")
    st.caption("View and manage your product catalogue and weight records.")

    tab_list, tab_upload = st.tabs(["Product list", "Upload CSV"])

    with tab_list:
        _render_product_list()

    with tab_upload:
        _render_csv_upload()


def _render_product_list() -> None:
    products = api_client.list_products(limit=200)

    if not products:
        st.info("No products found. Upload a CSV to get started.")
        return

    st.caption(f"{len(products)} product(s) — click a row to see weight records")

    # Build display table
    rows = []
    for p in products:
        rows.append({
            "SKU": p["external_product_id"],
            "Description": p["description"],
            "Category": p["product_category"],
            "Weight records": p["weight_count"],
        })

    import pandas as pd  # noqa: PLC0415 — optional import; streamlit env has pandas

    df = pd.DataFrame(rows)
    event = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected = event.selection.get("rows", []) if hasattr(event, "selection") else []
    if selected:
        product = products[selected[0]]
        _render_weight_detail(product)


def _render_weight_detail(product: dict) -> None:
    st.divider()
    st.subheader(f"Weight records — {product['external_product_id']}")
    st.caption(product["description"])

    weights = api_client.list_product_weights(product["id"])
    if not weights:
        st.info("No weight records for this product.")
        return

    import pandas as pd  # noqa: PLC0415

    rows = [
        {
            "Material": w["material_type"],
            "Weight (kg)": w["weight_kg"],
            "Period start": w["reporting_period_start"],
            "Period end": w["reporting_period_end"],
            "Source": w["source"],
        }
        for w in weights
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_csv_upload() -> None:
    st.subheader("Upload product weight CSV")

    with st.expander("\U0001f4cb Required CSV format"):
        st.markdown("""
| Column | Type | Example |
|--------|------|---------|
| `external_product_id` | string | `SKU-001` |
| `description` | string | `Plastic Bottle 0.5L` |
| `product_category` | enum | `packaging` |
| `weight_kg` | decimal | `0.025` |
| `material_type` | enum | `plastic` / `paper` / `glass` / `metal` / `wood` / `other` |
| `reporting_period_start` | date (YYYY-MM-DD) | `2024-01-01` |
| `reporting_period_end` | date (YYYY-MM-DD) | `2024-12-31` |
        """)
        st.download_button(
            "⬇️ Download template CSV",
            data=TEMPLATE_CSV,
            file_name="uusio_products_template.csv",
            mime="text/csv",
        )

    uploaded = st.file_uploader(
        "Choose a CSV file",
        type=["csv"],
        help="Max 200 MB. Rows with errors are skipped; a summary is shown after upload.",
    )

    if uploaded is not None:
        st.caption(f"Selected: **{uploaded.name}** ({uploaded.size:,} bytes)")

        if st.button("Import products", type="primary"):
            with st.spinner("Importing…"):
                result = api_client.upload_products_csv(uploaded.read(), uploaded.name)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("✅ Imported", result["imported"])
            with col2:
                st.metric("❌ Errors", result["errors"])

            if result["errors"] > 0:
                st.warning(f"{result['errors']} row(s) had errors and were skipped.")
                with st.expander("Show error details"):
                    import pandas as pd  # noqa: PLC0415
                    error_rows = [
                        {
                            "Row": e["row"],
                            "Errors": "; ".join(e["errors"]),
                        }
                        for e in result["error_details"]
                    ]
                    st.dataframe(pd.DataFrame(error_rows), use_container_width=True, hide_index=True)

            if result["imported"] > 0:
                st.success(f"Successfully imported {result['imported']} product weight record(s).")
                st.rerun()
