"""Dashboard page — high-level EPR compliance overview."""

from __future__ import annotations

import streamlit as st

from uusio.frontend import api_client

STATUS_COLOUR = {
    "draft": "🟡",
    "finalised": "🟢",
    "submitted": "🔵",
}

SUB_STATUS_COLOUR = {
    "pending": "🟡",
    "success": "🟢",
    "failed": "🔴",
    "acknowledged": "🔵",
}


def render() -> None:
    st.title("📊 Dashboard")
    st.caption("Your EPR compliance overview at a glance.")

    obligations = api_client.list_obligations()
    submissions = api_client.list_submissions()
    products = api_client.list_products(limit=1000)

    _render_kpi_row(obligations, submissions, products)
    st.divider()

    col_left, col_right = st.columns(2)
    with col_left:
        _render_obligations_summary(obligations)
    with col_right:
        _render_recent_submissions(submissions)

    st.divider()
    _render_compliance_checklist(obligations)


def _render_kpi_row(
    obligations: list[dict],
    submissions: list[dict],
    products: list[dict],
) -> None:
    draft = sum(1 for o in obligations if o["status"] == "draft")
    finalised = sum(1 for o in obligations if o["status"] == "finalised")
    submitted = sum(1 for o in obligations if o["status"] == "submitted")
    pending_subs = sum(1 for s in submissions if s["status"] == "pending")
    failed_subs = sum(1 for s in submissions if s["status"] == "failed")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📦 Products", len(products))
    with col2:
        st.metric("🟡 Draft obligations", draft)
    with col3:
        st.metric("🟢 Finalised", finalised)
    with col4:
        st.metric("🔵 Submitted", submitted)
    with col5:
        st.metric(
            "⚠️ Action needed",
            finalised + pending_subs + failed_subs,
            help="Finalised obligations awaiting submission + pending/failed submission attempts",
        )


def _render_obligations_summary(obligations: list[dict]) -> None:
    st.subheader("Obligations")

    if not obligations:
        st.info("No obligations yet. Go to **Calculations** to create one.")
        return

    import pandas as pd  # noqa: PLC0415

    rows = []
    for ob in obligations:
        icon = STATUS_COLOUR.get(ob["status"], "⚪")
        rows.append({
            "": icon,
            "Country": ob["country_code"],
            "Category": ob["product_category"],
            "Period": f"{ob['period_start']} → {ob['period_end']}",
            "Fee": f"{float(ob['fee_amount']):,.4f} {ob['currency']}",
            "Status": ob["status"],
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    needs_submission = [o for o in obligations if o["status"] == "finalised"]
    if needs_submission:
        st.warning(
            f"{len(needs_submission)} finalised obligation(s) awaiting submission. "
            "Go to **Submissions** to submit."
        )


def _render_recent_submissions(submissions: list[dict]) -> None:
    st.subheader("Recent submissions")

    if not submissions:
        st.info("No submission attempts yet.")
        return

    import pandas as pd  # noqa: PLC0415

    recent = submissions[:10]
    rows = []
    for s in recent:
        icon = SUB_STATUS_COLOUR.get(s["status"], "⚪")
        created = s["created_at"][:10]
        rows.append({
            "": icon,
            "PRO": s["pro_id"],
            "Method": s["submission_method"],
            "Status": s["status"],
            "Date": created,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    failed = [s for s in submissions if s["status"] == "failed"]
    if failed:
        st.error(
            f"{len(failed)} failed submission(s). Go to **Submissions** to retry."
        )


def _render_compliance_checklist(obligations: list[dict]) -> None:
    st.subheader("Compliance checklist")

    has_products = api_client.list_products(limit=1)
    steps = [
        (
            bool(has_products),
            "Product data uploaded",
            "Upload your product weight data on the **Products** page.",
        ),
        (
            any(o["status"] in ("draft", "finalised", "submitted") for o in obligations),
            "At least one calculation run",
            "Run your first EPR calculation on the **Calculations** page.",
        ),
        (
            any(o["status"] in ("finalised", "submitted") for o in obligations),
            "At least one obligation finalised",
            "Finalise a calculation to lock in the fee amount before submitting.",
        ),
        (
            any(o["status"] == "submitted" for o in obligations),
            "At least one obligation submitted",
            "Submit a finalised obligation to the PRO via the **Submissions** page.",
        ),
    ]

    all_done = all(done for done, _, _ in steps)
    if all_done:
        st.success("✅ All compliance steps completed for the current period!")
    else:
        st.caption("Complete these steps to stay compliant:")

    for done, label, hint in steps:
        icon = "✅" if done else "⬜"
        col_icon, col_text = st.columns([1, 12])
        with col_icon:
            st.markdown(icon)
        with col_text:
            if done:
                st.markdown(f"**{label}**")
            else:
                st.markdown(f"{label}")
                st.caption(hint)
