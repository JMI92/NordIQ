"""Data Sources page — list, add, test, delete customer data sources."""

from __future__ import annotations

import json

import streamlit as st

from nordiq.frontend import api_client


def render() -> None:
    st.title("\U0001f50c Data Sources")
    st.caption("Manage the connections NordIQ uses to import your product weight data.")

    # -----------------------------------------------------------------------
    # List existing data sources
    # -----------------------------------------------------------------------
    sources = api_client.list_data_sources()

    if sources:
        st.subheader(f"Configured sources ({len(sources)})")
        for ds in sources:
            _render_data_source_card(ds)
    else:
        st.info("No data sources configured yet. Add one below.")

    st.divider()

    # -----------------------------------------------------------------------
    # Add new data source
    # -----------------------------------------------------------------------
    with st.expander("➕ Add new data source", expanded=not sources):
        _render_add_form()


def _render_data_source_card(ds: dict) -> None:
    status_icon = "\U0001f7e2" if ds["is_active"] else "⚪"
    type_icon = {"csv": "\U0001f4c4", "snowflake": "❄️", "api": "\U0001f310"}.get(ds["source_type"], "\U0001f50c")

    with st.container(border=True):
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            st.markdown(f"{status_icon} {type_icon} **{ds['name']}**")
            st.caption(f"Type: `{ds['source_type']}` · Last sync: {ds.get('last_synced_at') or 'never'}")
            if ds.get("table_name"):
                st.caption(f"Table: `{ds['table_name']}`")
        with col2:
            if st.button("Test", key=f"test_{ds['id']}", use_container_width=True):
                with st.spinner("Testing connection…"):
                    result = api_client.test_data_source(ds["id"])
                if result.get("ok"):
                    st.success(result.get("detail", "OK"))
                else:
                    st.error(result.get("detail", "Failed"))
        with col3:
            if st.button("Delete", key=f"del_{ds['id']}", use_container_width=True, type="secondary"):
                api_client.delete_data_source(ds["id"])
                st.success(f"Deleted '{ds['name']}'")  
                st.rerun()


def _render_add_form() -> None:
    source_type = st.selectbox("Source type", ["csv", "snowflake"], key="new_ds_type")
    name = st.text_input("Name", placeholder="e.g. FI Warehouse CSV", key="new_ds_name")

    st.markdown("**Field mapping** — map your column names to NordIQ's canonical fields")
    default_mapping = {
        "external_product_id": "external_product_id",
        "description": "description",
        "product_category": "product_category",
        "weight_kg": "weight_kg",
        "material_type": "material_type",
        "reporting_period_start": "reporting_period_start",
        "reporting_period_end": "reporting_period_end",
    }
    mapping_text = st.text_area(
        "Field mapping (JSON)",
        value=json.dumps(default_mapping, indent=2),
        height=200,
        key="new_ds_mapping",
    )

    conn_config: dict = {}

    if source_type == "csv":
        file_path = st.text_input(
            "CSV file path (on the server)",
            placeholder="/data/products_2024.csv",
            key="new_ds_csv_path",
        )
        conn_config = {"file_path": file_path}
    else:
        st.markdown("**Snowflake connection**")
        c1, c2 = st.columns(2)
        with c1:
            account = st.text_input("Account", placeholder="xy12345.eu-west-1", key="sf_account")
            user = st.text_input("User", key="sf_user")
            warehouse = st.text_input("Warehouse", key="sf_warehouse")
        with c2:
            password = st.text_input("Password", type="password", key="sf_password")
            database = st.text_input("Database", key="sf_database")
            schema = st.text_input("Schema", value="PUBLIC", key="sf_schema")
        table_name = st.text_input("Table / view name", key="sf_table")
        conn_config = {
            "account": account, "user": user, "password": password,
            "warehouse": warehouse, "database": database, "schema": schema,
        }

    if st.button("Save data source", type="primary", key="save_ds"):
        if not name:
            st.warning("Please enter a name.")
            return
        try:
            mapping = json.loads(mapping_text)
        except json.JSONDecodeError:
            st.error("Field mapping must be valid JSON.")
            return

        payload: dict = {
            "name": name,
            "source_type": source_type,
            "connection_config": conn_config,
            "field_mapping": mapping,
        }
        if source_type == "snowflake":
            payload["table_name"] = table_name  # type: ignore[possibly-undefined]

        api_client.create_data_source(payload)
        st.success(f"Data source '{name}' created!")
        st.rerun()
