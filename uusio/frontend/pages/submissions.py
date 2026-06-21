"""Submissions page — submit finalised obligations to PRO portals or APIs."""

from __future__ import annotations

import streamlit as st

from uusio.frontend import api_client

STATUS_COLOUR = {
    "pending": "🟡",
    "success": "🟢",
    "failed": "🔴",
    "acknowledged": "🔵",
}

METHOD_ICON = {
    "portal": "🌐",
    "api": "⚡",
    "email": "📧",
}


def render() -> None:
    st.title("📤 Submissions")
    st.caption("Submit finalised EPR obligations to PRO portals and track attempts.")

    tab_submit, tab_history = st.tabs(["Submit obligation", "Submission history"])

    with tab_submit:
        _render_submit_tab()

    with tab_history:
        _render_history_tab()


def _render_submit_tab() -> None:
    st.subheader("Ready to submit")

    obligations = api_client.list_obligations()
    finalised = [ob for ob in obligations if ob["status"] == "finalised"]
    submitted = [ob for ob in obligations if ob["status"] == "submitted"]

    if not finalised and not submitted:
        st.info(
            "No finalised obligations found. "
            "Go to **Calculations** to run and finalise an obligation first."
        )
        return

    if submitted:
        st.caption(f"{len(submitted)} obligation(s) already submitted.")

    if not finalised:
        st.success("All obligations have been submitted.")
        return

    st.caption(f"{len(finalised)} finalised obligation(s) awaiting submission.")

    for ob in finalised:
        _render_submit_card(ob)


def _render_submit_card(ob: dict) -> None:
    with st.container(border=True):
        col_info, col_action = st.columns([5, 3])

        with col_info:
            st.markdown(f"**{ob['country_code']} — {ob['product_category']}**")
            st.caption(
                f"Period: {ob['period_start']} → {ob['period_end']} | "
                f"Fee: **{float(ob['fee_amount']):,.4f} {ob['currency']}**"
            )

        with col_action:
            method = st.selectbox(
                "Method",
                ["portal", "api"],
                key=f"method_{ob['id']}",
                help="portal: download CSV and upload manually. api: submit automatically.",
            )
            if st.button(
                "Submit", key=f"sub_{ob['id']}",
                type="primary", use_container_width=True,
            ):
                with st.spinner("Generating report and submitting…"):
                    result = api_client.submit_obligation(ob["id"], method)
                if result is None:
                    return

                if result["status"] == "success":
                    st.success(
                        f"Submitted via API. Reference: "
                        f"`{(result.get('response_payload') or {}).get('reference', 'N/A')}`"
                    )
                elif result["status"] == "failed":
                    st.error(f"Submission failed: {result.get('error_message', 'Unknown error')}")
                else:
                    # portal → PENDING
                    st.success("Report generated. Download it below and upload to the PRO portal.")
                    _render_download_button(result)
                st.rerun()


def _render_history_tab() -> None:
    st.subheader("Submission history")

    if st.button("Refresh", key="sub_refresh"):
        st.rerun()

    submissions = api_client.list_submissions()
    if not submissions:
        st.info("No submissions yet.")
        return

    st.caption(f"{len(submissions)} submission attempt(s)")
    for sub in submissions:
        _render_submission_card(sub)


def _render_submission_card(sub: dict) -> None:
    status_icon = STATUS_COLOUR.get(sub["status"], "⚪")
    method_icon = METHOD_ICON.get(sub["submission_method"], "🔌")
    attempt = sub["retry_count"] + 1

    with st.container(border=True):
        col_info, col_actions = st.columns([5, 3])

        with col_info:
            st.markdown(
                f"{status_icon} {method_icon} **{sub['pro_id']}** — "
                f"`{sub['status']}` (attempt #{attempt})"
            )
            created = sub["created_at"][:19].replace("T", " ")
            st.caption(f"Created: {created}")
            if sub.get("error_message"):
                st.error(sub["error_message"])
            payload = sub.get("response_payload") or {}
            if payload.get("reference"):
                st.caption(f"PRO reference: `{payload['reference']}`")

        with col_actions:
            _render_download_button(sub)

            if sub["status"] == "pending" and sub["submission_method"] == "portal":
                if st.button(
                    "Mark as acknowledged",
                    key=f"ack_{sub['id']}",
                    use_container_width=True,
                ):
                    with st.spinner("Acknowledging…"):
                        api_client.acknowledge_submission(sub["id"])
                    st.success("Marked as acknowledged.")
                    st.rerun()


def _render_download_button(sub: dict) -> None:
    """Fetch the report CSV bytes and offer a download button."""
    if not sub.get("report_file_path"):
        return

    report_bytes = api_client.download_submission_report(sub["id"])
    if report_bytes is None:
        return

    import os
    filename = os.path.basename(sub["report_file_path"])
    st.download_button(
        "⬇️ Download CSV",
        data=report_bytes,
        file_name=filename,
        mime="text/csv",
        key=f"dl_{sub['id']}",
        use_container_width=True,
    )
