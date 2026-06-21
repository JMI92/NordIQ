"""Calculations page — run EPR calculations and manage obligations."""

from __future__ import annotations

from datetime import date

import streamlit as st

from uusio.frontend import api_client

COUNTRIES = ["FI", "SE", "NO", "DK"]
CATEGORIES = ["packaging", "weee", "batteries", "vehicles", "other"]

STATUS_COLOUR = {
    "draft": "🟡",
    "finalised": "🟢",
    "submitted": "🔵",
}


def render() -> None:
    st.title("🧨 Calculations")
    st.caption("Run EPR fee calculations and manage your obligations.")

    tab_run, tab_list = st.tabs(["Run calculation", "Obligations"])

    with tab_run:
        _render_run_form()

    with tab_list:
        _render_obligations_list()


def _render_run_form() -> None:
    st.subheader("New calculation")

    col1, col2 = st.columns(2)
    with col1:
        country = st.selectbox("Country", COUNTRIES, key="calc_country")
        category = st.selectbox("Product category", CATEGORIES, key="calc_category")
    with col2:
        year = st.number_input(
            "Reporting year", min_value=2020, max_value=2035,
            value=date.today().year, key="calc_year",
        )
        period_type = st.selectbox(
            "Period", ["Full year", "Q1", "Q2", "Q3", "Q4", "Custom"], key="calc_period_type"
        )

    period_start, period_end = _resolve_period(int(year), period_type)

    if period_type == "Custom":
        col_s, col_e = st.columns(2)
        with col_s:
            period_start = st.date_input("Period start", value=period_start, key="calc_start")
        with col_e:
            period_end = st.date_input("Period end", value=period_end, key="calc_end")

    st.caption(f"Period: **{period_start}** → **{period_end}**")

    if st.button("Run calculation", type="primary", key="calc_run"):
        if period_start >= period_end:
            st.error("Period start must be before period end.")
            return
        with st.spinner("Calculating…"):
            result = api_client.run_calculation(
                country_code=country,
                product_category=category,
                period_start=str(period_start),
                period_end=str(period_end),
            )
        if result is None:
            return
        st.success("Calculation complete!")
        _render_obligation_card(result, show_actions=False)


def _resolve_period(year: int, period_type: str) -> tuple[date, date]:
    quarters = {
        "Q1": (date(year, 1, 1), date(year, 3, 31)),
        "Q2": (date(year, 4, 1), date(year, 6, 30)),
        "Q3": (date(year, 7, 1), date(year, 9, 30)),
        "Q4": (date(year, 10, 1), date(year, 12, 31)),
    }
    if period_type in quarters:
        return quarters[period_type]
    return date(year, 1, 1), date(year, 12, 31)


def _render_obligations_list() -> None:
    st.subheader("All obligations")

    if st.button("Refresh", key="oblig_refresh"):
        st.rerun()

    obligations = api_client.list_obligations()
    if not obligations:
        st.info("No obligations yet. Use the 'Run calculation' tab to create one.")
        return

    st.caption(f"{len(obligations)} obligation(s)")
    for ob in obligations:
        _render_obligation_card(ob, show_actions=True)


def _render_obligation_card(ob: dict, *, show_actions: bool) -> None:
    status_icon = STATUS_COLOUR.get(ob["status"], "⚪")
    with st.container(border=True):
        col_info, col_fee, col_actions = st.columns([4, 2, 2])

        with col_info:
            st.markdown(
                f"{status_icon} **{ob['country_code']} — {ob['product_category']}**"
            )
            st.caption(
                f"Period: {ob['period_start']} → {ob['period_end']} | "
                f"Status: `{ob['status']}`"
            )
            if ob.get("calculated_at"):
                st.caption(f"Calculated: {ob['calculated_at'][:19].replace('T', ' ')}")

        with col_fee:
            st.metric(
                "Total fee",
                f"{float(ob['fee_amount']):,.4f} {ob['currency']}",
                help="Sum of all material fees",
            )
            st.caption(f"Weight: {float(ob['total_weight_kg']):,.3f} kg")

        with col_actions:
            if show_actions and ob["status"] == "draft":
                if st.button(
                    "Finalise", key=f"fin_{ob['id']}",
                    type="primary", use_container_width=True,
                ):
                    with st.spinner("Finalising…"):
                        api_client.finalise_obligation(ob["id"])
                    st.success("Obligation finalised.")
                    st.rerun()

                if st.button(
                    "Delete", key=f"del_{ob['id']}",
                    use_container_width=True,
                ):
                    api_client.delete_obligation(ob["id"])
                    st.success("Deleted.")
                    st.rerun()

        snapshot = ob.get("calculation_snapshot")
        if snapshot:
            with st.expander("Show calculation details"):
                _render_snapshot(snapshot)


def _render_snapshot(snapshot: dict) -> None:
    import pandas as pd  # noqa: PLC0415

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Weight by material (kg)**")
        wbm = snapshot.get("weight_by_material_kg", {})
        if wbm:
            st.dataframe(
                pd.DataFrame(
                    [{"Material": m, "Weight (kg)": float(w)} for m, w in wbm.items()]
                ),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No products in scope for this period.")
    with col2:
        st.markdown("**Rates used (per kg)**")
        ru = snapshot.get("rates_used", {})
        if ru:
            st.dataframe(
                pd.DataFrame(
                    [{"Material": m, "Rate": float(r), "Currency": snapshot.get("currency", "")}
                     for m, r in ru.items()]
                ),
                use_container_width=True, hide_index=True,
            )

    fee_by = snapshot.get("fee_by_material", {})
    if fee_by:
        st.markdown("**Fee by material**")
        rows = [
            {"Material": m, "Fee": float(f), "Currency": snapshot.get("currency", "")}
            for m, f in fee_by.items()
        ]
        currency = snapshot.get("currency", "")
        rows.append({
            "Material": "**TOTAL**",
            "Fee": float(snapshot.get("total_fee", 0)),
            "Currency": currency,
        })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    rate_set = snapshot.get("rate_set", {})
    if rate_set.get("regulation_reference"):
        st.caption(f"Regulation: {rate_set['regulation_reference']}")
